# Eval Report — v11: 03 Procurement Management 확장

설계문서: `task-plan-v9-full-menu-rollout.md` §3 v11. 1.0 메뉴 구조 "03. Procurement Management"
중 공급업체평가/구매계약관리/외주구매·위탁구매 구분/원재료·부자재·설비·금형 구매(카테고리 뷰)/
통관·수입관리/구매실적관리/구매 Dashboard 구현.

## 구현

- **마이그레이션 0005(additive)** — `vendor_evaluation`(납기/품질/가격 100점 만점 평가), `purchase_contract`
  (sales_contract와 동일 패턴), `import_customs_record`(PO 단위 통관 기록, 간이) 3개 신규 테이블 +
  `purchase_order.po_type`(STANDARD/OUTSOURCING/CONSIGNMENT, 기본값 STANDARD) 컬럼 추가.
- **신규 라우터 `app/procurement_ext.py`**(prefix `/api`): 공급업체평가 등록/조회 + 평균점수·등급
  요약(`/vendor-evaluations/summary`, 80점 이상 A/60점 이상 B/미만 C), 구매계약 등록/조회,
  카테고리별 구매 집계(`/purchase/by-category` — `material.material_type` 필터 뷰, 신규 테이블 없음),
  통관 기록 등록/상태변경(PENDING→DECLARED→CLEARED/HOLD), 구매실적(`/purchase/performance`,
  vendor/material/month 그룹), 구매 KPI(`/purchase/kpi`).
- **`app/main.py` 최소 수정** — 기존 `create_po()`에 `po_type` 파라미터(기본 STANDARD, 미검증 값은
  400) 한 줄 추가. 외주/위탁구매는 승인 워크플로가 필요 없는 단순 분류라 v9의 quotation/sales_return
  패턴(범용 approval_workflow 재사용)과 달리 이 방식을 택함 — PR/PO/입고 기존 로직은 무변경.
- **원재료/부자재/설비/금형 구매**: task-plan §3 v11 지침대로 신규 테이블 없이 `material.material_type`
  필터 뷰로 대체. **알려진 범위 제한**: 현재 시드 데이터셋은 `material_type`이 RM/FG만 존재해
  실질적으로 원자재 구매만 카테고리로 잡힌다 — SUB(부자재)/EQUIP(설비)/MOLD(금형) 값이 향후 등록되면
  API/프론트 변경 없이 자동으로 별도 카테고리로 집계된다. 프론트에 이 제약을 안내 문구로 명시했다.
- **프론트**: `ProcurementPage.tsx`를 기존 단일화면(PR/PO)에서 6개 탭(발주관리/공급업체평가/구매계약/
  카테고리별 구매/통관관리/구매 분석)으로 확장. 발주관리 탭에 PO 구분(일반/외주/위탁) 선택 필드 추가.
  `lib/types.ts`에 v11 타입 7종(`VendorEvaluation`, `VendorEvaluationSummary`, `PurchaseContract`,
  `PurchaseByCategoryRow`, `ImportCustomsRecord`, `PurchasePerformanceRow`, `PurchaseKpi`) 추가,
  `PurchaseOrder`에 `po_type` 필드 추가.

## 검증

**pytest**: 신규 `tests/test_procurement_extension.py` 12개(공급업체평가 등록+요약+미존재공급사 404,
구매계약 등록, 카테고리 집계 shape+필터, PO 구분 기본값/명시값/잘못된값 400, 통관 등록+상태변경+
잘못된상태 400+미존재PO 404, 구매실적 3종 group_by, 구매KPI shape, 로그인 필요 확인) 추가.
기존 81개 + 신규 12개 = **93개 전부 PASS**(fresh `/tmp` 복사본, 회귀 없음).

**TypeScript**: `npx tsc -b` — 에러 없음.

## 비범위(의도적으로 남김)

- 브라우저 실기동 확인 — 이 세션 구조적 제약(리눅스 샌드박스/Mac 플랫폼 바이너리 문제, v1~v10과 동일
  제약)으로 미실행, 사용자 로컬 확인 필요.
- 부자재/설비/금형 구매 카테고리 실데이터 — 현재 시드 데이터셋에 해당 `material_type` 값이 없어
  API는 준비되어 있으나 조회 결과에는 나타나지 않음(알려진 범위 제한, 위 설명 참고).
- 통관/수입관리는 정식 관세사 EDI 연동 없는 간이 상태 관리 수준(task-plan에 명시된 Simplified 범위).

## 종합 평가

| 항목 | 평가 |
|---|---|
| 공급업체평가(등록+요약+등급) | ✅ 구현+테스트 PASS |
| 구매계약관리 | ✅ 구현+테스트 PASS |
| 외주/위탁구매 구분(po_type) | ✅ 구현+테스트 PASS(기존 PR/PO 로직 무변경) |
| 카테고리별 구매(원재료 등) | ✅ 구현+테스트 PASS(부자재/설비/금형은 데이터 부재로 미노출, 알려진 제한) |
| 통관/수입관리 | ✅ 구현+테스트 PASS |
| 구매실적/구매 KPI | ✅ 구현+테스트 PASS |
| 회귀(기존 81개) | ✅ 전부 PASS |
| 타입체크 | ✅ PASS |
| 브라우저 실기동 | ⚠️ 미실행 — 사용자 로컬 확인 필요 |

**점수: 91/100** (감점 사유: 브라우저 실기동 미확인, 카테고리 뷰가 현재 데이터로는 RM만 실질 검증됨)
