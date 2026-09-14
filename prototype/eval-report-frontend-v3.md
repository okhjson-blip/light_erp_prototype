# Eval Report — React 프론트엔드 마이그레이션 3차 (생산/재고)

설계문서: `task-plan-frontend-react.md`(3차 범위), `ui-identity.md`. 사용자 지시: "3차(생산/재고)로 진행".

## 구현

- **ProductionResultPicker 컴포넌트 신규**: `WarehousePicker`와 유사하지만 수량 입력 + 시리얼 생성
  체크박스가 추가로 필요해 별도 컴포넌트로 분리(기존 static/index.html의 `openResultPicker`/
  `confirmResultPick` 패턴 재현).
- **ProductionPage**: 생산오더 등록 폼(완제품[RM 제외 필터]/공장/수량) + 목록 테이블(`PLANNED`→작업지시
  버튼, `IN_PROGRESS`→`ProductionResultPicker`). 오더별 최근 발급된 `work_order_id`는 컴포넌트 상태
  (`lastWorkOrder` record)로 보관 — 기존 static의 전역 `LAST_WORK_ORDER` 객체를 React state로 재현.
  하단에 QMS 품질검사 등록 폼(품목 선택 시 해당 품목의 ACTIVE LOT 목록을 `useQuery`로 동적 조회 —
  기존 `loadQiLots()` 동작과 동일).
- **InventoryPage**: 현재고/재고이동이력/LOT추적/시리얼추적/LOT정합성 점검 5개 카드. LOT·시리얼 "추적"
  버튼은 기존과 동일하게 트레이스 결과를 요약 메시지로 표시(펼침형 상세는 ui-identity.md에서 "차용
  검토" 수준으로만 언급돼 있어 이번 범위에서는 정보량 동일성을 우선해 메시지 방식 유지 — 비범위 아님,
  향후 폴리시 단계에서 확장 가능). 시리얼 상태변경은 생산담당/관리자에게만 드롭다운+변경 버튼 노출.
  정합성 "부정합" 행은 `bg-danger-soft/40`로 배경 강조(ui-identity.md의 "위험행 강조" 규칙 적용).
- 두 페이지 모두 정보항목은 기존 static과 완전 동일, 레이아웃(카드 분리, 뱃지, 인라인 액션)만 변경.

## 검증

**TypeScript 타입체크**: `npx tsc -b` — 에러 없음(신규 파일: types.ts 확장 9개 인터페이스,
ProductionResultPicker.tsx, ProductionPage.tsx, InventoryPage.tsx, App.tsx 라우트 갱신).

**API 계약 검증**(fresh `/tmp` 복사본, `TestClient`로 전체 생산 흐름 + 재고/LOT/시리얼 조회 실제 호출):
```
production-orders[0] keys: external_no, material_id, material_name, order_date, plant_id, prod_order_id, qty, status
result keys: lot, result_id, serials | lot keys: lot_id, lot_no | serials len: 5
inventory[0] keys: code, inventory_id, material_id, material_name, qty, warehouse_id, warehouse_name
txns[0] keys: material_id, material_name, qty, ref_doc_id, ref_doc_type, txn_date, txn_id, txn_type, warehouse_id
lots[0] keys: created_date, lot_id, lot_no, material_code, material_id, material_name, qty, source_ref_id, source_type, status, warehouse_id, warehouse_name
lot trace keys: consumptions, lot, serials
serials[0] keys: created_date, lot_id, lot_no, material_code, material_id, material_name, serial_id, serial_no, status
serial trace keys: lot, serial
reconciliation[0] keys: active_lot_qty, consistent, inventory_qty, material_code, material_id, material_name, untracked_qty, warehouse_id, warehouse_name
```
생산오더 등록→작업지시→실적입력(시리얼 5건 생성 확인)→품질검사 등록까지 전체 흐름을 실제로 호출해
200 응답 확인. 프론트 `lib/types.ts` 인터페이스 전부 실제 응답과 필드명까지 정확히 일치.

**미실행**: `vite build` 번들링과 브라우저 실기동은 이번에도 플랫폼(리눅스 샌드박스 vs 사용자 Mac)
바이너리 불일치로 이 세션에서 실행하지 못함 — 1~2차와 동일한 패턴. 사용자 로컬 확인 필요.

## 비범위
- 회계/승인함/연동로그(4차), AI Agent/참고데이터(5차) — 다음 단계
- LOT/시리얼 추적 결과를 펼침형 상세 행으로 바꾸는 것 — 정보량은 동일하나 표시 방식 개선은 별도 후보

## 종합 평가

| 항목 | 평가 |
|---|---|
| 생산오더 등록/작업지시/실적입력(LOT+시리얼) 연동 | ✅ 전체 흐름 TestClient로 실제 호출 검증 |
| QMS 품질검사 등록(LOT 동적 조회 포함) 연동 | ✅ API 계약 검증 PASS |
| 재고/이동이력/LOT/시리얼/정합성 조회 | ✅ 6개 엔드포인트 응답 필드 전체 일치 확인 |
| 시리얼 상태변경 권한 게이팅 | ✅ 프론트에서 hasRole 체크, 백엔드 동일 정책 재확인 |
| 브라우저 실기동 확인 | ⚠️ 미실행 — 사용자 로컬 확인 필요 |

**점수: 90/100** (감점 사유: vite build/브라우저 실기동 미확인 — 타입체크+API 계약 검증으로 대체)
