# Task Plan — AI Agent 나머지 3개 시나리오 (수요예측/품질/CFO Copilot)

## 목표
README/task-plan-v2.md에 "설계만 완료"로 남겨둔 3개 AI Agent 시나리오를 규칙기반(rule-based, LLM 미호출)으로
실제 동작하게 구현한다. 기존 AI Buyer/Scheduler와 동일한 거버넌스 원칙(추천-실행 분리, Human-in-the-loop)을 따른다.

## 범위
1. **AI Demand Planner** (`GET /api/ai/demand-planner/recommendations`, `POST /api/ai/demand-planner/apply`)
   - demand_forecast(최근 3개월)의 평균 MAPE가 임계치(15%) 이상인 품목을 예측 정확도 저하로 플래그.
   - actual_sales_qty와 forecast_qty의 평균 갭으로 과소/과대 예측 방향 판단, 재발주점/목표재고 조정값 제안.
   - apply는 material.reorder_point/target_stock을 직접 갱신(금액 이동이 없는 계획 파라미터라 승인 워크플로 생략,
     Buyer의 PR 생성과는 다르게 처리 — 사람이 버튼을 눌러야 반영되는 것은 동일).
2. **AI Quality Engineer** (`GET /api/ai/quality/recommendations`, 조회전용)
   - 품목별 최근 6건 quality_inspection 중 FAIL 건수, CAPA 필요 건수, 평균 defect_ppm 집계.
   - FAIL 발생 또는 CAPA 필요 비율 50% 이상인 품목만 추천 목록에 포함, risk_level(높음/중간) 부여.
   - CAPA 실행 테이블이 없으므로 apply 엔드포인트는 만들지 않음(정보 제공까지가 범위).
3. **CFO Copilot** (`GET /api/ai/cfo-copilot/insights`, 조회전용)
   - finance_summary_monthly 최근 2개월 영업이익률 변화, 영업이익 대비 현금흐름 괴리(운전자본 신호),
     kpi_monthly의 공급리스크 건수, 라이브 AR/AP(sales_invoice/ap_invoice OPEN 합계)를 조합한 인사이트 리스트.
   - 실행 액션 없음(자문 역할).

## 비범위(명시적으로 하지 않음)
- LLM 호출 없음(토큰/에러 최소화 원칙 유지, 순수 규칙기반).
- CAPA 워크플로 테이블/실행 API 신규 생성 안 함.
- 기존 Buyer/Scheduler 로직 변경 안 함.

## 성공 기준
1. 3개 GET 엔드포인트가 실데이터 기준으로 그럴듯한 추천/인사이트를 반환.
2. Demand Planner apply 클릭 시 material.reorder_point/target_stock이 실제로 갱신됨.
3. 기존 AI Agent(Buyer/Scheduler)·전체 E2E 플로우 회귀 없음.
4. index.html AI Agent 탭에 3개 섹션 추가, 브라우저에서 정상 렌더링 확인.
