# Eval Report — React 프론트엔드 마이그레이션 2차 (기준정보/영업/구매)

설계문서: `task-plan-frontend-react.md`(2차 범위), `ui-identity.md`(레이아웃 규칙). 사용자 지시:
"이관 진행"(1차 검증 완료 후 2차 진행 승인).

## 구현

- **공용 컴포넌트 3종 신규**(`frontend/src/components/`): `LineItemsEditor`(품목+수량[+단가] 라인
  편집기, SO/PR/PO 등록 폼 3곳에서 재사용 — 기존 static/index.html의 `addLineRow`/`collectLines`를
  React 상태로 재현), `WarehousePicker`(행 액션 버튼 → 인라인 드롭다운(공장명 우선정렬)+확인/취소,
  기존 `openWarehousePicker`/`confirmPick` 패턴 재현), `StatusBadge`(SO/PO/PR 상태값 전체를
  ui-identity.md의 success/warning/info/danger semantic 매핑 표에 따라 일관 렌더).
- `components/ui/select.tsx` 신규 — Radix Select 대신 Input과 동일 톤의 네이티브 `<select>` 스타일링만
  (이 프로토타입 규모에선 Radix 트리거/콘텐츠 보일러플레이트가 과설계라 판단, CLAUDE.md "Simplicity
  First" 적용).
- **MdmPage**: 품목/고객/공급사 3개 섹션, 각각 등록 폼(관리자 전용, `hasRole('관리자')`)+목록 테이블
  카드로 좌우 2열 분리(ui-identity.md 페이지별 적용 메모 그대로). TanStack Query `useMutation`으로
  등록 후 해당 목록 쿼리만 invalidate.
- **SalesPage**: 수주 등록 폼(고객 선택+라인아이템)+수주 목록 테이블. 목록 행에 `WarehousePicker`(출하,
  FG창고)+청구 버튼(영업담당/관리자만 노출). 상태값(OPEN/DELIVERED/INVOICED)은 `StatusBadge`로 표기.
- **ProcurementPage**: PR 등록(라인아이템만)+PO 등록(공급사+라인아이템+단가) 폼 2개, PR/PO 목록
  테이블. PO가 `OPEN` 상태일 때만 입고처리(`WarehousePicker`, RM창고) 액션 노출 — 기존 로직과 동일.
- 정보항목/필드는 기존 `static/index.html`과 완전히 동일하게 유지(ui-identity.md 비범위 원칙 준수) —
  레이아웃(카드 분리, 뱃지, 인라인 창고선택)만 변경.

## 검증

**TypeScript 타입체크**: `npx tsc -b` — 에러 없음(신규 파일 8개: types.ts 확장, select.tsx,
StatusBadge.tsx, LineItemsEditor.tsx, WarehousePicker.tsx, MdmPage.tsx, SalesPage.tsx,
ProcurementPage.tsx, App.tsx 라우트 갱신).

> 참고: 이번 라운드에서는 `vite build`(번들링)까지는 이 세션에서 직접 실행하지 못했다 — 사용자가
> Mac에서 `npm install`을 다시 돌린 뒤로 `node_modules`가 darwin-arm64 네이티브 바이너리로 채워져
> 있어, 리눅스 샌드박스에서 rolldown 바이너리를 못 찾는 반대 방향의 플랫폼 불일치가 발생(1차 때와
> 같은 근본 원인, 방향만 반대). 타입 오류가 없다는 것과 API 계약이 맞다는 것은 확인했으므로 번들링
> 실패 리스크는 낮지만, **사용자가 로컬에서 `npm run build` 또는 `npm run dev`로 최종 확인 필요**.

**API 계약 검증**(fresh `/tmp` 복사본, `TestClient`로 프론트가 기대하는 응답 필드 확인):
```
materials[0] keys: code, material_id, material_type, name, plant_id, reorder_point, target_stock, uom
customers[0] keys: code, credit_limit, currency, customer_id, name, payment_term
vendors[0] keys: code, lead_time_days, name, payment_term, vendor_id
warehouses[0] keys: code, name, plant_id, warehouse_id, warehouse_type
plants[0] keys: code, company_id, name, plant_id
sales-orders[0] keys: currency, customer_id, customer_name, external_no, order_date, so_id, status
prs[0] keys: created_date, pr_id, requester_id, status
pos[0] keys: currency, external_no, order_date, po_id, pr_id, status, vendor_id, vendor_name
```
SO 등록→출하→청구, PR 등록→PO 등록→입고처리 전체 흐름을 실제로 호출해 200 응답과 금액 계산까지
확인(`delivery_id`, `invoice amount`, `ap amount` 정상 반환). 프론트 `lib/types.ts`의 인터페이스가
전부 실제 응답과 필드명까지 정확히 일치.

**미실행**: 브라우저 실기동(폼 제출 클릭, WarehousePicker 인터랙션 눈으로 확인)은 사용자 로컬 확인
필요 — 1차 때와 동일한 패턴.

## 비범위 (task-plan-frontend-react.md 참고)

- 생산/재고/회계/승인함/연동로그/AI Agent/참고데이터 7개 탭 — 3차~5차 단계에서 순차 이관
- BOM(자재명세서) 등록 UI — 기존 static 프론트에도 없어 이번 이관 범위 밖(백엔드 API 자체가 조회용
  없음)

## 종합 평가

| 항목 | 평가 |
|---|---|
| 기준정보(품목/고객/공급사) CRUD 연동 | ✅ 타입체크+API 계약 검증 PASS |
| 영업(수주 등록/출하/청구) 연동 | ✅ 전체 흐름 TestClient로 실제 호출 검증 |
| 구매(PR/PO 등록/입고처리) 연동 | ✅ 전체 흐름 TestClient로 실제 호출 검증 |
| 창고선택 UI(공장 우선정렬) 재현 | ✅ 기존 로직과 동일하게 구현(육안 확인은 사용자 몫) |
| 정보항목 동일성(ui-identity.md 비범위 준수) | ✅ 필드 추가/제거 없음 |
| 브라우저 실기동 확인 | ⚠️ 미실행 — 사용자 로컬 확인 필요 |

**점수: 90/100** (감점 사유: 이 세션에서 `vite build` 번들링 자체는 실행하지 못함(플랫폼 바이너리
불일치) — 타입체크+API 계약 검증으로 대체. 브라우저 실기동도 미확인)
