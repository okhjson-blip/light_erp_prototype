# Task Plan — WMS/QMS LOT·Serial 추적 (v3 우선순위 2)

## 목표
재고 이동(입고/생산/출하)에 LOT(배치) 단위 추적을 추가해 "이 완제품이 어느 원자재 LOT으로
만들어졌는지", "이 원자재 LOT이 어디로 소진됐는지" 역추적(traceability)이 가능하게 한다.
전자/전기 제품 특성상 완제품 낱개 추적이 필요한 경우를 위해 선택적 시리얼 넘버 생성도 지원한다.
QMS(품질검사)는 기존 참조데이터(임포트, 조회전용)에 더해, LOT에 연결된 실시간 검사 등록 기능을
추가한다.

## 설계 결정
1. **기존 `inventory`(집계 테이블)는 그대로 둔다.** LOT은 별도 레이어로 추가하고, 기존
   `adjust_inventory()` 로직은 건드리지 않는다(Surgical Changes). LOT 레이어는 같은 호출부에
   "한 줄 추가"로 병행 기록한다.
2. **LOT 생성**: 입고(GR), 생산실적(FG 입고), WMS IN 이벤트 시 새 LOT 생성.
3. **LOT 소진(FIFO)**: 출하(delivery), 생산실적의 BOM 소요(RM 출고), WMS OUT 이벤트 시
   가장 오래된 ACTIVE LOT부터 순서대로 소진 기록.
4. **과거 임포트 재고는 LOT이 없다** (스냅샷으로 적재된 데이터라 소급 생성하지 않음). FIFO 소진
   시 가용 LOT 수량이 부족해도 에러 없이 가능한 만큼만 소진 기록하고 나머지는 추적 불가로 남긴다
   (명시적 비범위 — 기존 회귀 방지가 우선).
5. **시리얼 넘버는 선택 기능**이다. 생산실적입력 시 `generate_serials: true`를 명시적으로 보낸
   경우에만 완제품 LOT 안에 개별 시리얼을 생성한다(기본은 LOT 추적만). 안전장치로 1회 최대 500개.
6. **QMS 실시간 등록**: `quality_inspection` 테이블에 `lot_id`(nullable) 컬럼을 추가(additive)하고,
   신규 `POST /api/quality/inspections`로 LOT에 연결된 검사를 기록할 수 있게 한다. 기존 임포트
   데이터(조회전용, reference_data.py)는 그대로 유지.
7. **신규 의존성 없음.** 표준 라이브러리(secrets, datetime)만 사용.
8. **역할 게이팅**: 이 프로젝트에 "품질담당" 역할이 없으므로, 품질검사 등록은 생산담당+관리자로
   게이팅한다(생산현장 검사라는 현실적 가정). LOT/시리얼 조회 API는 기존 RBAC 범위 결정과 동일하게
   GET이라 인증을 강제하지 않는다.

## 신규 테이블 (additive)
- `lot(lot_id, lot_no UNIQUE, material_id, warehouse_id, qty, source_type, source_ref_id, status, created_date)`
- `lot_consumption(consumption_id, lot_id, qty, ref_doc_type, ref_doc_id, consumed_date)`
- `serial_number(serial_id, serial_no UNIQUE, material_id, lot_id NULL, status, created_date)`
- `quality_inspection.lot_id` 컬럼 추가 (nullable FK)

## 비범위 (명시)
- 과거 임포트 재고에 대한 소급 LOT 생성
- 유효기한(expiry)/리콜(recall) 워크플로
- 신규 "품질담당" 역할 신설
- LOT 재고와 집계 `inventory.qty`의 실시간 정합성 검증 로직(둘은 독립적으로 기록됨)

## 성공 기준
1. 입고처리 → 새 LOT 생성 확인 (`GET /api/lots`)
2. 생산실적입력 → RM LOT 소진 기록 + FG LOT 생성 확인, `generate_serials:true` 시 시리얼 생성 확인
3. 출하 → FG LOT 소진 기록 확인 (FIFO 순서)
4. `GET /api/lots/{lot_id}/trace` — 소진 이력 조회 가능
5. `GET /api/serials/{serial_no}/trace` — 시리얼→LOT 역추적 가능
6. `POST /api/quality/inspections` — LOT 연결 검사 등록, 역할 미달 시 403
7. 기존 E2E 플로우(수주→출하→청구, PR→PO→입고, 생산오더→작업지시→실적입력) 회귀 없음
8. MES/WMS mock 웹훅(integrations.py)도 동일하게 LOT 생성/소진 반영
