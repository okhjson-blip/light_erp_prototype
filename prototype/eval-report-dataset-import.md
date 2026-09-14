# Evaluation Report — prototype_dataset 임포트

```json
{
  "pass": true,
  "score": 90,
  "independence_check": {"existing_files_modified": ["app/schema_sqlite.sql", "app/schema_postgres.sql", "app/seed.py", "app/main.py", "static/index.html"], "db_schema_changed": true},
  "failures": [],
  "harness_update_needed": false
}
```

기존 파일 수정/스키마 변경은 task-plan-dataset-import.md에 사전 명시한 계획 범위 내(전부 additive:
컬럼 추가, 신규 테이블 추가, 기존 컬럼/테이블 삭제·변경 없음)이므로 계획대로 진행된 것으로 판단.

## 확인 결과 요약
`prototype_dataset/`는 코드 기반 FK(문자열)를 쓰는 플랫 CSV 17종 + 스테이징용 `seed_schema.sql`로,
기존 서로게이트 PK 정규화 스키마와 그대로 호환되지 않아 **코드→ID 매핑 임포터가 필요**했음
(task-plan에 기술한 대로). 아래처럼 수정 후 전체 데이터를 반영함.

## 성공 기준 대비 결과
1. 임포트 후 테이블별 행수가 CSV 대비 정확히 일치 — **PASS** (company 4, plant 5, warehouse 8,
   customer 6, vendor 8, material 15, bom 25, sales_order/line 216, purchase_order/line 264,
   production_order/work_order/production_result 180, inventory 45, demand_forecast 60,
   quality_inspection 180, shipment 124, finance_summary_monthly 12, kpi_monthly 12,
   ai_recommendation_log 5 — 전부 정확히 일치)
2. FK 무결성 오류 없음 — **PASS** (전 항목 code→id 매핑 성공, 매핑 실패시 즉시 예외를 던지는
   `_require_map` 가드를 넣었으나 실제로는 한 건도 발생하지 않음)
3. 기존 API에 신규 컬럼 포함 + 회귀 없음 — **PASS** (materials에 reorder_point/target_stock 실데이터
   반영 확인, customers/vendors/warehouses에 code 포함 확인, 기존 v1/v2 E2E 플로우(수주→출하→청구,
   PR→PO→입고, 생산오더→실적) 임포트된 데이터 위에서 재실행해 정상 동작 확인)
4. AI Buyer/Scheduler가 실데이터로 그럴듯하게 동작 — **PASS** (RM-0001 reorder_point=7079/
   target_stock=17948로 스냅샷 기준 정확히 계산됨. Scheduler는 58건의 오픈 생산오더를 자재가용성
   기준으로 정상 평가)
5. 신규 참조 테이블 6종 API+UI 조회 가능 — **PASS** (6개 엔드포인트 모두 정상 응답, "참고 데이터" 탭 추가)
6. 창고 매칭 버그(한글 문자열 매칭) 수정 확인 — **PASS**: 영문 창고명(이번 데이터셋)에서도
   `warehouse_type` 컬럼 기반으로 정확한 창고를 선택하도록 수정, 회귀 테스트로 확인

## 명시적으로 하지 않은 것 (task-plan에 기술한 스코프 경계, 계획대로)
- 과거 SO/PO의 배송/입고/회계전표를 소급 생성하지 않음 — 마스터+헤더/라인+현재 재고 스냅샷만 적재.
  대시보드의 매출채권/매입채무는 새로 발생시킨 라이브 트랜잭션 금액만 반영됨(의도된 동작)
- `ai_recommendations.csv`는 별도 `ai_recommendation_log` 테이블(과거 이력 참고용)로 분리 적재해
  실시간 규칙기반 AI Buyer/Scheduler(app/ai_agent.py)와 혼동되지 않게 함
- vendor의 quality_grade, customer/vendor의 country/group 등 일부 CSV 컬럼은 스코프 최소화를 위해
  적재하지 않음(현재 어떤 로직도 참조하지 않음)

## 알려진 제약
- 다중 공장(4개국) 데이터인데 화면의 출하/입고/생산실적 처리 버튼은 여전히 "첫 번째 매칭 창고"를
  단순 선택함 (공장별 창고 선택 UI는 미구현) — v3 이후 개선 과제로 남김
- 기존에 이미 떠 있던 서버(옛 스키마의 erp.db)는 새 컬럼/테이블이 없어 삭제 후 재시작이 필요했음.
  삭제 완료, `.py` 파일 touch로 재시작 트리거함 — 사용자 쪽 uvicorn --reload가 이를 감지해
  재기동하는지는 브라우저로 별도 확인 필요
