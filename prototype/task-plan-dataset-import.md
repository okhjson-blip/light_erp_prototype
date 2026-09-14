# Task Plan — prototype_dataset 임포트

## 확인 결과
`prototype_dataset/`는 전자부품·소형가전 제조사 가정의 코드기반(FK가 code 문자열) 플랫 CSV
17종 + `seed_schema.sql`(플랫 스테이징 스키마) + `README_dataset.md`(화면 매핑 가이드).
기존 v1/v2 정규화 스키마(서로게이트 PK/FK)와 컬럼·테이블 구조가 달라 **그대로는 사용 불가**하며,
코드→ID 매핑 임포터가 필요함. 17개 중 11개는 기존 테이블에 매핑 가능, 6개(수요예측/품질검사/
출하/재무요약/월간KPI/AI추천이력)는 대응 테이블이 없어 신규 추가 필요 — "필요시 수정" 지시에 따라
아래처럼 스키마를 additive하게 확장하고 전체 데이터를 반영한다.

## 매핑 결정

| CSV | 처리 |
|---|---|
| companies/plants/warehouses/customers/vendors | 기존 테이블에 매핑 + `code` 컬럼 신규 추가(추적성) |
| warehouses | `warehouse_type`(RM/FG) 컬럼 추가 — 기존 UI가 창고명 한글 포함여부로 원자재/완제품 창고를 구분하던 버그를 해결하는 데도 사용 |
| materials | 기존 material에 매핑(`code`는 이미 존재). `reorder_point`=재고스냅샷 safety_stock_qty 합, `target_stock`=on_hand_qty 합으로 계산해 AI Buyer가 의미있게 동작하도록 함 |
| bom_items | 기존 bom에 매핑 (item_no/effective_from은 프로토타입 스코프상 생략) |
| sales_orders/purchase_orders | 기존 sales_order+line / purchase_order+line에 매핑. `external_no`, `currency` 컬럼 신규 추가(원본 문서번호·통화 보존) |
| production_orders/production_results | production_order에 매핑(`external_no` 추가), production_result는 오더당 work_order 1개를 합성해 연결. `oee/availability/performance/quality_rate` 컬럼 신규 추가 |
| inventory_snapshot | 기존 inventory 테이블의 현재값으로 직접 적재(과거 거래를 재생하여 재고를 역산하지 않음 — 스냅샷을 현재 잔고의 소스오브트루스로 취급) |
| demand_forecast, quality_inspections, shipments, finance_summary, kpi_monthly, ai_recommendations | 신규 테이블 6개 추가(순수 참조/조회용, 비즈니스 로직 없음) |

## 명시적으로 하지 않는 것 (스코프 경계)
- 과거 SO/PO 배송·입고·회계전표를 소급 생성하지 않음(트랜잭션 재현이 아니라 마스터+헤더/라인+현재 재고 스냅샷만 적재). 기존 화면의 출하/청구/입고처리 버튼은 그대로 사용 가능해 이후 수동으로 라이브 플로우를 시연할 수 있음.
- `ai_recommendations.csv`는 과거 이력 참고용 정적 테이블(`ai_recommendation_log`)로만 적재하고, 기존 v2의 실시간 규칙기반 AI Buyer/Scheduler 추천 로직과는 분리·구분 표기(혼동 방지)

## 성공 기준
1. `python3 -c "from app.seed import run_seed"` 기반 임포트 실행 후 각 테이블 행수가 CSV 대비 정확히 일치
2. FK 무결성 오류 없음 (모든 code→id 매핑 성공, 매핑 실패시 임포트가 조용히 넘어가지 않고 에러로 드러남)
3. 기존 v1/v2 API(materials/customers/... 등) 응답에 `code` 등 신규 컬럼이 정상 포함되고 기존 프론트 로직 회귀 없음
4. `/api/inventory`, `/api/ai/buyer/recommendations` 등이 새 데이터 기준으로 그럴듯한 값을 반환
5. 신규 참조 테이블 6종이 각각 GET API + UI "참고 데이터" 탭에서 조회 가능
6. 창고 매칭 버그(한글 문자열 매칭) 수정 확인 — 이번 데이터셋(영문 창고명)에서도 출하/입고/생산실적처리가 정확한 창고를 선택하는지 확인

## 미결 질문
- 없음. 지시된 "필요시 수정해서 데이터 반영" 범위 내에서 판단해 진행.
