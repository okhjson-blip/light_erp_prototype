# Eval Report — v9: 01 Sales Management 확장

설계문서: `task-plan-v9-full-menu-rollout.md` §3 v9. 1.0 메뉴 구조 "01. Sales Management"의 미구현
9개 항목(가격정책/견적/판매계약/반품/서비스오더/채권조회/영업실적/손익분석/영업KPI) 구현.

## 구현

- **마이그레이션 0004**: `price_policy`, `quotation`/`quotation_line`, `sales_contract`,
  `sales_return`/`sales_return_line`, `service_order` 신규 테이블 + `material.std_cost` 컬럼(손익
  근사 계산용). 전부 additive, `schema_*.sql` 무수정.
- **`app/sales_ext.py`(신규 라우터)**: 가격정책 CRUD+lookup(고객전용 우선, 없으면 전체고객 정책),
  견적 등록→승인→수주전환, 판매계약 CRUD, 반품 접수→승인 시 재고복원, 서비스오더 접수+상태변경,
  채권조회(payment_term 기반 만기 근사+연체 표시), 영업실적(고객/제품/월별), 손익분석(매출-표준원가
  근사), 영업 KPI(이번달 매출/수주잔고/이번달 수주건수·고객수).
- **승인함 재사용**: 견적·반품은 신규 UI 없이 기존 `approval_workflow`(PR/PO와 동일 테이블)에
  등록 — `app/main.py`의 `decide_approval()`에 `QUOTATION`/`SALES_RETURN` 분기만 추가해 기존
  승인함 화면이 그대로 동작한다.
- **`SalesPage.tsx`**: 탭 7개(수주관리/견적관리/가격정책/판매계약/반품관리/서비스오더/영업 분석)로
  재구성. 영업 분석 탭은 KPI 카드 4종 + AR 조회 표 + 실적/손익 표(고객·제품·월별 그룹 전환)를 통합.

## 검증

**pytest**: 신규 `tests/test_sales_extension.py` 11개(가격정책 조회/미스매치, 견적 승인 전 전환
차단, 견적 승인→전환, 판매계약, 반품 승인 시 재고 복원(+2 확인)/반려 시 재고 불변, 서비스오더
상태전이+잘못된 상태 400, AR/실적/손익/KPI 응답 shape) 추가. 기존 62개 + 신규 11개 = **73개 전부
PASS**(fresh 경량 복사본 — `app/migrations/tests/requirements*.txt/prototype_dataset`만 복사해
`frontend/node_modules` 등 대용량 디렉토리를 제외, 샌드박스 타임아웃 회피).

**TypeScript**: `npx tsc -b` — 에러 없음.

**버그 하나 발견·수정(테스트 코드 쪽)**: `GET /api/inventory`는 필터 쿼리파라미터가 없어 전체 목록을
반환하는 기존 동작인데, 처음 작성한 테스트가 `?material_id=&warehouse_id=`를 붙이면 필터링될 거라
잘못 가정해 실패했다. 실제 재고 복원 로직은 정상 동작했음(디버그 스크립트로 특정 행의 qty가 정확히
+2 되는 것 확인) — 테스트를 클라이언트 사이드 필터링으로 수정.

## 비범위(의도적으로 남김)
- 담당자별 영업실적 — `sales_order`에 영업담당자 컬럼이 없어 이번 라운드에서 추가하지 않음(고객/
  제품/월별 집계만 제공).
- 정교한 손익배부(COPA) — v17(09 Controlling)에서 다룰 예정, 이번은 표준원가 단순 차감 근사치.
- 브라우저 실기동 확인 — 이 세션 구조적 제약(플랫폼 바이너리 문제)으로 미실행, 사용자 로컬 확인 필요.

## 종합 평가

| 항목 | 평가 |
|---|---|
| 가격정책/견적/전환 흐름 | ✅ 구현+테스트 PASS |
| 판매계약 | ✅ 구현+테스트 PASS |
| 반품(승인 시 재고복원, 반려 시 불변) | ✅ 구현+테스트 PASS |
| 서비스오더 | ✅ 구현+테스트 PASS |
| 채권조회/실적/손익/KPI | ✅ 구현+테스트 PASS |
| 회귀(기존 62개) | ✅ 전부 PASS |
| 타입체크 | ✅ PASS |
| 브라우저 실기동 | ⚠️ 미실행 — 사용자 로컬 확인 필요 |

**점수: 91/100** (감점 사유: 브라우저 실기동 미확인 — 기존 세션과 동일한 구조적 제약)
