# AX ERP Prototype v1 / v2

Phase 1 Core 7모듈(MDM/Sales/Procurement/Production/Inventory/FI/Common)을
FastAPI + SQLAlchemy(SQLite 기본, PostgreSQL 전환 가능)로 구현한 프로토타입.
v2에서 MES/WMS mock 연계, AI Agent(Buyer/Scheduler) 추천을 추가했다.

## 실행 방법 (SQLite, 기본)
```bash
cd prototype
python3 -m venv .venv && source .venv/bin/activate   # 선택
pip install -r requirements.txt
uvicorn app.main:app --reload
```
최초 실행 시 `app/erp.db`가 자동 생성되고 기준정보(회사/공장/창고/품목/BOM/고객/공급사/계정과목)가
시드된다. 화면은 React 프론트엔드(`frontend/`)를 별도로 띄워서 봐야 한다 — 아래 "React 프론트엔드"
섹션 참고. `http://127.0.0.1:8000`에 직접 접속하면(운영 빌드 전) 안내 메시지 JSON만 반환된다.

## PostgreSQL로 전환 (v2)
```bash
docker-compose up -d          # 로컬 PostgreSQL 16 기동 (호스트 포트 5433 사용)
cp .env.example .env          # DATABASE_URL 주석 해제 후 사용
export DATABASE_URL=postgresql+psycopg2://erp:erp_local_dev@127.0.0.1:5433/standard_erp
uvicorn app.main:app --reload
```
코드/SQL은 SQLite와 동일하게 동작하며(`app/database.py`가 방언별로 `schema_sqlite.sql`/
`schema_postgres.sql` 중 하나를 선택), `DATABASE_URL`을 지정하지 않으면 항상 SQLite로 기동한다.
> 참고: 호스트 포트는 5432가 아닌 **5433**을 사용한다 — 로컬에 이미 다른 Postgres가 5432를
> 점유 중인 경우가 흔해 충돌을 피하기 위함(실제로 이 프로젝트 검증 중에도 발견된 이슈).
> `verify_postgres.command`로 원클릭 검증 가능(연결→스키마→시드→E2E 스모크 테스트) —
> **2026-07-05 사용자 로컬 환경에서 전체 PASS 확인 완료** (`eval-report-postgres-verify.md` 참고).

## 컨테이너화 (v5, v8에서 프론트엔드 포함) — 앱+DB를 한번에
`Dockerfile`(2-스테이지: `node:20-slim`으로 React 빌드 → `python:3.11-slim`에 결과물만 복사)로
앱을 이미지화하고, `docker-compose.yml`에 `app` 서비스를 추가해 PostgreSQL과 함께 한 번에 띄울 수 있다.
v8부터는 이미지 안에 `frontend/dist`가 포함되어 `/`에서 바로 React 화면이 서빙된다(별도 `npm run build`
불필요 — 이미지 빌드 과정에서 자동 수행). **이 다단계 빌드 자체는 샌드박스에 Docker가 없어 실행/검증하지
못했다** — 아래 명령은 사용자 로컬에서 실행 확인 필요.
```bash
docker compose up --build       # 앱(8000) + PostgreSQL(5433) 함께 기동
curl http://127.0.0.1:8000/health   # {"status":"ok","db":"ok"} 확인
```
- `app` 서비스는 `postgres` 서비스가 healthy(= `pg_isready` 통과)해질 때까지 기동을 기다린다
  (`depends_on.condition: service_healthy`).
- `app` 자체의 healthcheck는 이미 구현된 `GET /health`를 그대로 활용한다(신규 엔드포인트 불필요).
- `DATABASE_URL`은 compose 내부 네트워크 주소(`postgres:5432`)로 자동 설정되어 사용자가 직접
  환경변수를 export할 필요가 없다.
- 최초 기동 시 `init_db()`가 Alembic 마이그레이션(`alembic upgrade head`)으로 스키마를 생성하고,
  신규 DB면 `prototype_dataset/` CSV 시드를 자동 임포트한다(기존 로컬 실행과 동일한 동작).
- SQLite로 가볍게 로컬에서 띄우는 기존 방법(`pip install` + `uvicorn`, 맨 위 "실행 방법" 참고)은
  그대로 유지된다 — compose는 PostgreSQL을 포함한 완전한 환경이 필요할 때 쓰는 옵션.
- **비범위**(명시적으로 제외, task-plan-v5.md 참고): nginx 리버스프록시/TLS, Kubernetes manifests,
  이미지 레지스트리 푸시/CI 이미지 빌드 자동화 — 실운영 도메인/인증서가 없는 프로토타입 단계에서는
  과설계로 판단.

## MES/WMS 연계 (v2, Mock) — API Key 인증 (v3)
실제 MES/WMS 시스템이 없으므로, 그 시스템들이 보낼 법한 Webhook을 받는 엔드포인트를
`app/integrations.py`에 구현하고 Mock 이벤트를 보내는 시뮬레이터를 제공한다.
```bash
uvicorn app.main:app --reload          # 터미널 1
python3 simulate_mes_wms.py            # 터미널 2 — MES 생산실적 + WMS 입고 이벤트 전송
```
결과는 화면의 "연동 로그" 탭 또는 `GET /api/integrations/events`(비인증 조회 가능)에서 확인 가능.
- **인증**: 두 웹훅 엔드포인트(`POST /api/integrations/mes/production-result`,
  `POST /api/integrations/wms/inventory-movement`)는 `X-API-Key` 헤더를 요구한다. RBAC의 세션 인증과는
  별개로, 외부 시스템 간(system-to-system) 호출에 맞춘 단순 공유키 방식이다(신규 의존성 없음).
- **데모 키** (고정값 — 실제 운영 전환 시 반드시 교체): `mes-demo-key-please-rotate`(MES),
  `wms-demo-key-please-rotate`(WMS). `source_system`이 다르면 교차 사용이 차단된다(MES 키로 WMS
  엔드포인트 호출 불가).
- 실제 시스템 연동 시에는 두 엔드포인트의 URL과 API Key만 실제 스펙에 맞게 교체하면 되고, 내부 처리
  로직(재고/LOT 반영)은 그대로 재사용 가능.
- 상세 설계/성공기준은 `task-plan-mes-auth.md` / `eval-report-mes-auth.md` 참고

## AI Agent 추천 (v2/v3, 규칙기반 — LLM 미호출)
화면의 "AI Agent" 탭에서 확인. 거버넌스 원칙(추천만 제공, 사람이 승인 후 실행)을 지킨다.
- **AI Buyer**(`GET /api/ai/buyer/recommendations`): 재고가 재발주점 아래인 원자재에 대해
  추천 발주량/공급사 제시 → "PR 생성 적용" 버튼(`POST /api/ai/buyer/apply`)을 눌러야 실제 PR 생성
- **AI Production Scheduler**(`GET /api/ai/scheduler/recommendations`): 오픈 생산오더를
  자재 가용성 기준으로 우선순위 정렬, 부족 자재 상세 표시
- **AI Demand Planner**(`GET /api/ai/demand-planner/recommendations`): 최근 3개월 수요예측 오차(MAPE)가
  10% 이상인 품목을 찾아 재발주점/목표재고 조정값 제안 → "계획값 적용" 버튼(`POST /api/ai/demand-planner/apply`)을
  눌러야 material에 실제 반영(금액 이동이 없는 계획 파라미터라 승인 워크플로 없이 즉시 반영)
- **AI Quality Engineer**(`GET /api/ai/quality/recommendations`): 품목별 최근 6건 품질검사 중
  불량(FAIL)/CAPA 필요 비율이 높은 품목에 위험도(높음/중간)와 근거 제시. CAPA 실행 워크플로가 없어 조회전용
- **CFO Copilot**(`GET /api/ai/cfo-copilot/insights`): 월별 재무 요약의 영업이익률 변화, 영업이익 대비
  현금흐름 괴리, 공급 리스크 건수, 라이브 매출채권/매입채무를 조합한 인사이트 목록. 조회전용(자문 역할)
- 상세 설계/성공기준은 `task-plan-ai-agent-v3.md` / `eval-report-ai-agent-v3.md` 참고
- **LLM 고도화 1단계(v3)**: 각 추천/인사이트에 사람이 읽기 편한 자연어 문단 `ai_narrative`를
  추가했다(화면의 "AI 설명" 컬럼). 현재는 템플릿 기반 생성(`app/llm_rationale.py`)만 제공하며
  외부 LLM API는 호출하지 않는다(신규 의존성/토큰 비용 없음). 추천 대상/수치 산출 로직은 그대로
  규칙기반이며, 실제 LLM API 연계는 통합테스트/현업 검증 단계에서 필요시 진행하기로 사용자와
  확인됨. 상세는 `task-plan-llm-narrative.md` / `eval-report-llm-narrative.md` 참고

## RBAC (역할 기반 접근 제어, v3~v6)
로그인 화면(이메일+비밀번호)이 최초 화면. `Authorization: Bearer <access_token>` 헤더로 API 호출.
- **데모 계정** (비밀번호 전부 `demo1234` — 실제 운영 전환 시 반드시 교체할 것):
  `admin@standard-erp.local`(관리자) / `sales@standard-erp.local`(영업담당) /
  `purchase@standard-erp.local`(구매담당) / `production@standard-erp.local`(생산담당)
- **인가 범위(v4~v5)**: 상태를 변경하는 POST 엔드포인트는 역할로 게이팅한다(관리자는 모든
  역할 겸용). MDM 생성/회계 수동전표/승인 결재/AI Agent apply는 관리자 전용. 영업·구매·생산
  트랜잭션은 각 담당 역할(+관리자)만 가능. GET(조회)은 v4부터 로그인을 요구하며 기본적으로 역할
  무관 전체 조회가 가능하지만, **v5부터 재무 민감정보(회계 전표 `GET /api/accounting/documents*`,
  계정과목 `GET /api/gl-accounts`, CFO Copilot `GET /api/ai/cfo-copilot/insights`)는 조회도
  관리자 전용**으로 좁혔다(그 외 모듈의 세부 역할별 조회 제한은 여전히 비범위). `/`(운영 빌드 서빙
  또는 안내 메시지)와 `/assets/*`(React 정적 자산)는 로그인 화면 자체를 봐야 하므로 계속 비인증.
  프론트엔드도 역할에 맞지 않는 탭/폼/버튼은 아예 숨긴다.
- **토큰 체계(v5, 완전 무상태 전환)**: Access token(JWT, **TTL 30분**)과 Refresh token(JWT, TTL
  8시간) 이중 구조. Access token은 `sub`/`name`/`email`/`roles`를 payload에 전부 담아
  `current_user()`가 **DB를 전혀 조회하지 않고** 서명+만료만 검증한다(완전 무상태). Refresh token은
  기존 세션 테이블(`session`)을 그대로 재사용(스키마 변경 없음)해 `POST /api/auth/refresh`로 access
  token을 재발급받는다. 로그아웃(`POST /api/auth/logout`)은 refresh token을 즉시 삭제해 재발급을
  막지만, **이미 발급된 access token은 자연 만료(최대 30분)까지 유효**하다 — 이것이 완전 무상태화의
  의도된 트레이드오프(TTL을 짧게 유지해 창을 최소화). 신규 라이브러리 없이 `hmac`/`base64`/`json`
  표준 라이브러리만으로 서명·검증을 자체 구현(`app/auth.py`). 서명 키는 `JWT_SECRET` 환경변수로
  교체 가능(기본값은 개발용 — 운영 전환 시 필수 교체). 프론트엔드는 401 응답 시 자동으로 refresh를
  시도한 뒤 원요청을 1회 재시도한다.
- **Refresh token 회전 + 재사용 탐지(v6)**: `POST /api/auth/refresh` 호출마다 refresh token도 함께
  회전한다(응답에 새 `refresh_token` 포함, 이전 것은 즉시 폐기). 이미 폐기된(rotated) refresh token이
  다시 제시되면 탈취로 간주해 **그 로그인에서 파생된 모든 토큰(family)을 즉시 무효화**하고 401 +
  경고 로그를 남긴다 — 정상 클라이언트는 항상 최신 토큰만 쓰므로, 오래된 토큰의 재등장은 도난 신호로
  본다. `session` 테이블에 `family_id`/`rotated_at` 컬럼 추가(Alembic
  `migrations/versions/0002_session_rotation.py`, 기존 세션은 자기 `token` 값으로 family를 개별
  격리해 마이그레이션함). Family의 만료(8시간)는 로그인 시점 기준 고정 — 계속 refresh해도 연장되지
  않는다. 로그아웃도 family 전체를 지운다. 프론트엔드는 refresh 응답의 새 `refresh_token`으로 반드시
  교체 저장한다.
- 상세 설계/성공기준은 `task-plan-rbac.md`/`eval-report-rbac.md`,
  `task-plan-get-auth.md`/`task-plan-jwt.md`/`eval-report-v4-auth-serial.md`,
  `task-plan-v5.md`/`eval-report-v5.md`,
  `task-plan-refresh-rotation.md`/`eval-report-refresh-rotation.md` 참고

## WMS/QMS LOT·Serial 추적 (v3)
기존 `inventory`(집계) 테이블은 그대로 두고, LOT은 병행 기록되는 별도 레이어다(신규 의존성 없음).
- **LOT 생성**: 입고처리(GR) / 생산실적입력(FG) / WMS IN 이벤트 시 자동 생성
- **LOT 소진(FIFO)**: 출하 / 생산실적의 BOM 소요(RM) / WMS OUT 이벤트 시 가장 오래된 LOT부터 소진
- **시리얼(선택 기능)**: 생산실적입력 시 "시리얼 생성" 체크박스를 켠 경우에만 완제품 LOT 안에 개별
  시리얼 생성(1회 최대 500개). 조회: `GET /api/serials`, `GET /api/serials/{serial_no}/trace`
- **시리얼 상태 관리(v4)**: 출하 시 소진 수량만큼 시리얼이 자동으로 SHIPPED 처리된다(생성순).
  `POST /api/serials/{serial_no}/status`로 IN_STOCK/SHIPPED/DEFECTIVE/SCRAPPED 수동 변경도 가능
  (생산담당+관리자 권한 — 품질 불량/폐기 판단용). 재고 탭에서 상태변경 UI 제공. 상세는
  `task-plan-serial-ui.md` 참고
- **LOT 조회/역추적**: `GET /api/lots`(필터: material_id/warehouse_id/status), `GET /api/lots/{lot_id}/trace`
  (생성출처+소진이력). 재고 탭에서 확인 가능
- **QMS 실시간 검사 등록**: `POST /api/quality/inspections`(LOT 연결 가능) — 생산담당+관리자 권한.
  기존 임포트 참조데이터(quality_inspection, reference_data.py)는 조회전용으로 그대로 유지
- **알려진 비범위**: 과거 임포트 재고는 LOT이 없어 소급 생성하지 않음(FIFO 소진 시 가용 LOT 부족해도
  에러 없이 가능한 만큼만 처리). 유효기한/리콜 워크플로 미포함. 상세는 `task-plan-lot-serial.md` /
  `eval-report-lot-serial.md` 참고
- **정합성 검증**: `GET /api/lots/reconciliation` — 품목×창고별 활성 LOT 합계와 재고집계
  (inventory.qty)를 비교한다. 재고집계가 더 큰 것(미추적수량 > 0)은 과거 임포트 재고 등으로 인한
  정상 상황이며, 반대로 LOT 합계가 재고집계를 초과하면(미추적수량 < 0) 실제 버그 신호로
  `consistent:false`로 표시한다. 재고 탭에서 확인 가능. 상세는 `task-plan-lot-reconciliation.md` /
  `eval-report-lot-reconciliation.md` 참고

## 운영 인프라 (v4, MVP)
프로토타입 단계를 지나 실제로 운영 가능한 최소 기반(마이그레이션/헬스체크/로깅/자동테스트/CI)을 갖췄다.
- **DB 마이그레이션(Alembic)**: 이 프로젝트의 첫 신규 런타임 의존성(사용자 확인됨). ORM 모델이 없어
  autogenerate는 쓸 수 없고, 모든 마이그레이션은 `migrations/versions/`에 손으로 작성한 raw SQL이다.
  최초 마이그레이션(`0001_initial_schema.py`)은 기존 `schema_sqlite.sql`/`schema_postgres.sql`을 그대로
  실행해 기존 스키마와 동일하게 맞췄다. `init_db()`가 자동으로: (1) 완전 신규 DB → `alembic upgrade head`,
  (2) Alembic 전환 이전에 만들어진 기존 DB(테이블은 있으나 `alembic_version` 없음) → 데이터 손실 없이
  `alembic stamp head`, (3) 이미 추적 중인 DB → `alembic upgrade head`를 자동 판단해 실행한다. 이제
  스키마가 바뀌어도 `app/erp.db`를 지울 필요가 없다 — `migrations/versions/`에 새 리비전만 추가하면 됨.
- **헬스체크**: `GET /health`(비인증) — DB 연결까지 확인 후 `{"status":"ok","db":"ok"}` 반환. 인프라
  프로브용으로 GET 인증 확장(v4) 대상에서 제외.
- **구조화 로깅**: 표준 라이브러리 `logging`만 사용(신규 의존성 없음). 서버 기동/마이그레이션/시드
  적재 등 주요 이벤트를 타임스탬프+레벨 포맷으로 기록.
- **pytest 테스트 스위트**: 그동안 `/tmp`에서 임시로 실행하던 검증 스크립트를 `tests/`로 정식화했다
  (RBAC·JWT·LOT/Serial·LOT 정합성·MES/WMS 인증·AI Agent·시리얼 상태변경·헬스체크 8개 파일, 총 42개
  테스트). 실행: `pip install -r requirements-dev.txt && pytest`. 실 개발용 `app/erp.db`는 절대 건드리지
  않고 `tests/conftest.py`가 임시 SQLite 파일로 격리한다.
- **CI/CD**: `.github/workflows/ci.yml` — push/PR 시 `requirements-dev.txt` 설치 후 pytest 자동 실행.
- 상세 설계/성공기준은 `task-plan-mvp-infra.md` / `eval-report-mvp-infra.md` 참고

## 화면 구성
로그인 → 대시보드 / 기준정보(MDM) / 영업 / 구매 / 생산 / 재고 / 회계 / 승인함 / 연동 로그 / AI Agent / 참고 데이터 — 11개 탭
(생산 탭에 품질검사 등록, 재고 탭에 LOT/시리얼 조회가 추가됨). **v7부터 이 화면은 React 프론트엔드
(`frontend/`)로 완전히 이관되었다** — 아래 섹션 참고.

## React 프론트엔드 (v7, 이관 완료)
기존 `static/index.html`(vanilla JS)의 11개 탭 전 기능이 `frontend/`(React)로 완전히 이관되어
**static/index.html은 제거되었다**. 백엔드는 이미 순수 JSON REST API + JWT 인증이라 이관 과정에서
**백엔드 API 변경은 전혀 없었다**.
```bash
# 터미널 1 (백엔드)
cd prototype
uvicorn app.main:app --reload          # http://127.0.0.1:8000

# 터미널 2 (프론트엔드, 개발 중)
cd prototype/frontend
npm install                            # 최초 1회
npm run dev                            # http://localhost:5183, /api·/health는 :8000으로 프록시
```
> 위 두 단계를 매번 손으로 치기 번거로우면 `run_server.command`(백엔드) /
> `run_frontend.command`(프론트엔드)를 더블클릭하면 된다(Mac). `run_frontend.command`는
> `node_modules`가 없으면 자동 설치하고, 백엔드(`:8000`)가 응답하지 않으면 경고를 띄운 뒤
> `npm run dev`를 실행한다.

운영 빌드는 `cd frontend && npm run build` → `frontend/dist/`가 만들어지면 백엔드가 `/`에서 바로
서빙한다(`app/main.py`가 `frontend/dist/index.html` 존재 여부를 자동 판단 — 아직 빌드하지 않았으면
`/`는 개발 서버 안내 JSON을 반환). **v8부터 Docker 이미지에도 프론트엔드 빌드가 포함된다** — `Dockerfile`이
Node 멀티스테이지(1: `node:20-slim`으로 `frontend/` 빌드 → 2: `python:3.11-slim`에 `frontend/dist`만
복사)로 바뀌었다. Stage 1은 `package-lock.json`을 복사하지 않고 `package.json`만으로 `npm install`을
새로 실행 — 호스트(Mac)에서 만들어진 lockfile이 rolldown/vite의 플랫폼별 네이티브 바이너리를 고정해버려
리눅스 컨테이너에서 설치가 깨지는 문제(이 프로젝트에서 두 번 겪음)를 원천 차단하기 위함. **미검증**:
샌드박스에 Docker가 없어 `docker build`/`docker compose up --build`는 사용자 로컬 확인 필요.
- **스택**: Vite + React 19 + TypeScript + Tailwind CSS v4(`@theme` 토큰에 `ui-identity.md`의 hex
  값 이식) + React Router + TanStack Query + Recharts(Tremor 스타일 KPI 카드 직접 구현 — `@tremor/react`
  패키지 자체는 배포방식 불확실로 미설치) + shadcn/ui 스타일 컴포넌트(CLI 대신 소스 직접 작성).
- **1차**: 로그인, 사이드바+상단바 셸(역할별 탭 숨김·배지), 대시보드(KPI 6종).
- **2차**: 기준정보(품목/고객/공급사 등록+목록), 영업(수주 등록+출하/청구), 구매(PR/PO 등록+입고처리).
- **3차**: 생산(생산오더 등록/작업지시/실적입력+QMS 품질검사 등록), 재고(현재고/이동이력/LOT추적/
  시리얼추적/LOT정합성 점검).
- **4차**: 회계(관리자 전용), 승인함(승인/반려), 연동 로그(payload 보기 토글+시스템 아이콘).
- **5차**: AI Agent(5종 추천 카드, rationale/ai_narrative 시각적 분리), 참고 데이터(6개 서브테이블
  탭 전환). **마무리**로 `static/index.html` 제거, `app/main.py`의 `/`가 `frontend/dist/` 자동 서빙
  (없으면 안내 메시지)하도록 정리, `Dockerfile`에서 `static/` 복사 라인 제거 — pytest 55개 전부
  회귀 없이 통과 확인.
- **미확인**: 1~5차 전체에 걸쳐 `vite build`/브라우저 실기동은 플랫폼(리눅스 샌드박스↔Mac) 바이너리
  불일치로 이 프로젝트의 개발 세션에서 직접 실행하지 못했다(타입체크+API 계약 검증으로 대체) — 1차만
  사용자 로컬에서 실기동 확인됨. 2~5차는 아직 사용자 로컬 확인 필요.
- 상세 설계/검증은 `task-plan-frontend-react.md` / `eval-report-frontend-v1.md` /
  `eval-report-frontend-v2.md` / `eval-report-frontend-v3.md` / `eval-report-frontend-v4.md` /
  `eval-report-frontend-v5.md` 참고
- **v8**: topbar에 세션 관리 Dialog(`SessionsDialog.tsx`, Radix `@radix-ui/react-dialog` 최초 사용)
  추가 — 로그인된 기기 목록 조회 + 기기별 개별 로그아웃. 대시보드 KPI에 "LOT 정합성 불일치" 카드 추가.
  자세한 내용은 `eval-report-v8.md` 참고.

## 검증된 E2E 흐름
1. 수주 등록 → 출하(재고 차감) → 청구(매출채권/매출 전표 자동 생성)
2. PR 등록 → 승인 → PO 등록 → 입고처리(재고 증가, 매입채무 전표 자동 생성)
3. 생산오더 등록 → 작업지시 → 실적입력(BOM 소요 원자재 차감 + 완제품 입고)
4. MES 생산실적 Webhook / WMS 입출고 Webhook → 재고 반영 + 이벤트 로그 기록
5. AI Buyer 추천 → PR 생성 적용 → 승인함 반영 / AI Scheduler 우선순위 산정

## 샘플 데이터셋 (prototype_dataset/)
전자부품·소형가전 제조사 가정의 다국적(4개사/5개공장/8개창고) 현실적 샘플 데이터 17종 CSV.
최초 기동 시 `app/seed.py`가 자동 임포트하며(코드→ID 매핑, 재고스냅샷을 현재잔고로 직접 반영),
DB가 이미 있으면 재적재하지 않는다. 재적재하려면 `app/erp.db` 삭제 후 재기동.
SCM(수요예측)/QMS(품질검사)/WMS(출하)/EIS(재무·KPI)/AI Copilot(추천이력)처럼 아직 업무 로직이
없는 6종은 "참고 데이터" 탭에서 조회 전용으로 볼 수 있다. `prototype_dataset/`이 없으면 기존
최소 데모 데이터로 자동 대체된다.

## 문서
- `task-plan.md` / `eval-report.md` — v1 Planner/Evaluator 산출물
- `task-plan-v2.md` / `eval-report-v2.md` — v2 Planner/Evaluator 산출물
- `task-plan-dataset-import.md` / `eval-report-dataset-import.md` — 샘플 데이터셋 임포트 산출물

## 공장·창고 선택 UI (2026-07-05 개선)
출하/입고처리/생산실적입력 시 예전에는 "타입이 일치하는 첫 번째 창고"를 자동 선택했으나,
이제 버튼 클릭 시 인라인 드롭다운(공장명·창고명 표시)이 나타나 사용자가 직접 창고를 선택한다.
생산실적입력은 해당 생산오더의 공장을 목록 최상단에 우선 정렬해 보여준다(다른 공장 창고도 선택 가능).
확인/취소 버튼으로 선택을 확정하거나 되돌릴 수 있다.

## 문서 (계속)
- `task-plan-ai-agent-v3.md` / `eval-report-ai-agent-v3.md` — AI Agent 5종 완성 산출물
- `eval-report-postgres-verify.md` — PostgreSQL 로컬 접속 검증 산출물
- `task-plan-rbac.md` / `eval-report-rbac.md` — RBAC(역할 기반 접근 제어) 산출물
- `task-plan-lot-serial.md` / `eval-report-lot-serial.md` — WMS/QMS LOT·Serial 추적 산출물
- `task-plan-mes-auth.md` / `eval-report-mes-auth.md` — MES/WMS 웹훅 API Key 인증 산출물
- `task-plan-llm-narrative.md` / `eval-report-llm-narrative.md` — AI Agent LLM 고도화 1단계 산출물
- `task-plan-lot-reconciliation.md` / `eval-report-lot-reconciliation.md` — LOT 정합성 검증 산출물
- `task-plan-get-auth.md`, `task-plan-jwt.md`, `task-plan-serial-ui.md` /
  `eval-report-v4-auth-serial.md` — GET 인증 확장 + JWT 전환 + 시리얼 UI 고도화 산출물
- `task-plan-mvp-infra.md` / `eval-report-mvp-infra.md` — 운영 인프라 MVP(마이그레이션/헬스체크·
  로깅/pytest/CI) 산출물
- `task-plan-v5.md` / `eval-report-v5.md` — GET 세부 역할 제한 + 완전 무상태 JWT + 컨테이너화 산출물
- `task-plan-refresh-rotation.md` / `eval-report-refresh-rotation.md` — Refresh token 회전+재사용
  탐지 산출물
- `ui-identity.md` — 참조 이미지 기반 UI 아이덴티티 스펙(색상/타이포/레이아웃/컴포넌트 규칙)
- `task-plan-frontend-react.md` / `eval-report-frontend-v1.md` — React 프론트엔드 마이그레이션
  1차 수직 슬라이스(로그인/셸/대시보드) 산출물
- `eval-report-frontend-v2.md` — React 프론트엔드 마이그레이션 2차(기준정보/영업/구매) 산출물
- `eval-report-frontend-v3.md` — React 프론트엔드 마이그레이션 3차(생산/재고) 산출물
- `eval-report-frontend-v4.md` — React 프론트엔드 마이그레이션 4차(회계/승인함/연동로그) 산출물
- `eval-report-frontend-v5.md` — React 프론트엔드 마이그레이션 5차(AI Agent/참고데이터, 전체 이관 완료) 산출물
- `eval-report-v8.md` — Docker 프론트엔드 포함, audit_log 연결, LOT 정합성 KPI, 세션 관리 산출물
- `task-plan-v9-full-menu-rollout.md` — 1.0 메뉴 구조 13개 모듈 전체 구현 로드맵(v9~v21 웨이브)
- `eval-report-v9.md` — 01.Sales Management 확장(가격정책/견적/판매계약/반품/서비스오더/채권/실적/손익/KPI) 산출물
- `eval-report-v10.md` — 02.SCM 신규(수요예측정확도/S&OP/공급계획/MPS/재고계획/공급위험관리/Control Tower) 산출물
- `eval-report-v11.md` — 03.Procurement 확장(공급업체평가/구매계약/PO구분/카테고리별구매/통관관리/구매실적/KPI) 산출물

## 프로토타입 v1~v2 완료 (2026-07-05)
Phase 1 Core 7모듈, PostgreSQL 이중지원(로컬 검증 완료), MES/WMS mock 연계, AI Agent 5종(Buyer/
Scheduler/Demand Planner/Quality Engineer/CFO Copilot), 다국적 샘플 데이터셋, 공장·창고 선택 UI까지
전부 구현 및 검증 완료. v1~v2 스코프로 정의했던 항목은 이걸로 마감한다.

## v3 진행 상황
- RBAC(역할 기반 접근 제어) — **완료**(2026-07-05). 세션 기반 로그인/역할별 트랜잭션 제어.
- WMS/QMS LOT·Serial 추적 — **완료**(2026-07-05). LOT FIFO 생성/소진, 선택적 시리얼, QMS 실시간 검사 등록.
- MES/WMS 웹훅 API Key 인증 — **완료**(2026-07-05). X-API-Key 헤더, source_system별 키 분리.
- AI Agent LLM 고도화 1단계 — **완료**(2026-07-05). 템플릿 기반 자연어 근거(`ai_narrative`) 추가,
  실제 LLM API 호출은 미포함(비용 없음).
- LOT ↔ inventory.qty 정합성 검증 — **완료**(2026-07-05). `GET /api/lots/reconciliation`, 재고 탭에
  점검 테이블 추가.
- GET 엔드포인트 인증 확장 — **완료**(2026-07-05). 로그인만 하면 역할 무관 전체 조회 가능.
- JWT 토큰 포맷 전환 — **완료**(2026-07-05). 세션 테이블 유지 + 표준 JWT 포맷(신규 의존성 없음).
- 시리얼 UI 고도화 — **완료**(2026-07-05). 출하 자동 SHIPPED 반영 + 수동 상태변경(불량/폐기) UI.
- 운영 인프라(마이그레이션+헬스체크/로깅+pytest+CI) — **완료**(2026-07-05). Alembic 마이그레이션 도구
  도입(기존 스키마와 동일하게 재현), `GET /health`, 표준 로깅, pytest 42개 테스트, GitHub Actions CI.
- GET 세부 역할 제한 + 완전 무상태 JWT + 컨테이너화 — **완료**(2026-07-05). 회계/CFO Copilot 조회를
  관리자 전용으로 좁힘, Access(30분·무상태)+Refresh(8시간·세션테이블) 이중 토큰 전환, 앱 Dockerfile+
  docker-compose 통합(`docker compose up`으로 앱+DB 한번에 기동). **사용자 로컬 환경에서
  `docker compose up --build` 실기동 후 `GET /health` 200 확인 완료**(eval-report-v5.md 참고).
- Refresh token 회전(rotation) + 재사용 탐지 — **완료**(2026-07-05). refresh 호출마다 토큰 회전,
  폐기된 토큰 재사용 시 해당 로그인의 전체 세션(family) 즉시 무효화 + 경고 로그. v5에서 남겨둔
  보안 절충을 메움.
- UI 아이덴티티 정의 + 페이지별 시안 — **완료**(2026-07-05). 참조 이미지 16종 분석 → `ui-identity.md`
  (색상/타이포/레이아웃 토큰), 인터랙티브 목업으로 12개 페이지 시안 제시.
- React 프론트엔드 마이그레이션 1차(로그인/셸/대시보드) — **완료**(2026-07-05). Vite+React+TS+
  Tailwind v4, 실 API 연동 검증(빌드 성공+API 계약 일치 확인). 브라우저 실기동 확인은 사용자 몫으로 남김.
- Docker 이미지에 프론트엔드 빌드 포함 — **완료**(2026-07-05). Node 멀티스테이지 빌드로 `frontend/dist`를
  이미지에 포함(`docker build` 자체는 샌드박스 제약으로 미실행, 사용자 로컬 확인 필요).
- 시리얼 상태변경/refresh 재사용 탐지 audit_log 연결 — **완료**(2026-07-05). 기존 미사용
  `audit_log` 테이블 활용, `GET /api/audit-log`(관리자 전용) 신규.
- LOT 정합성 자동 알림(대시보드 KPI 반영) — **완료**(2026-07-05). 온디맨드 조회 결과 개수를
  `GET /api/dashboard/kpi`에 상시 노출.
- 디바이스별 다중 세션 조회/개별 로그아웃 — **완료**(2026-07-05). `migrations/0003`으로
  `user_agent`/`last_seen_at` 추가, `GET /api/auth/sessions` + `POST /api/auth/sessions/{family_id}/logout`
  (소유권 검증 포함), topbar 세션 관리 Dialog. 상세는 `eval-report-v8.md` 참고.

## v9~ : 1.0 메뉴 구조 전체 구현 로드맵

`/Users/greeme/Claude/workspace/AX-ERP/1.0_AX_ERP_Menu_Structure.md`의 13개 모듈·153개
메뉴 항목을 전부 구현하기 위한 로드맵을 `task-plan-v9-full-menu-rollout.md`에 수립했다(사용자 승인
완료, 자동 순차 진행 중). 진행 순서: v9(01 Sales, 완료) → v10(02 SCM) → v11(03 Procurement) →
v12(04 Logistics) → v13(05 Production) → v14(06 Quality) → v15(07 R&D) → v16(08 FI) →
v17(09 Controlling) → v18(10 Marketing) → v19(11 Service) → v20(12 MDM 마무리) →
v21(13 Common/Platform 마무리). 각 웨이브는 additive 마이그레이션 + FastAPI 라우터 + React 페이지
확장 + pytest/tsc 검증 + eval-report 순서로 진행한다.

- **v9(01 Sales 확장) 완료**: 가격정책/견적(승인함 재사용→수주전환)/판매계약/반품(승인 시 재고복원)/
  서비스오더/채권조회/영업실적/손익분석(근사)/영업KPI. `eval-report-v9.md` 참고.
- **v10(02 SCM 신규) 완료**: 수요예측 정확도/S&OP/공급계획/MPS뷰/재고계획/공급위험관리/Control Tower
  — 전부 조회 전용, 신규 테이블 없음. 공급망 시뮬레이션은 이번 로드맵에서 제외. `eval-report-v10.md` 참고.
- **v11(03 Procurement 확장) 완료**: 공급업체평가(납기/품질/가격 점수+등급)/구매계약관리/외주·위탁구매
  구분(`purchase_order.po_type`)/원재료 등 카테고리별 구매(material_type 필터 뷰)/통관·수입관리(간이)/
  구매실적/구매KPI. `eval-report-v11.md` 참고.

## 다음 단계 (v9 후보)
- React 2~5차 + v8 신규 UI(세션 관리 Dialog, LOT 정합성 KPI 카드) 브라우저 실기동 확인
  (사용자 로컬에서 `npm run dev` + 로그인부터 전 탭 클릭 테스트)
- Docker 실빌드 검증 — 사용자 로컬에서 `docker compose up --build` 후 `/`가 React 앱을 서빙하는지,
  `GET /health` 200 확인
- audit_log 조회 화면(프론트) — 현재는 백엔드 API(`GET /api/audit-log`)만 있고 UI는 없음
- AI Agent LLM 고도화 2단계: 실제 LLM API(Anthropic 등) 연계 — 통합테스트/현업 검증 단계에서 필요시
- GET 세부 역할 제한을 회계/CFO 외 모듈로 확대할지 검토(실사용 피드백 기반)
- migrations/0003(세션 device 컬럼)의 PostgreSQL 실환경 검증 — 0002와 동일한 단순 ADD COLUMN 패턴이라
  호환성 위험은 낮게 평가하나 실제 PG 인스턴스로는 미검증
- nginx 리버스프록시/TLS, Kubernetes manifests, 이미지 레지스트리 CI 자동화 — 실운영 전환 규모에 따라
- 부하테스트, 외부 로그 수집(ELK 등) — 실운영 전환 규모에 따라 별도 검토
