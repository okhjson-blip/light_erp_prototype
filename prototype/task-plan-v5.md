# Task Plan v5 — GET 세부 역할 제한 / 완전 무상태 JWT / 컨테이너화

사용자 지시: "GET 세부 역할별 제한, 완전 무상태 JWT, 컨테이너화 진행해". 3개 항목 모두 여러
설계 선택지가 있어 AskUserQuestion으로 사전 확인, 전부 추천안 채택.

## 1. GET 엔드포인트 세부 역할별 제한 — 범위: 민감 모듈만

**결정**: 회계 전표(`accounting_document`/`gl_account`)와 CFO Copilot(재무 인사이트)만 관리자 전용으로
좁힌다. 나머지(자재/재고/영업/구매/생산/LOT 등)는 v4에서 정한 대로 로그인만 하면 전체 조회 유지 —
부서간 조회 공유가 실무상 자연스럽다는 v4 때의 판단을 그대로 유지.

**대상 엔드포인트** (모두 `Depends(current_user)` → `Depends(require_roles("관리자"))`로 변경):
- `GET /api/accounting/documents` (main.py `list_acc_docs`)
- `GET /api/accounting/documents/{doc_id}` (main.py `get_acc_doc`)
- `GET /api/gl-accounts` (main.py `list_gl_accounts`)
- `GET /api/ai/cfo-copilot/insights` (ai_agent.py `cfo_copilot_insights`)

**비범위**: 다른 모듈의 세부 역할별 조회 제한(예: 영업 데이터는 영업담당만)은 이번에도 하지 않는다 —
실사용 피드백 없이 미리 잠그면 대시보드/AI Agent의 교차조회 UX를 해칠 수 있다는 게 사용자 선택 이유.

**프론트엔드**: 회계 탭 폼/테이블과 AI Agent 탭의 CFO Copilot 섹션을 `hasRole("관리자")`로 조건부 렌더링
(다른 역할 로그인 시 섹션 자체를 숨김 — 이미 확립된 패턴, 예: MDM 폼의 `hasRole("관리자")` 처리와 동일).

## 2. 완전 무상태 JWT — Access+Refresh 이중 토큰

**기존(v4)**: 세션 테이블 대조가 매 요청마다 필요해 "JWT 포맷만 표준화"였을 뿐 무상태가 아니었음.

**결정**: 두 종류 토큰으로 분리.
- **Access token**: JWT, TTL **30분**. Payload에 `sub`(user_id)/`name`/`email`/`roles`/`iat`/`exp`/`typ:"access"`를
  전부 담아, `current_user()`가 **DB를 전혀 조회하지 않고** 서명+만료만 검증해 반환 — 매 요청 완전 무상태.
- **Refresh token**: 기존 `session` 테이블을 그대로 재사용(스키마 변경 없음 — `token`/`user_id`/`expires_at`
  컬럼 의미만 "refresh token 저장용"으로 바뀜). TTL은 기존과 동일하게 **8시간**. `POST /api/auth/refresh`로
  access token을 재발급받는다. Refresh token 자체는 회전(rotate)하지 않음(단순성 우선, 알려진 절충).
- **로그인**: `POST /api/auth/login` 응답이 `{access_token, refresh_token, user}`로 변경(기존 `token`
  필드는 제거 — 이 프로젝트는 아직 배포 전 프로토타입이라 하위호환 불필요, 프론트/테스트/시뮬레이터를
  전부 함께 갱신).
- **로그아웃**: refresh token을 DB에서 즉시 삭제(재발급 차단). **단, 이미 발급된 access token은 만료
  (최대 30분)까지 여전히 유효** — 이것이 완전 무상태화의 명시적 트레이드오프이며 AskUserQuestion에서
  사용자가 인지하고 선택한 부분. TTL을 8시간→30분으로 줄여 이 창을 최소화.
- **프론트엔드**: `api()` 헬�퍼가 401을 받으면 자동으로 `/api/auth/refresh` 시도 → 성공 시 원요청 재시도,
  실패 시 로그아웃 처리. Access/Refresh 토큰 모두 `localStorage`에 저장(기존 `erp_token` 단일 키를
  `erp_access_token`/`erp_refresh_token`으로 분리).

**비범위**: refresh token 회전(rotation), 디바이스별 다중 세션 관리, refresh token 탈취 탐지 — 실운영
전환 시 검토.

## 3. 컨테이너화 — 앱 Dockerfile + docker-compose 통합

**결정**: 멀티스테이지/nginx 없이 단일 스테이지 Dockerfile(`python:3.11-slim`)로 앱만 컨테이너화하고,
기존 `docker-compose.yml`(PostgreSQL 전용)에 `app` 서비스를 추가해 `docker compose up` 한 번으로
앱+DB가 함께 뜨도록 한다.
- `app` 서비스는 `postgres` 서비스에 `depends_on`(healthcheck 기반)으로 연결, `DATABASE_URL`을
  compose 내부 네트워크 주소(`postgres:5432`)로 자동 설정 — 사용자가 직접 환경변수를 export할 필요 없음.
- 이미 구현된 `GET /health`를 그대로 컨테이너 healthcheck에 활용(신규 엔드포인트 불필요).
- SQLite로 로컬에서 가볍게 띄우는 기존 방법(`pip install` + `uvicorn`)은 그대로 유지 — compose는
  "PostgreSQL 포함 완전한 환경"이 필요할 때 쓰는 옵션으로 포지셔닝.

**비범위** (AskUserQuestion에서 확인): nginx 리버스프록시/TLS, Kubernetes manifests, 이미지 레지스트리
푸시/CI 이미지 빌드 자동화 — 실운영 도메인/인증서가 없는 프로토타입 단계에서는 과설계로 판단.

## 검증 계획
- pytest 스위트(`tests/`)를 새 로그인 응답 포맷(`access_token`/`refresh_token`)에 맞게 갱신 후 전체 재실행.
- 신규 시나리오 테스트 추가: refresh 토큰으로 재발급, 로그아웃 후 refresh 거부(그러나 기존 access는
  만료 전까지 유효 — 이 트레이드오프를 테스트로 명시적으로 증명), 회계/CFO 엔드포인트 403(비관리자).
- `docker compose build` + `docker compose up` 후 `GET /health` 응답 확인(샌드박스에서 가능한 범위,
  실제 포트/네트워크는 사용자 로컬에서 최종 확인 권장 — PostgreSQL 로컬검증 때와 동일 패턴).
