# SESSION LOG (AX-ERP)

## 2026-07-05 | 프로토타입 v1 착수 | memory_updated: true
- 수행: /Users/greeme/Claude 루트 에이전트 체계 문서(CLAUDE.md, Harness_CLAUDE.md,
  consultingWizard_planner/EXECUTOR/evaluator_CLAUDE.md, Memory_CLAUDE.md) +
  hermes-cowork 메모리 체계(MEMORY.md/USER.md/SESSION_LOG.md/curator) 조사.
  AX-ERP 1.x/2.x 설계문서 조사 → 프로토타입 범위 확정.
- 사용자 결정: 스택=경량 Python(FastAPI+SQLite), 범위=Phase1 Core 7모듈.
- 산출물: prototype/ 폴더(FastAPI+SQLite ERP), memory/ 폴더(이 자기성장형 메모리 체계).
- 다음 액션: 프로토타입 실행 검증 → 사용자 피드백 반영 → v2(MES/WMS 연계 등) 논의.
- 검증 결과: E2E 3개 플로우(수주-출하-매출/PR-PO-입고-매입채무/생산오더-실적-재고) 전부 통과(eval-report.md, score 92/100). 재고 음수 은폐 버그 1건 발견 즉시 수정. 샌드박스 마운트 폴더의 SQLite I/O 이슈 대응해 init_db를 테이블 존재 기반 자동복구 로직으로 방어 처리.

## 2026-07-05 | v2 확장(PostgreSQL/MES·WMS/AI Agent) | memory_updated: true
- 사용자 결정: DB=SQLAlchemy 이중지원(SQLite 기본/Postgres 옵션), MES/WMS=Mock 어댑터+시뮬레이터, AI Agent=Buyer+Scheduler 2종 규칙기반.
- 구현: database.py를 SQLAlchemy 엔진 기반으로 전면 교체(run/insert_returning 헬퍼로 main.py 최소변경), schema_sqlite.sql/schema_postgres.sql 분리, helpers.py로 공통로직 분리(순환참조 방지), app/integrations.py(MES/WMS webhook), app/ai_agent.py(추천 API), simulate_mes_wms.py, docker-compose.yml, static/index.html에 "연동 로그"/"AI Agent" 탭 추가.
- 검증: v1 전체 회귀 재통과 + MES/WMS 시뮬레이터 실제 서버 기동 후 E2E 확인 + AI Buyer/Scheduler 추천 정확성 확인(eval-report-v2.md, score 88/100). PostgreSQL은 샌드박스에 root/Docker 권한이 없어 실제 접속 테스트 불가 — DDL 문법 검증만 완료, 사용자 로컬 docker-compose 최종검증 필요.
- 다음 액션: 사용자가 로컬에서 Postgres 접속 검증 → v3(수요예측/품질/CFO Copilot AI Agent, RBAC, LOT/Serial) 논의.

## 2026-07-05 | 로컬 서버 구동 확인 + 샘플 데이터셋 임포트 | memory_updated: true
- 로컬 서버 구동 확인 중 사용자 환경에 sqlalchemy 미설치로 서버가 죽어있던 것 발견 → run_server.command(의존성 자동설치 스크립트) 제공, 사용자가 재실행 후 Chrome으로 v2 화면(연동 로그/AI Agent 탭) 정상 렌더링 확인.
- prototype_dataset/(17종 CSV, 전자부품·소형가전 4개사/5공장/8창고 현실적 샘플) 사용 가능 여부 확인 → 코드기반 플랫 스키마라 그대로는 불가, 코드→ID 매핑 임포터 필요 판단.
- 스키마 additive 확장(company/plant/warehouse/customer/vendor에 code, sales/purchase/production_order에 external_no, production_result에 OEE 4종, 신규 참조테이블 6개: demand_forecast/quality_inspection/shipment/finance_summary_monthly/kpi_monthly/ai_recommendation_log) 후 seed.py를 CSV 임포터로 교체(데이터셋 없으면 기존 데모시드로 폴백).
- 창고명 한글 문자열 매칭 버그(다국적 데이터의 영문 창고명에서 깨짐) 발견 → warehouse_type 컬럼 기반으로 수정.
- 검증: 전 테이블 행수 CSV와 정확히 일치, FK 무결성 오류 없음, 기존 v1/v2 라이브 플로우 회귀 없음, 실제 브라우저에서 대시보드/기준정보/참고데이터 탭 실데이터 렌더링 확인(eval-report-dataset-import.md, score 90/100).
- 알려진 한계: 다중 공장 창고 선택 UI 미구현(항상 첫 매칭 창고 선택) — [[dataset-warehouse-limitation]] 참고.

## 2026-07-05 | 공장·창고 선택 UI 개선 | memory_updated: true
- 위 한계 해결: 출하/입고처리/생산실적입력 버튼 클릭 시 자동 첫매칭 대신 인라인 드롭다운(공장명·창고명 표시,
  확인/취소)으로 사용자가 창고를 직접 선택하도록 static/index.html 수정. 생산실적입력은 생산오더의
  plant_id를 기준으로 해당 공장 창고를 목록 최상단에 우선 정렬(다른 공장도 선택 가능하게 유지).
  백엔드 API는 이미 warehouse_id를 받고 있어 변경 없음(프론트엔드 전용 변경).
- 검증: node --check로 JS 문법 확인, 실제 브라우저(Chrome)에서 3개 플로우 모두 라이브 테스트—
  ① SO#214 출하를 Korea가 아닌 USA DC 창고로 선택해 정상 처리(재고 이동 이력에 USA DC 반영 확인),
  ② PO 입고처리 드롭다운 정상 렌더링, ③ MO#175 생산실적입력을 베트남 공장(오더의 실제 공장) 창고로
  자동 우선정렬된 채 정상 처리(재고 증가 확인). 기존 v1/v2/데이터셋 임포트 플로우 회귀 없음.
- 산출물: static/index.html(openWarehousePicker/openResultPicker 등 추가), README.md 갱신.
  [[dataset-warehouse-limitation]] 한계 해결됨.

## 2026-07-05 | AI Agent 나머지 3개 시나리오 구현 (수요예측/품질/CFO Copilot) | memory_updated: true
- 구현: app/ai_agent.py에 AI Demand Planner(GET .../demand-planner/recommendations, POST .../apply —
  demand_forecast 최근 3개월 평균 MAPE 10% 이상 품목의 재발주점/목표재고 조정 제안, 사람이 적용 버튼
  클릭 시 material 직접 갱신), AI Quality Engineer(GET .../quality/recommendations — 최근 6건 검사 중
  FAIL/CAPA 비율 기준 위험도, 조회전용), CFO Copilot(GET .../cfo-copilot/insights — 영업이익률 변화/
  현금흐름 괴리/공급리스크/라이브 AR·AP, 조회전용) 추가. index.html AI Agent 탭에 3개 섹션 추가.
- 판단: MAPE 임계치는 15%→10%로 재조정(실데이터 최대 12.1%라 15%면 추천 0건). Demand Planner apply는
  금액이동이 없는 계획 파라미터라 승인 워크플로 없이 즉시 반영(Buyer의 PR+승인 방식과 다름, 사람이
  버튼을 눌러야 하는 원칙은 동일). Quality Engineer는 CAPA 실행 테이블이 없어 조회전용으로 범위 한정.
- 검증: TestClient로 3개 엔드포인트 응답 확인 + apply 동작 확인(테스트 후 원복), 실브라우저에서 5개
  AI Agent 섹션 전부 라이브 렌더링 및 계획값 적용 버튼 실제 동작 확인(eval-report-ai-agent-v3.md, 91/100).
  기존 Buyer/Scheduler·전체 E2E 회귀 없음.
- 알려진 제약: Demand Planner는 적용 이력을 추적하지 않아 반복 클릭 시 계속 상향 조정됨(1회 적용 전제
  설계). CFO Copilot의 라이브 AR/AP는 데이터셋 임포트가 과거 거래를 소급 생성하지 않아 현재 0원(의도된
  동작). 남은 다음 단계: PostgreSQL 로컬 검증, RBAC 강화, WMS/QMS LOT·Serial, LLM 기반 추천 고도화.

## 2026-07-05 | PostgreSQL 로컬 검증 완료 — v1~v2 프로토타입 전체 완료 확정 | memory_updated: true
- 사용자 로컬 Mac(Docker 29.4.0, CLI 전용 설치라 request_access의 GUI앱 목록엔 안 잡힘)에서
  docker-compose 기반 PostgreSQL 16 검증 진행. verify_postgres.command(원클릭 스크립트) +
  verify_postgres.py(연결→스키마초기화→시드임포트→E2E 스모크 테스트) 작성해 제공.
- 발견/해결한 이슈 3건: ①호스트에 이미 네이티브 Postgres가 5432를 점유 중이라 컨테이너 접속이
  가로채임(`role erp does not exist`로 나타남) → docker-compose.yml 포트를 5433으로 변경해 해결.
  ②볼륨이 비어있을 때만 계정이 생성되는 Postgres 특성 때문에 재실행 시 계정 문제 반복 → 스크립트가
  매번 `docker compose down -v` 후 새로 띄우도록 수정. ③requirements.txt에 httpx 누락으로 최신
  Starlette TestClient가 임포트 실패 → httpx==0.27.2 추가.
- 결과: 최종 전체 PASS. 스키마/시드 행수가 SQLite 버전과 정확히 일치(company 4, plant 5, warehouse 8,
  material 15, sales_order 216, production_order 180, demand_forecast 60), E2E 스모크 테스트(SO 생성)
  통과. eval-report-postgres-verify.md(95/100) 작성.
- **판단: v2 eval부터 미검증으로 남아있던 마지막 조건이 충족되어, 프로토타입 v1~v2 범위는 이걸로
  전체 완료로 확정.** 컴퓨터유즈로 Finder 자동화를 시도했으나 사용자가 Chrome을 실시간으로 쓰고 있어
  포커스 충돌 발생 → 자동화 포기하고 사용자에게 직접 더블클릭 요청하는 방식으로 전환(과거 세션의
  "iScreen Shoter" 포커스 이슈와 동일한 교훈 재확인: 사용자가 화면을 실사용 중이면 자동화보다 직접 요청이 낫다).
  남은 항목(RBAC/LOT·Serial/LLM 고도화)은 애초 v1~v2 스코프 밖이라 v3 이후 과제로 이월.

## 2026-07-05 | v3 스택 전환 상담 + RBAC 구현 완료 | memory_updated: true
- 사용자가 v3부터 스택 전환(Spring Boot+PostgreSQL 표준설계 / Node.js+TS) 여부를 질문 →
  현재 스택(FastAPI) 유지를 권고(전환은 MVP 완성 후 "Enterprise ERP" 단계의 계획된 1회성
  포팅으로 미루는 게 리스크가 낮다는 논리, 원 설계문서와의 정합성/전환 트리거 기준을 로드맵
  테이블로 제시). 사용자가 현재 스택 유지 + RBAC부터 진행하기로 결정.
- RBAC 구현: 세션 테이블 기반 인증(신규 app/auth.py, hashlib.pbkdf2_hmac만 사용 — 신규 의존성
  없음). app_user.password_hash/session 테이블 추가(additive). 데모 계정 4개(관리자/영업담당/
  구매담당/생산담당, 비밀번호 공통 demo1234) seed.py에 추가. 상태변경 POST 14개 + AI Agent apply
  2개에 require_roles 게이팅 적용(관리자는 전 역할 겸용). GET은 이번 범위에서 인증 강제 안 함
  (명시적 비범위, 내부망 전제). 프론트엔드에 로그인 화면 + 역할별 폼/버튼 노출 로직 추가.
- 검증: TestClient로 로그인 성공/실패/401/403/E2E 회귀 전부 확인(임시 복사본에서 진행해 라이브
  DB 보호). 브라우저 라이브 테스트로 관리자/영업담당 로그인 후 역할별 UI 차이 확인.
- 버그 발견/수정: initNav()가 로그인마다 nav 버튤을 append만 해 재로그인 시 탭 중복 렌더링되는
  버그를 라이브 테스트 중 발견해 즉시 수정(nav.innerHTML="" 추가). /api/users가 password_hash를
  노출하던 것도 함께 수정.
- 스키마 변경으로 인해 사용자 로컬 erp.db 삭제 후 재시작 트리거 과정에서 서버가 일시 다운(터미널
  종료가 원인으로 추정) → 사용자가 run_server.command로 재기동, 정상 복구 확인.
- 산출물: task-plan-rbac.md/eval-report-rbac.md(92/100), README RBAC 섹션, app/auth.py 신규.
  v3 우선순위 1번(RBAC) 완료. 남은 v3~v4 후보: WMS/QMS LOT·Serial, MES 인증, AI LLM 고도화.

## 2026-07-05 | WMS/QMS LOT·Serial 추적 구현 완료 (v3 우선순위 2)
사용자가 "순차적으로 WMS/QMS LOT·Serial 추적, MES 인증(API Key/OAuth), AI Agent LLM 고도화
진행하자"고 지시 → 명시된 순서대로 첫 항목부터 진행.
- 설계: 기존 `inventory`(집계) 테이블과 `adjust_inventory()`는 그대로 두고, LOT을 병행 기록되는
  별도 레이어로 추가(Surgical Changes). 신규 테이블 `lot`/`lot_consumption`/`serial_number`
  (전부 additive), `quality_inspection.lot_id` 컬럼 추가. schema_sqlite.sql/schema_postgres.sql
  양쪽 다 반영하되, PostgreSQL은 FK 순방향 참조를 허용하지 않아 LOT 테이블 정의를
  quality_inspection보다 앞(섹션 08b)으로 옮겨 두 파일 구조를 통일.
- 신규 모듈 app/lot_tracking.py: generate_lot_no/create_lot/consume_lots_fifo/generate_serials
  헬퍼 + 조회 라우터(GET /api/lots, /api/lots/{id}/trace, /api/serials, /api/serials/{no}/trace)
  + QMS 실시간 등록(POST /api/quality/inspections, 생산담당+관리자 게이팅).
- 기존 흐름에 한 줄씩 추가(입고처리→RM LOT 생성, 생산실적입력→RM LOT FIFO 소진+FG LOT 생성+선택적
  시리얼, 출하→FG LOT FIFO 소진). MES/WMS mock 웹훅(integrations.py)도 동일하게 반영.
- 시리얼은 선택 기능(생산실적입력 시 "시리얼 생성" 체크박스, 1회 최대 500개 안전장치).
- "품질담당" 역할이 없어 QMS 등록은 생산담당+관리자로 게이팅(현실적 절충, README에 명시).
- 과거 임포트 재고는 LOT이 없어 소급 생성하지 않음 — FIFO 소진 시 가용 LOT 부족해도 에러 없이
  가능한 만큼만 처리(비범위, task-plan에 사전 명시).
- 프론트엔드: 재고 탭에 LOT/시리얼 조회 테이블 + "추적" 버튼, 생산 탭에 QMS 검사 등록 폼 추가.
- 검증: `/tmp` 임시 복사본에서 TestClient로 시드 데이터(FG-1001+BOM) 기준 입고→생산→출하 전체
  플로우 + LOT/시리얼/QMS API 9개 시나리오 전부 PASS, 기존 RBAC 401/403 회귀 없음도 재확인.
  JS 문법은 node --check로 검증. 사용자의 실제 라이브 erp.db는 스키마 변경으로 삭제 후 재시드
  트리거(RBAC 때와 동일 패턴) — 사용자가 서버 재기동 필요.
- 산출물: task-plan-lot-serial.md/eval-report-lot-serial.md(91/100), README LOT/Serial 섹션,
  app/lot_tracking.py 신규. v3 우선순위 2번 완료. 다음: MES 인증(API Key/OAuth).

## 2026-07-05 | MES/WMS 웹훅 API Key 인증 완료 (v3 우선순위 3)
- 신규 테이블 `integration_api_key`(additive). `X-API-Key` 헤더 + `source_system`(MES/WMS)별 키
  분리로 교차 사용 차단(MES 키로 WMS 엔드포인트 호출 불가). RBAC 세션 인증과는 별개의 system-to-
  system 공유키 방식(신규 의존성 없음).
- 데모 키 고정값(RBAC의 demo1234와 같은 취지): `mes-demo-key-please-rotate` / `wms-demo-key-
  please-rotate`. 세션 토큰과 동일하게 평문 저장(해시화 안 함 — 절충 명시).
- `GET /api/integrations/events`는 기존 RBAC 비범위 결정과 동일하게 계속 비인증 조회 가능.
- 작업 중 `simulate_mes_wms.py`가 이미 두 가지 이유로 깨져 있던 것을 발견해 함께 수정:
  (1) RBAC 도입 이후 생산오더/작업지시 생성 API가 역할 인증을 요구하는데 시뮬레이터에 로그인
  로직이 없었음 → 생산담당 데모 계정 로그인 추가. (2) 데이터셋 임포트(prototype_dataset) 사용 시
  창고명이 영어("Korea Factory 1 FG Warehouse")인데 시뮬레이터는 한글 부분일치("완제품"/"원자재")로
  찾고 있어 StopIteration 발생 → 기존 `warehouse_type` 컬럼 기반 매칭으로 수정.
- 검증: `/tmp` 임시 복사본에서 TestClient로 401(키 없음)/401(오답)/401(교차 source_system)/200(정답)
  전부 확인. 실제 uvicorn 백그라운드 기동이 이 세션의 샌드박스에서 반복적으로 exit 143(추정:
  타임아웃)으로 실패해, 동일 API 호출 시퀀스를 TestClient로 재현하는 방식으로 대체 검증하고 사용자
  로컬 환경에서 실제 스크립트 실행으로 최종 확인을 권장하는 것으로 문서화.
- 산출물: task-plan-mes-auth.md/eval-report-mes-auth.md(93/100), README MES/WMS 섹션 갱신.
  v3 우선순위 3번 완료. 다음: AI Agent LLM 고도화(범위 재확인 필요 — 외부 LLM 호출은 토큰비용 발생).

## 2026-07-05 | AI Agent LLM 고도화 1단계 완료 (v3 우선순위 4, 마지막)
- 외부 LLM 호출은 프로젝트의 "토큰 사용 최소화" 지침과 직접 충돌 가능성이 있고, 범위(자연어 근거
  보강 vs 추천 로직 자체 보강) 및 호출 방식(템플릿 vs 실시간 API)이 비용/의존성 측면에서 크게
  갈리는 결정이라 AskUserQuestion으로 사전 확인.
- 사용자 답변: "지금은 1번으로 하고, 통합테스트 및 현업 검증 단계에서 필요시 API 연계 진행하자"
  → 자연어 근거 문장만 보강(추천 대상/수치 로직은 규칙기반 유지), 템플릿 기반(실제 LLM API 미호출,
  토큰 비용 0)으로 확정.
- 신규 모듈 `app/llm_rationale.py`: narrate_buyer/scheduler/demand_planner/quality/cfo 5개 함수,
  표준 라이브러리 f-string만 사용(외부 의존성 없음). `app/ai_agent.py`의 각 추천/인사이트 딕셔너리에
  `ai_narrative` 필드를 additive로 추가 — 기존 `rationale`/`detail` 필드는 그대로 유지(회귀 없음).
- 프론트엔드: AI Agent 탭 5개 테이블에 "AI 설명" 컬럼 추가.
- 검증: `/tmp` 임시 복사본에서 TestClient로 5개 에이전트 전부 `ai_narrative` 정상 생성 확인(AI
  Buyer는 현재 시드 데이터에 재발주점 이하 품목이 없어 테스트 전용으로 재고를 0으로 조정해 추천
  발생 시나리오 강제 재현 — 데이터 의존적 상황이지 회귀 아님). `node --check`로 JS 문법 확인.
  스키마 변경 없어 사용자 라이브 DB 추가 조치 불필요.
- 산출물: task-plan-llm-narrative.md/eval-report-llm-narrative.md(94/100), README 갱신.
  **v3 우선순위 1~4(RBAC→LOT·Serial→MES인증→LLM고도화) 사용자가 지시한 순서대로 전부 완료.**
  다음 단계 후보(v4): 실제 LLM API 연계(통합테스트 단계), GET 엔드포인트 인증 확장/JWT 전환 검토.

## 2026-07-05 | v3 통합 재검증 + LOT ↔ inventory.qty 정합성 검증 로직 완료
- 사용자가 "다음 단계 가이드" 요청 → v4 후보 표(실제 LLM 연계/GET 인증확장/LOT정합성검증/시리얼UI/
  Spring Boot전환)로 답변. 사용자가 "지금 결과 확인하고 문제없으면 LOT 정합성 검증부터"로 확정.
- **1) v3 통합 재검증**: RBAC+LOT·Serial+MES인증+LLM고도화가 전부 반영된 현재 repo 상태를 fresh
  복사본에서 TestClient로 재검증 — RBAC 401/403, 입고→RM LOT, 생산실적→FG LOT+시리얼10건+RM
  FIFO소진, 출하→FG FIFO소진, QMS 등록/403, MES/WMS API Key 401/교차차단/200, AI Agent 5종
  ai_narrative+기존필드 유지, 프론트엔드 신규 UI 전부 포함 등 34개 항목 전부 PASS. 회귀 없음 확인.
- **2) LOT 정합성 검증 로직**: `GET /api/lots/reconciliation`(app/lot_tracking.py) 추가. 설계
  핵심 — 완전 일치를 기대하지 않음(과거 임포트 재고는 LOT이 없어 재고집계가 LOT 합계보다 항상 큼,
  이건 정상). 대신 "활성 LOT 합계가 재고집계를 초과하는 경우"만 실제 버그 신호(`consistent:false`,
  `untracked_qty<0`)로 판정 — LOT은 항상 실제 재고 이동에 곁들여 생성/소진되므로 이론상 집계를
  초과할 수 없고, 초과한다면 LOT 로직과 adjust_inventory() 호출이 어긋난 버그이기 때문.
- 재고 탭에 "LOT 정합성 점검" 테이블 추가(부정합 행은 "⚠ 부정합"으로 표시).
- 검증: TestClient로 정상 케이스(입고 후 consistent=True) + 버그 시뮬레이션 케이스(SQL로 LOT
  수량을 직접 조작해 재고집계 초과시켜 consistent=False 정확히 탐지) 둘 다 확인. node --check로 JS
  검증. 스키마 변경 없어 사용자 라이브 DB 추가 조치 불필요.
- 산출물: task-plan-lot-reconciliation.md/eval-report-lot-reconciliation.md(95/100), README 갱신.

## 2026-07-05 | GET 인증 확장 + JWT 전환 + 시리얼 UI 고도화 완료 (v4)
- 사용자가 "GET 인증 확장/JWT 전환, 시리얼 UI 고도화 진행한다" 요청. 두 항목 모두 여러 설계
  선택지가 있어(GET 인증 범위, JWT 완전전환 vs 포맷만, 시리얼 UI 자동/수동 범위) AskUserQuestion으로
  사전 확인 → 전부 추천안 채택: "로그인만 하면 전체 조회(역할무관)", "세션테이블 유지+토큰만 JWT
  포맷", "출하 자동반영+수동 상태변경(불량/폐기) UI".
- **GET 인증 확장**: main.py(19)/ai_agent.py(5)/reference_data.py(6)/lot_tracking.py(5)/
  integrations.py(1, GET /events) 총 36개 GET 엔드포인트에 `Depends(current_user)` 추가. `/`,
  `/static/*`만 예외(로그인 화면 자체는 봐야 하므로). 부수조치: simulate_mes_wms.py의 GET 호출
  (materials/plants/warehouses/events)도 이제 401 나므로 auth_headers 추가.
- **JWT 전환**: app/auth.py에 표준 JWT(header.payload.signature, HMAC-SHA256)를 hmac/base64/json
  표준 라이브러리만으로 자체 구현(`_jwt_encode`/`_jwt_verify`, 신규 의존성 없음). 세션 테이블은
  그대로 유지 — current_user()는 ① JWT 서명 검증(위조 토큰을 DB 조회 전에 401) ② 세션 테이블 대조
  (로그아웃 즉시무효화/만료는 여전히 DB 기준) 2단계로 검증. `JWT_SECRET` 환경변수로 서명키 교체
  가능(기본값은 개발용 고정 문자열). payload에 sub/iat/exp/jti 클레임 — exp는 세션 테이블
  expires_at과 동일 시각에서 계산해 두 값이 어긋나지 않게 함.
- **시리얼 UI 고도화**: `consume_lots_fifo()`에 `mark_serials_shipped` 파라미터 추가, 출하
  (create_delivery)에서만 True로 호출 — 소진된 LOT의 IN_STOCK 시리얼을 생성순(serial_id ASC)으로
  소진수량만큼 SHIPPED 자동반영(생산 자재소요 등 다른 소진에는 적용 안 함, 의도적 구분). 신규
  `POST /api/serials/{serial_no}/status`(IN_STOCK/SHIPPED/DEFECTIVE/SCRAPPED, 생산담당+관리자
  게이팅 — QMS 등록과 동일한 절충)로 수동 변경. 재고 탭 시리얼 테이블에 상태 드롭다운+변경 버튼
  추가(생산담당/관리자만 노출).
- 검증: `/tmp` 임시 복사본에서 TestClient로 26개 항목(로그인 4계정, GET/POST 인증, JWT 위조/변조
  토큰 차단, 구매→입고→LOT, 생산→FG LOT+시리얼8건→RM소진, 출하→FG LOT소진+시리얼3건 자동SHIPPED,
  시리얼 수동변경+권한, QMS등록, LOT정합성, MES API Key, AI Agent narrative, 프론트엔드 신규요소)
  전부 PASS 확인. node --check로 JS 검증. 스키마 변경 없음(토큰 문자열 포맷/애플리케이션 로직만
  변경) — 사용자 라이브 DB 추가 조치 불필요.
- 산출물: task-plan-get-auth.md/task-plan-jwt.md/task-plan-serial-ui.md/
  eval-report-v4-auth-serial.md(93/100), README 갱신.

## 2026-07-05 | 운영 인프라 MVP 완료 (마이그레이션/헬스체크·로깅/pytest/CI) | memory_updated: true
- 사용자가 "현단계 마무리, 다음 상세화 단계 제안" 요청 → v4 마무리 정리 후 다음 후보(운영 인프라 /
  실제 LLM 연계 / GET 세부권한 등) 제시. 사용자가 "운영 인프라(특히 마이그레이션 도구) 먼저 진행"으로
  확정. 마이그레이션 도구 선택(Alembic 추천 vs 직접 스크립트)과 이번 작업 범위(마이그레이션만 vs
  인프라 트랙 전체)를 AskUserQuestion으로 확인 → 둘 다 추천안: Alembic 도입 + 마이그레이션+CI/CD+
  헬스체크/로깅 전체를 한 번에 진행.
- **Alembic 도입**: 이 프로젝트 최초의 신규 런타임 의존성(요청서에 명시된 "가급적 신규 의존성 없이"
  원칙의 명시적 예외 — 사용자 사전 확인). ORM 모델이 없는 raw-SQL 프로젝트라 autogenerate는 애초에
  불가능하다고 판단 → `migrations/versions/`에 전부 손으로 `op.execute()` raw SQL만 작성하는 방식으로
  설계. `0001_initial_schema.py`는 기존 `schema_sqlite.sql`/`schema_postgres.sql`을 그대로 실행해
  Alembic 도입 전/후 스키마가 바이트 단위로 동일하도록 맞춤. `app/database.py`의 `init_db()`를
  3분기 자동판단으로 재작성: ①완전 신규 DB→`alembic upgrade head` ②Alembic 도입 이전에 만들어진
  기존 DB(테이블은 있으나 `alembic_version` 없음, 즉 사용자의 현재 라이브 erp.db 같은 케이스)→
  `alembic stamp head`로 데이터 손실 없이 "이미 head"라고 표시만 함 ③이미 추적 중인 DB→
  `alembic upgrade head`.
- **3가지 시나리오로 직접 검증**: 신규 DB(43개 테이블 정상 생성), legacy DB(더미 데이터 삽입 후
  stamp 실행 — 데이터/테이블 전부 보존 확인), 추가 리비전 적용(데모 컬럼 추가 마이그레이션을 legacy→
  tracked DB에 적용해 무손실 스키마 변경 확인, 검증 후 데모 리비전 파일은 삭제). **이걸로 "스키마
  바뀔 때마다 erp.db 삭제" 문제가 실제로 해결됨을 증명** — 앞선 RBAC/LOT·Serial 단계에서 반복됐던
  "스키마 변경 시 라이브 DB 삭제 후 재기동" 패턴이 이번 단계부터는 더 이상 필요 없음.
- **헬스체크/로깅**: `GET /health`(비인증, DB 연결까지 확인) 추가 — GET 인증 확장(v4)의 명시적 예외.
  표준 라이브러리 `logging`으로 서버 기동/마이그레이션/시드적재 이벤트 기록(신규 의존성 없음).
- **pytest 스위트 정식화**: 그동안 이 세션 전체에서 `/tmp`에 임시로 짜서 쓰고 버렸던 검증 스크립트들을
  `tests/`에 정식 pytest로 승격 — `conftest.py`에 세션스코프 fixture(client/tokens 4계정/plant_id/
  warehouse_id/rm_lot/fg_lot_with_serials/db_path) 구성, 8개 테스트 파일(auth_rbac/jwt/lot_serial/
  lot_reconciliation/mes_wms_auth/ai_agent/serial_status/health) 작성. 총 42개 테스트 전부 PASS.
  실 개발용 `app/erp.db`는 건드리지 않고 `conftest.py`가 `DATABASE_URL`을 임시 SQLite 파일로 오버라이드
  (app.* 모듈 임포트 전에 설정해야 함에 주의). `requirements-dev.txt`로 pytest를 런타임 의존성과 분리.
  작업 중 발견한 사소한 버그: `fg_lot_with_serials` fixture가 `lot["qty"]`를 기대했으나 work-order
  results 응답의 `lot`은 `create_lot()`의 `{lot_id, lot_no}`만 담아 KeyError 발생 → 테스트를
  `/lots/{id}/trace`로 qty를 재조회하도록 수정(앱 코드는 건드리지 않음, 테스트 쪽 가정 오류였음).
- **CI/CD**: `.github/workflows/ci.yml` — push/PR 시 `requirements-dev.txt` 설치 후 `pytest -q` 자동 실행.
- 비범위(명시적 제외): 컨테이너화(Docker/K8s), 부하테스트, 외부 로그 수집(ELK 등), lint/ruff CI 스텝.
- 산출물: task-plan-mvp-infra.md/eval-report-mvp-infra.md(95/100), alembic.ini, migrations/ 디렉토리,
  tests/ 디렉토리 8개 파일, requirements-dev.txt, .github/workflows/ci.yml, README 운영 인프라 섹션 신규.
  다음 단계 후보(v5): 실제 LLM API 연계, GET 세부 역할별 제한, 완전 무상태 JWT, LOT 정합성 자동알림,
  시리얼 감사로그, 컨테이너화/부하테스트/외부 로그수집.

## 2026-07-05 | v5 완료 (GET 세부 역할 제한 + 완전 무상태 JWT + 컨테이너화) | memory_updated: true
- 사용자가 "GET 세부 역할별 제한, 완전 무상태 JWT, 컨테이너화 진행해" 요청 — 3개 항목 모두 여러
  설계 선택지가 있어 AskUserQuestion으로 사전 확인 → 전부 추천안 채택: "민감 모듈만 GET 제한",
  "Access+Refresh 이중 토큰", "앱 Dockerfile + docker-compose 통합".
- **GET 세부 역할 제한**: 회계 전표(`GET /api/accounting/documents`, `/api/accounting/documents/{id}`),
  계정과목(`GET /api/gl-accounts`), CFO Copilot(`GET /api/ai/cfo-copilot/insights`) 4개만
  `current_user`→`require_roles("관리자")`로 좁힘. 그 외 모듈(자재/재고/영업/구매/생산/LOT 등)은
  v4와 동일하게 로그인만 하면 전체 조회 유지 — "실사용 피드백 없이 미리 잠그면 대시보드/AI Agent의
  교차조회 UX를 해칠 수 있다"는 사용자 판단. 프론트엔드: 회계 nav 탭을 비관리자에게 아예 숨기고,
  AI Agent 탭의 CFO Copilot 섹션은 비관리자일 때 API 호출 자체를 생략(불필요한 403 방지).
- **완전 무상태 JWT (Access+Refresh)**: `app/auth.py` 전면 재작성. Access token(JWT, TTL 30분)의
  payload에 `sub`/`name`/`email`/`roles`를 전부 담아 `current_user()`가 **DB를 전혀 조회하지 않고**
  서명+만료만 검증 — 매 요청 완전 무상태로 전환. Refresh token은 기존 `session` 테이블을 그대로
  재사용(스키마 변경 없음 — token/user_id/expires_at 컬럼의 의미만 "refresh 저장용"으로 바뀜), TTL
  8시간, `POST /api/auth/refresh` 신규 엔드포인트로 재발급(회전은 안 함, 단순성 우선 절충). 로그인
  응답 포맷을 `{token}`→`{access_token,refresh_token,user}`로 변경(배포 전 프로토타입이라 하위호환
  없이 프론트/테스트/시뮬레이터 전부 함께 갱신). 로그아웃은 refresh token만 즉시 삭제(재발급 차단) —
  **단, 이미 발급된 access token은 자연 만료(최대 30분)까지 여전히 유효**하다는 게 완전 무상태화의
  의도된 트레이드오프(AskUserQuestion에서 사용자가 인지하고 선택, TTL을 짧게 유지해 창을 최소화).
  프론트 `api()` 헬퍼가 401 응답 시 자동으로 refresh를 시도한 뒤 원요청을 1회 재시도하도록 수정,
  `erp_token` 단일 localStorage 키를 `erp_access_token`/`erp_refresh_token`으로 분리.
- **컨테이너화**: `Dockerfile`(단일 스테이지, `python:3.11-slim`, `requirements.txt`만 설치 —
  psycopg2-binary라 libpq-dev 등 빌드 의존성 불필요) 신규 작성. `docker-compose.yml`에 `app` 서비스
  추가 — `postgres`에 `pg_isready` 헬스체크를 붙이고 `app`이 그게 healthy할 때까지 기다리도록
  (`depends_on.condition: service_healthy`), `DATABASE_URL`은 compose 내부 네트워크 주소로 자동
  설정, `app` 자체 헬스체크는 이미 만들어둔 `GET /health`를 그대로 재활용. `.dockerignore` 추가.
  이 세션 샌드박스에는 Docker 데몬이 없어 `docker compose up`을 직접 실행하지 못함 → 대신 YAML 문법
  검증 + Dockerfile의 모든 COPY 경로 존재 확인 + **깨끗한 venv에 `requirements.txt`(Dockerfile과
  동일한 런타임 의존성만, pytest 등 dev 의존성 제외)만 설치한 뒤 앱을 실제로 기동해 `/health`와
  로그인이 정상 동작함을 확인**하는 방식으로 간접 검증(이는 이미지 내부 환경과 동일한 조건이라
  컨테이너 기동 성공을 강하게 시사) — 사용자 로컬에서 `docker compose up --build` 최종 확인 권장
  (PostgreSQL 로컬검증 때와 동일 패턴).
- 검증: `tests/`에 신규 9개(GET 세부제한 403/200 5개, JWT refresh 발급/거부/로그아웃 트레이드오프
  증명 4개) 추가해 전체 51개 pytest 전부 PASS(fresh `/tmp` 복사본, 회귀 없음). `node --check`로
  프론트 JS 문법 확인.
- 산출물: task-plan-v5.md/eval-report-v5.md, Dockerfile, .dockerignore, docker-compose.yml 갱신,
  app/auth.py 전면 재작성, README RBAC/컨테이너화 섹션 갱신.
  다음 단계 후보(v6): 실제 LLM API 연계, GET 세부제한 확대 검토, refresh token 회전/다중세션 관리,
  nginx 리버스프록시/TLS, Kubernetes manifests, 부하테스트/외부 로그수집.

## 2026-07-05 | v5 컨테이너화 사용자 로컬 검증 완료
- 사용자가 로컬에서 `docker compose up --build`로 앱+PostgreSQL 컨테이너를 실제 기동한 뒤
  `http://localhost:8000/health`를 호출해 `{"status":"ok","db":"ok"}` 확인. `postgres` healthcheck
  (`pg_isready`) 통과 후 `app`이 기동되는 `depends_on` 체인, 컨테이너 내부 `DATABASE_URL`(compose
  네트워크 주소) 연결, `GET /health`의 DB 연결 확인 로직까지 실제 환경에서 전부 정상 동작 확인 —
  PostgreSQL 로컬검증(v2) 때와 동일한 패턴으로 v5 컨테이너화의 마지막 불확실성 해소.
- 산출물: eval-report-v5.md 점수 90→96/100 갱신(컨테이너 실기동 확인 반영), README/MEMORY.md 갱신.
  이걸로 v5(GET 세부 역할 제한 + 완전 무상태 JWT + 컨테이너화) 완전히 마감.

## 2026-07-05 | v6 완료 (Refresh Token 회전 + 재사용 탐지) | memory_updated: true
- 사용자가 v6 후보 표에서 "Refresh token 회전(rotation) + 탈취 탐지" 항목을 지목해 진행 요청.
  이 항목은 v5에서 "회전은 안 함(단순성 우선)"으로 명시적으로 미뤄뒀던 보안 절충이었음.
- **회전(Rotation)**: `app/auth.py`에 `rotate_tokens()` 신규 — `POST /api/auth/refresh` 호출마다
  새 access_token+refresh_token을 발급하고, 기존 refresh_token은 `rotated_at`을 찍어 폐기(1회용으로
  전환). `create_refresh_token()`에 `family_id`/`expires_at` 선택 인자를 추가해, 회전 시에는 같은
  family_id·고정 만료시각(로그인 시점 기준 8시간, 연장 안 됨)을 유지하도록 함.
- **재사용(탈취) 탐지**: 이미 `rotated_at`이 찍힌(=이미 한 번 쓰여 폐기된) refresh_token이 다시
  제시되면 `RefreshTokenReuseDetected` 예외를 던지고 해당 `family_id`에 속한 세션을 전부 삭제 —
  정상 클라이언트는 항상 최신 토큰만 갖고 있으므로, 오래된 토큰의 재등장은 탈취 신호로 간주하는
  표준 OAuth2 refresh rotation reuse-detection 패턴. `main.py`의 refresh 엔드포인트가 이 예외를
  캐치해 `logging.warning()` 기록 + 401(탈취 의심 메시지) 반환. `audit_log` 테이블(스키마에는 이미
  있지만 여태 앱에서 한 번도 안 쓰인 미사용 테이블)에는 연결하지 않음 — 앱 전체 감사로그 연결은
  범위가 훨씬 커서 별도 과제로 명시적으로 미룸(이번엔 표준 logging만 사용, 신규 의존성 없음).
- **스키마 변경**: `session` 테이블에 `family_id`/`rotated_at` 컬럼 추가
  (`migrations/versions/0002_session_rotation.py`). **중요한 설계 규칙을 재확인/재확립**:
  `schema_sqlite.sql`/`schema_postgres.sql`은 절대 건드리지 않았다 — `0001_initial_schema.py`가 이
  파일들을 마이그레이션 *실행 시점*에 동적으로 읽어 실행하기 때문에(마이그레이션 파일 안에 SQL이
  박제되어 있는 게 아님), 만약 스키마 파일을 직접 고치면 신규 설치에서는 0001이 이미 새 컬럼을 만든
  뒤 0002가 같은 컬럼을 또 추가하려다 "duplicate column" 오류가 난다. **v4(Alembic 도입) 이후
  스키마 변경은 반드시 번호 붙은 마이그레이션 파일에만 남겨야 하고, schema_*.sql은 다시 건드리면
  안 된다**는 규칙을 이번에 처음으로 실전 적용하며 명확히 문서화함(향후 스키마 변경 시 반드시
  참고할 것).
- 기존(0002 이전) 세션 행은 `family_id`를 자기 `token` 값으로 백필해 서로 다른 family로 분리했다
  (전부 빈 문자열로 두면 모든 레거시 세션이 하나의 family로 묶여, 한 세션의 재사용 탐지가 무관한
  다른 사용자 세션까지 통째로 무효화하는 사고가 날 뻔했음 — 설계 단계에서 미리 발견해 회피).
- **로그아웃 의미 확장**: 기존엔 토큰 1개만 삭제했으나, 이제 `delete_refresh_token()`이 family
  전체를 삭제하도록 변경 — 로그아웃은 그 로그인에서 파생된 모든 토큰을 무효화하는 게 자연스러운 의미.
- **프론트엔드**: `tryRefreshToken()`이 이제 refresh 응답의 새 `refresh_token`으로 반드시 교체
  저장하도록 수정(회전 반영 안 하면 다음 refresh부터 전부 401).
- 검증: `tests/test_jwt.py`에 신규 5개 추가(회전 시 새 refresh_token 발급, 예전 토큰 재사용 거부,
  **재사용 탐지가 아직 안 쓴 최신 토큰까지 함께 무효화함을 직접 증명**, 로그아웃의 family 전체
  무효화). 전체 pytest 55개 전부 PASS. 추가로 마이그레이션 자체를 실제로 실행하는 ad-hoc 검증
  스크립트로 "0001까지만 적용된 DB에 레거시 세션 2건을 직접 삽입 → 0002까지 업그레이드 → 서로 다른
  family로 정상 격리됨"을 확인(MVP 인프라 단계 때와 동일한 검증 방식). `node --check`로 프론트 JS
  문법 확인.
- 산출물: task-plan-refresh-rotation.md/eval-report-refresh-rotation.md(94/100), migrations/versions/
  0002_session_rotation.py, app/auth.py·main.py·static/index.html 수정, README RBAC 섹션 갱신.
  다음 단계 후보(v7): 실제 LLM API 연계, 디바이스별 세션 관리 UI, audit_log 연동, nginx/K8s,
  부하테스트/외부 로그수집.

## 2026-07-07 | Sub-Agent 체계 재확인 + Hermes 폐쇄형 학습 루프 적용 | memory_updated: true
- 사용자 지시: "/Users/greeme/Claude 폴더의 md 읽어서 Sub-agent 구성" + "hermes-cowork 지침 읽고
  closed-loop 학습 루프 적용(필요시 파일을 프로젝트 파일로 복사)" — 두 항목만 수행 후 다음 지시 대기.
- `/Users/greeme/Claude` 최상위는 보호 경로(`Scheduled`) 충돌로 재차 마운트 불가 확인. 이미 이
  프로젝트 루트에 존재하는 5개 파일(Harness_CLAUDE.md, consultingWizard_planner/EXECUTOR/
  evaluator_CLAUDE.md, Memory_CLAUDE.md — 2026-07-05 최초 조사분과 동일)을 유효한 소스로 재확인.
- hermes-cowork(MEMORY.md/USER.md/SESSION_LOG.md/SKILLS_USAGE.json/curator/SKILL.md/
  CLAUDE_HERMES_ADDON.md) 재독. 하드 문자한도(2,200/1,375자) 방식은 이 프로젝트 memory/MEMORY.md가
  이미 훨씬 큰 규모라 그대로 적용 불가 — 파일을 복사하지 않고 경로만 이 프로젝트 것으로 매핑해
  메커니즘(자동 저장 트리거/세션 로그/스킬 추적/curator 주기)만 CLAUDE.md에 추가.
- 산출물: `CLAUDE.md`에 "Sub-Agent 체계" + "Hermes 폐쇄형 학습 루프" 섹션 추가(기존 내용 무변경),
  `memory/SKILLS_USAGE.json` 신규 생성(turn_counter=0부터 시작).
- 다음 액션: 사용자 다음 지시 대기(v11 Procurement 확장 등 재개 여부 포함).

## 2026-07-07 | v11(03 Procurement Management 확장) 완료 | memory_updated: true
- 사용자 지시: "v11 진행하자" — task-plan-v9-full-menu-rollout.md §3 v11 스코프대로 진행.
- 마이그레이션 0005(vendor_evaluation/purchase_contract/import_customs_record 신규 테이블 +
  purchase_order.po_type 컬럼) + 신규 라우터 app/procurement_ext.py(공급업체평가/구매계약/
  카테고리별구매/통관관리/구매실적/구매KPI) + main.py의 create_po()에 po_type 파라미터 1개 추가.
- 프론트: ProcurementPage.tsx를 탭 6개로 확장, lib/types.ts에 v11 타입 7종 추가.
- 검증: 신규 pytest 12개 추가, 기존81+신규12=93개 전부 PASS, tsc -b 통과.
- 산출물: eval-report-v11.md(91/100), README/task-plan-v9-full-menu-rollout.md §6 갱신.
- 다음 액션: 사용자 지시 시 v12(04 Logistics Management 확장) 진행.

## 2026-07-11 — 로컬 서버 구동 검증
- Desktop Commander로 사용자 Mac에서 prototype/run_server.command 직접 실행 성공 (venv 재사용, 프론트 빌드 260ms, uvicorn 기동)
- /health {"status":"ok","db":"ok"}, 대시보드·구매 탭(v11: 공급업체평가/구매계약/카테고리별구매/통관관리/구매분석) 렌더링 확인, 콘솔 에러 없음
- 다음 액션: 신규 탭 CRUD 기능 테스트(평가 등록, 통관 기록 등록 등)

## 2026-07-11 — v11 신규 탭 CRUD 검증 (브라우저 자동화)
- 공급업체평가: Korea PCB Co. 90/85/80 등록 → 종합 85·등급 A·이력 반영 OK
- 구매계약: Japan Motor Works 2026-07-11~2027-07-10 등록 → ACTIVE 목록 반영 OK
- 카테고리별 구매: RM 519,676개 / ₩2,208,256,550 / 264건 집계 표시 OK
- 통관관리: PO 264 + 신고번호 등록 → PENDING → CLEARED 상태 변경 OK
- 발견 이슈(수정 후보): ① SPA 딥링크/새로고침 시 404 (FastAPI fallback 라우트 없음) ② 통관 PO 번호 입력란이 숫자 ID만 허용, PO-2026-XXXXX 입력 시 "필수 항목 누락: po_id" ③ 평가일이 UTC 기준으로 하루 이전 표시

## 2026-07-11 — 검증 이슈 3건 수정 완료
- ① SPA fallback: app/main.py 말미에 catch-all GET 라우트 추가(api/assets/health 제외) → /procurement 직접 접근 정상
- ② 통관 PO 입력: 백엔드가 po_no(external_no) 조회 지원 + 프론트가 숫자/원본번호 자동 판별 + placeholder 개선 → PO-2026-00263 등록 성공
- ③ 날짜 UTC: vendor_evaluation.eval_date, import_customs_record.customs_date INSERT 시 서버 로컬 date.today() 명시 → 신규 평가 2026-07-11 정상 표시
- pytest 93건 통과, 프론트 재빌드·서버 재기동·브라우저 재검증 완료

## 2026-07-11 — v12 물류 확장 완료
- 마이그레이션 0006 + app/logistics.py(17 API) + LogisticsPage(7탭) + 테스트 18개(111/111 PASS)
- 브라우저 E2E: /logistics 딥링크, 배차 등록, 물류비 정산→회계전표 생성 확인
- eval-report-v12.md 92/100 PASS. 다음 액션: v13 생산 확장

## 2026-07-11 — v13 생산 확장 완료
- 0007 마이그레이션 + production_ext.py(MRP/외주/재작업/생산마감/OEE/Dashboard) + ProductionPage 7탭
- 테스트 126/126 PASS, 브라우저 검증 완료, eval-report-v13.md 92/100
- 다음 액션: v14 품질 확장(검사기준/SPC/8D/CAPA)

## 2026-07-11 — v14 품질 확장 완료
- 0008 마이그레이션 + quality_ext.py(검사기준/SPC/부적합/8D/클레임/CAPA) + QualityPage 7탭
- 테스트 140/140 PASS, SPC 브라우저 실계산 확인, eval-report-v14.md 91/100
- 다음 액션: v15 R&D(BOM 트리/ECO·ECR), 이월: 시드 inspection_type 정규화
