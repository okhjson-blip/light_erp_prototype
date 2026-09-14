# Evaluation Report — LOT ↔ inventory.qty 정합성 검증 로직 (+ v3 통합 재검증)

```json
{
  "pass": true,
  "score": 95,
  "independence_check": {
    "existing_files_modified": ["app/lot_tracking.py", "static/index.html", "README.md"],
    "new_files": ["task-plan-lot-reconciliation.md"],
    "db_schema_changed": false
  },
  "failures": [],
  "harness_update_needed": false
}
```

## 1) v3 통합 재검증 (RBAC + LOT·Serial + MES 인증 + LLM 고도화)
이번 작업 전, 현재 repo 상태를 fresh 복사본에서 TestClient로 한 번에 재검증했다. 34개 항목 전부
PASS — RBAC 401/403, 입고→RM LOT, 생산실적→FG LOT+시리얼10건+RM FIFO소진, 출하→FG FIFO소진,
QMS 등록/403, MES/WMS API Key 401/교차차단/200, GET 이벤트로그 비인증 유지, AI Agent 5종
ai_narrative 생성+기존 rationale/detail 필드 유지, 프론트엔드 신규 UI 요소 전부 포함 확인.
**회귀 없음 — v3 전체 정상 동작 확인.**

## 2) LOT 정합성 검증 로직
task-plan-lot-reconciliation.md에 명시한 범위(완전 일치가 아닌 "LOT 합계 > 재고집계"만 실제
버그로 판정) 그대로 구현됨. 스키마 변경 없음.

### 성공 기준 대비 결과
1. 정상 상태에서 모든 행 `consistent: true` — **PASS** (입고 500 → active_lot_qty=500,
   inventory_qty=7065(과거 임포트분 포함), untracked_qty=6565로 정상 판정)
2. 활성 LOT 합계를 인위적으로 집계값 초과하도록 조작 시 해당 행만 `consistent: false`,
   `untracked_qty < 0` 탐지 — **PASS** (동일 material/warehouse에 +10000 조작 →
   active_lot_qty=10500 > inventory_qty=7065 → untracked_qty=-3435, consistent=False로 정확히 탐지)
3. 재고 탭에 "LOT 정합성 점검" 테이블 노출 — **PASS** (`GET /`로 tbl-lot-recon/LOT 정합성 점검/
   reconciliation 포함 확인)

### 검증 방법
- `/tmp` 임시 복사본에서 TestClient로 정상 케이스(입고→PASS)와 버그 시뮬레이션 케이스(직접 SQL로
  LOT qty 조작→FAIL 탐지) 둘 다 확인.
- `node --check`로 JS 문법 검증.
- 스키마 변경 없어 사용자 라이브 DB 추가 조치 불필요.

## 설계상 의도적 비범위 (task-plan에 사전 명시)
- 자동 알림/스케줄 점검 없음(온디맨드 조회 API + 수동 새로고침)
- 부정합 자동 교정 없음(사람이 확인 후 조치)
- LOT이 아예 없는 품목×창고 조합은 리포트에 나타나지 않음(점검 대상 없음, 오류 아님)
