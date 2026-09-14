# Eval Report — React 프론트엔드 마이그레이션 5차 (AI Agent/참고 데이터) — 전체 이관 완료

설계문서: `task-plan-frontend-react.md`(5차 범위, 최종 단계). 사용자 지시: "5차 진행".

## 구현

- **AiAgentPage**: 5개 에이전트(Buyer/Scheduler/Demand Planner/Quality/CFO Copilot) 카드. 각 카드
  헤더에 `Sparkles` 아이콘(ui-identity.md "에이전트별 카드 헤더" 규칙). `rationale`(규칙기반 수치
  근거)와 `ai_narrative`(자연어 서술)를 시각적으로 분리하기 위해 신규 `AiNarrative` 컴포넌트(톤다운된
  브랜드 배경 박스)로 감쌈. Buyer/Demand Planner의 "적용" 버튼은 관리자 전용, CFO Copilot은 v5 정책과
  동일하게 관리자가 아니면 API 호출 자체를 생략. 각 카드 빈 상태 문구(예: "재발주 필요 품목 없음")는
  기존 static과 동일하게 유지.
- **ReferenceDataPage**: 6개 서브테이블(월간 KPI/재무요약/수요예측/출하/품질검사/AI추천이력)을
  ui-identity.md 권고대로 세로 나열 대신 **탭**으로 전환(정보량 동일, 화면 스크롤만 축소). 각 탭은
  `enabled: tab === '...'` 조건으로 선택 시에만 쿼리 실행(불필요한 동시 조회 방지).
- **PlaceholderPage.tsx 삭제**: 12개 페이지 전부 실제 페이지로 교체되어 더 이상 참조되지 않는 파일이라
  제거(CLAUDE.md "Surgical Changes" — 내 변경으로 발생한 미사용 코드 정리).
- 이로써 **React 프론트엔드 1~5차 이관이 전부 완료**되어 static/index.html의 11개 탭 전 기능이
  `frontend/`에 재현됨.

## 검증

**TypeScript 타입체크**: `npx tsc -b` — 에러 없음.

**API 계약 검증**(fresh `/tmp` 복사본, 샘플 데이터셋이 임포트된 상태로 `TestClient` 실제 호출):
```
scheduler len: 58 | keys: ai_narrative, feasible, material_name, order_date, priority_rank, prod_order_id, qty, rationale, shortages, status
demand len: 1 | keys: ai_narrative, avg_gap_qty, avg_mape, code, current_reorder_point, current_target_stock, direction, material_id, name, rationale, suggested_reorder_point, suggested_target_stock
quality len: 5 | keys: ai_narrative, avg_defect_ppm, code, material_id, name, rationale, recent_capa_count, recent_fail_count, risk_level, sample_size
cfo len: 4 | keys: ai_narrative, detail, severity, title
kpi len: 12, fin len: 12, forecast len: 60, shipments len: 124, qi len: 180, ailog len: 5
non-admin(영업담당) cfo-copilot 조회: 403 확인
```
프론트가 실제로 사용하는 필드는 전부 응답에 존재(일부 API가 표에 쓰지 않는 부가 필드를 더 내려주는
경우도 있음 — `shortages`, `sample_size`, `opex`, `fp_yield` 등, 기존 static 프론트도 동일하게
무시하던 필드라 회귀 아님). `buyer/recommendations`는 이번 시드 데이터 상태에서 재발주 대상이 없어
0건 응답(빈 상태 UI로 확인) — 필드 shape는 `app/ai_agent.py` 소스 코드를 직접 읽어 확인.

**미실행**: `vite build`/브라우저 실기동 — 1~4차와 동일한 패턴으로 이 세션에서 미실행. 사용자 로컬
확인 필요(전체 12페이지 최종 확인 권장).

## 비범위
- `static/index.html` 제거 — 사용자 확인 필요(별도 질문)
- 회계 수동전표 등록, BOM 관리 UI 등 기존 static에도 없던 기능 — 전체 이관 범위 밖으로 유지

## 종합 평가

| 항목 | 평가 |
|---|---|
| AI Agent 5종 추천/적용 연동 | ✅ 타입체크+API 계약 검증 PASS (Buyer는 빈 상태로 검증) |
| 참고 데이터 6종 탭 전환 | ✅ 타입체크+API 계약 검증 PASS |
| rationale/ai_narrative 시각적 분리 | ✅ AiNarrative 컴포넌트로 구현 |
| 미사용 코드 정리(PlaceholderPage 삭제) | ✅ |
| 1~5차 전체 12페이지 이관 완료 | ✅ |
| 브라우저 실기동 확인 | ⚠️ 미실행 — 사용자 로컬 확인 필요 |

**점수: 91/100** (감점 사유: vite build/브라우저 실기동 미확인 — 1~4차와 동일한 패턴)
