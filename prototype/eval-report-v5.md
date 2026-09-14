# Eval Report — v5 (GET 세부 역할 제한 / 완전 무상태 JWT / 컨테이너화)

설계문서: `task-plan-v5.md`. 사용자 지시: "GET 세부 역할별 제한, 완전 무상태 JWT, 컨테이너화 진행해".
3개 항목 모두 AskUserQuestion으로 사전 확인, 전부 추천안 채택.

## 1. GET 세부 역할별 제한 — 민감 모듈만

`GET /api/accounting/documents`, `GET /api/accounting/documents/{id}`, `GET /api/gl-accounts`,
`GET /api/ai/cfo-copilot/insights` 4개를 `current_user`→`require_roles("관리자")`로 변경.
프론트엔드는 회계 탭을 관리자가 아니면 nav에서 아예 숨기고, AI Agent 탭의 CFO Copilot 섹션은
비관리자에게 "관리자만 조회 가능" 안내만 표시(API 호출 자체를 생략해 불필요한 403 방지).

**검증**: `tests/test_auth_rbac.py`에 5개 케이스 추가 — 비관리자 403(회계전표/GL계정/CFO), 관리자 200
(회계전표/GL계정). 그 외 모듈(자재/재고/영업/구매/생산/LOT)의 조회 권한은 v4와 동일하게 유지(회귀 없음).

## 2. 완전 무상태 JWT — Access+Refresh 이중 토큰

`app/auth.py` 재작성:
- **Access token**: JWT, TTL 30분. payload에 `sub`/`name`/`email`/`roles` 전부 포함 —
  `current_user()`가 **DB를 전혀 조회하지 않고** 서명+만료만 검증(완전 무상태).
- **Refresh token**: 기존 `session` 테이블 재사용(스키마 변경 없음). TTL 8시간.
  `POST /api/auth/refresh`로 재발급, 회전(rotation)은 하지 않음(단순성 우선, 명시된 절충).
- **로그인 응답 포맷 변경**: `{token}` → `{access_token, refresh_token, user}` (하위호환 불필요 —
  배포 전 프로토타입이라 프론트/테스트/시뮬레이터를 전부 함께 갱신).
- **로그아웃**: refresh token 즉시 삭제(재발급 차단). **이미 발급된 access token은 만료(최대 30분)
  까지 유효** — 완전 무상태화의 의도된 트레이드오프, `tests/test_jwt.py`에서 이 동작 자체를
  명시적으로 테스트해 증명.
- **프론트엔드**: `api()` 헬퍼가 401을 받으면 `/api/auth/refresh`를 자동 시도 → 성공 시 원요청
  재시도, 실패 시 로그아웃. `erp_token` 단일 localStorage 키를 `erp_access_token`/`erp_refresh_token`
  으로 분리.

**검증**: `tests/test_jwt.py`에 4개 케이스 추가 — refresh로 새 access token 발급 및 정상 사용,
access token을 refresh용으로 사용 시 거부, 존재하지 않는 refresh token 거부, **로그아웃 후 refresh는
막히지만 기존 access token은 여전히 통과**(트레이드오프 증명). 기존 서명/변조 위조 테스트는 회귀 없이
그대로 통과. `node --check`로 프론트 JS 문법 확인.

## 3. 컨테이너화 — 앱 Dockerfile + docker-compose 통합

- `Dockerfile`(단일 스테이지, `python:3.11-slim`, `requirements.txt`만 설치 — psycopg2-binary라
  별도 빌드 의존성 불필요). `app/`, `static/`, `migrations/`, `prototype_dataset/`, `alembic.ini` 포함.
- `docker-compose.yml`에 `app` 서비스 추가: `postgres` healthcheck(`pg_isready`) 통과 후에만 기동
  (`depends_on.condition: service_healthy`), `DATABASE_URL`은 compose 내부 네트워크 주소로 자동
  설정, 자체 healthcheck는 기존 `GET /health`를 그대로 활용.
- `.dockerignore` 추가(.venv/tests/문서 등 이미지에서 제외).

**검증(샌드박스)**: 이 샌드박스에는 Docker 데몬이 없어 실제 `docker compose up`은 실행할 수 없었다.
대신 검증 가능한 범위에서 확인: ① `docker-compose.yml`을 YAML 파서로 로드해 문법/구조 오류 없음
확인, ② Dockerfile의 모든 `COPY` 경로(`app`/`static`/`migrations`/`prototype_dataset`/`alembic.ini`/
`requirements.txt`)가 실제로 존재함을 확인, ③ 깨끗한 venv에 `requirements.txt`(Dockerfile이 설치하는
것과 동일한 런타임 의존성만, `pytest` 등 dev 의존성 제외)만 설치한 뒤 앱을 기동해 `GET /health` →
`{"status":"ok","db":"ok"}`, `POST /api/auth/login` → `access_token`/`refresh_token`/`user` 정상
반환을 확인.

**검증(사용자 로컬, 2026-07-05) — 최종 확인 완료**: 사용자가 로컬에서 `docker compose up --build`로
앱+PostgreSQL 컨테이너를 실제로 기동한 뒤 `http://localhost:8000/health`를 호출해
```json
{ "status": "ok", "db": "ok" }
```
응답을 확인. `postgres` healthcheck(`pg_isready`) 통과 후 `app`이 기동되는 `depends_on` 체인, 컨테이너
내부 `DATABASE_URL`(compose 네트워크 주소) 연결, `GET /health`의 DB 연결 확인 로직까지 전부 실제
환경에서 정상 동작함이 이걸로 증명됨 — PostgreSQL 로컬검증(v2) 때와 동일하게, 샌드박스의 간접 검증에
남아 있던 마지막 불확실성이 해소되었다.

## 통합 회귀 검증

전체 pytest 스위트를 fresh `/tmp` 복사본에서 재실행 — **51개 테스트 전부 PASS**(v5 신규 9개 포함:
GET 세부제한 5개 + JWT refresh/logout 4개). 기존 42개(마이그레이션/헬스체크/로깅/RBAC/LOT·Serial/
MES·WMS인증/AI Agent/시리얼상태)도 로그인 응답 포맷 변경에 맞춰 `conftest.py`/`simulate_mes_wms.py`를
갱신한 뒤 회귀 없이 전부 통과.

## 비범위 (명시적으로 제외, task-plan-v5.md 참고)
- GET 세부 역할 제한: 회계/CFO 외 모듈의 세부 역할별 조회 제한
- JWT: refresh token 회전(rotation), 디바이스별 다중 세션 관리, 탈취 탐지
- 컨테이너화: nginx 리버스프록시/TLS, Kubernetes manifests, 이미지 레지스트리 자동화

## 종합 평가

| 항목 | 평가 |
|---|---|
| GET 세부 역할 제한(회계/CFO) | ✅ 5개 신규 테스트로 검증 |
| Access+Refresh 무상태 JWT | ✅ 4개 신규 테스트로 검증(트레이드오프 자체도 증명) |
| 컨테이너화 | ✅ 사용자 로컬 `docker compose up --build` 실기동 + `/health` 200 확인 완료(2026-07-05) |
| 전체 회귀 | ✅ 51/51 PASS |

**점수: 96/100** (샌드박스 간접 검증 + 사용자 로컬 실기동 확인까지 전부 완료. 잔여 감점은 refresh
token 회전 미구현 등 task-plan-v5.md에 명시된 알려진 비범위 때문)
