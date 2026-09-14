# Task Plan v2 — PostgreSQL 전환 / MES·WMS 연계 / AI Agent

## 목표
v1(SQLite 단일 모놀리식)을 유지하면서 3개 축을 확장한다.
1. PostgreSQL도 선택적으로 지원 (SQLAlchemy 도입, `DATABASE_URL` 환경변수로 전환)
2. 실제 MES/WMS가 없는 상태에서 연계 아키텍처를 Mock 어댑터 + 시뮬레이터로 검증
3. AI Agent 5개 시나리오 중 AI Buyer(재발주 추천) + Production Scheduler(생산우선순위 추천) 2개를
   규칙기반(무료, LLM 미호출)으로 실제 동작하게 구현. 나머지 3개(수요예측/품질/CFO)는 설계만.

## 성공 기준 (측정 가능)
1. `DATABASE_URL` 미설정 시 기존과 동일하게 SQLite로 기동 (v1 회귀 테스트 재통과)
2. `DATABASE_URL=postgresql+psycopg2://...` 설정 시 동일 코드로 PostgreSQL 방언 DDL이 정상 생성됨
   (샌드박스에 실제 Postgres 서버가 없어 실제 접속 테스트는 불가 — DDL 컴파일 검증 + docker-compose 제공으로 사용자 로컬 검증 유도)
3. `simulate_mes_wms.py` 실행 시 MES 생산실적 이벤트 1건, WMS 입출고 이벤트 1건이 각각
   `integration_event_log`에 기록되고 재고/생산실적에 정상 반영됨
4. `GET /api/ai/buyer/recommendations` 가 재고 < 재발주점인 원자재에 대해 추천 PR 수량을 반환
5. `GET /api/ai/scheduler/recommendations` 가 오픈 생산오더를 자재가용성 기준으로 우선순위 정렬해 반환
6. 기존 v1 API/화면 동작에 회귀 없음

## DB 스키마 변경 (추가적, 기존 컬럼/테이블 변경 없음)
- `material`: `reorder_point`, `target_stock` 컬럼 추가 (AI Buyer용)
- 신규 테이블: `integration_event_log` (event_id, source_system, event_type, payload_json, status, received_at)

## 컴포넌트 구조
- `app/database.py` : SQLAlchemy 엔진 생성(`DATABASE_URL`), 방언별 스키마 파일 선택(`schema_sqlite.sql`/`schema_postgres.sql`), `run()` 헬퍼(포지셔널 `?` → named param 자동 변환)
- `app/schema_sqlite.sql`, `app/schema_postgres.sql` : 기존 schema.sql을 방언별로 분리
- `app/main.py` : 기존 sqlite3 API를 SQLAlchemy Connection 기반으로 전환(SQL 문자열은 최대한 유지, 커넥션/lastrowid 처리만 교체)
- `app/integrations.py` : MES/WMS 수신 Webhook 엔드포인트 + 이벤트 로그 기록
- `app/ai_agent.py` : AI Buyer / Scheduler 추천 로직(규칙기반)
- `simulate_mes_wms.py` : 실행 중인 서버에 Mock MES/WMS 이벤트를 전송하는 스크립트
- `docker-compose.yml` : 로컬 PostgreSQL 16 기동용 (사용자가 직접 검증할 때 사용)
- `static/index.html` : "연동 로그", "AI Agent" 탭 2개 추가

## 기존 코드 영향범위
- `app/main.py` : DB 커넥션/lastrowid 처리 부분 전면 수정 (SQL 로직 자체는 불변) — 회귀 테스트로 검증
- `app/database.py` : 전면 교체 (SQLAlchemy 기반)
- `app/schema.sql` → `schema_sqlite.sql`로 이름 변경(내용 동일), `schema_postgres.sql` 신규
- 기존 v1 문서(README/task-plan/eval-report)는 유지, v2 산출물은 별도 파일로 추가

## 거버넌스 원칙 (2.8 §12.2 준수)
AI Agent는 추천만 제공하고 자동 실행하지 않음. AI Buyer 추천을 실제 PR로 전환하려면
UI에서 "적용" 버튼을 눌러 기존 PR 생성 API를 사람이 명시적으로 호출해야 함(Human-in-the-loop).

## 미결 질문 / 알려진 제약
- 샌드박스에 root 권한/Docker가 없어 실제 PostgreSQL 서버 기동·접속 테스트는 이번 세션에서 불가.
  SQLAlchemy DDL 컴파일 검증과 SQLite 전체 회귀 테스트로 대체하며, 사용자가 로컬에서
  `docker-compose up -d` 후 `DATABASE_URL` 지정 시 최종 검증을 권장.
