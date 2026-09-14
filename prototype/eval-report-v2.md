# Evaluation Report — v2 (PostgreSQL 전환 / MES·WMS 연계 / AI Agent)

```json
{
  "pass": true,
  "score": 88,
  "independence_check": {"existing_files_modified": ["app/main.py", "app/database.py", "app/seed.py", "static/index.html", "requirements.txt"], "db_schema_changed": true},
  "failures": [],
  "harness_update_needed": false
}
```

독립성 체크(existing_files_modified)는 v1 기준으로는 위배처럼 보이지만, task-plan-v2.md에
명시한 대로 이번 태스크 자체가 "DB 커넥션 계층 전환"이라 기존 파일 수정이 계획된 범위였음
(신규 기능은 helpers.py/integrations.py/ai_agent.py로 분리해 신규 파일에 담음). DB 스키마 변경도
`material.reorder_point/target_stock` 컬럼 추가와 `integration_event_log` 테이블 추가로,
기존 컬럼/테이블 변경 없는 additive 변경. score 88점은 실제 PostgreSQL 서버 미검증(샌드박스 제약)을 반영해 v1(92점)보다 낮게 책정.

## 성공 기준 대비 결과 (task-plan-v2.md 기준)
1. `DATABASE_URL` 미설정 시 SQLite로 기존과 동일 기동 — **PASS** (v1 전체 플로우 회귀 재통과)
2. PostgreSQL 방언 DDL 생성 — **PARTIAL PASS**: 샌드박스에 root/Docker 권한이 없어 실제 Postgres
   서버 기동·접속 테스트는 불가. 대신 `schema_postgres.sql` 31개 문장 괄호/구조 검증과
   `create_engine("postgresql+psycopg2://...")` 드라이버 파싱을 통과 확인. **사용자가 로컬에서
   `docker-compose up -d` 후 `DATABASE_URL` 지정해 최종 접속 검증을 권장**.
3. `simulate_mes_wms.py` 실행 → MES/WMS 이벤트 각 1건이 `integration_event_log`에 기록되고
   재고/생산실적 반영 — **PASS** (실제 uvicorn 서버 기동 후 스크립트로 직접 검증)
4. AI Buyer 추천(재고<재발주점) — **PASS** (RM-001 재고 15 < 재발주점 30 → 추천 135 발주,
   PR 생성 적용까지 확인)
5. AI Scheduler 우선순위(자재가용성) — **PASS** (feasible 오더 1순위, shortage 상세 포함
   blocked 오더 2순위로 정렬 확인)
6. v1 API/화면 회귀 없음 — **PASS**

## 발견 이슈 및 조치
- 없음 (신규 버그 미발견). v1에서 이미 수정된 재고음수 은폐 버그, DB 자동복구 로직은 유지됨.

## 독립성/거버넌스 체크
- AI Agent는 추천 API(`/recommendations`)와 실행 API(`/apply`)를 분리 — 추천만으로는 어떤 데이터도
  변경되지 않고, PR 생성 등 실제 반영은 사람이 명시적으로 호출해야 함(Human-in-the-loop, 2.8 §12.2 준수)
- MES/WMS 연계는 Mock이므로 실제 시스템 연동 시 `app/integrations.py`의 두 엔드포인트 URL/인증만
  교체하면 되도록 어댑터 경계를 명확히 분리

## 남은 한계
- 실제 PostgreSQL 서버 접속 검증 미완료(샌드박스 제약) — 사용자 로컬 docker-compose 검증 필요
- AI Agent 5개 시나리오 중 3개(수요예측/품질/CFO Copilot)는 미구현 (task-plan-v2.md에 설계만 기록)
- MES/WMS 인증(API Key 등) 미구현 — 프로토타입 수준이라 인증 없이 오픈 엔드포인트
