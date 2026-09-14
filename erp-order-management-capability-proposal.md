# AX-ERP 필수 주문관리 Capability 참조 제안

| 항목 | 내용 |
|---|---|
| 문서 상태 | **Proposed / Claude Review Required** |
| 제안 근거 | 2026-07-18 사용자 방향 변경. 별도 AX-OMS 개발 중지 |
| 적용 대상 | AX-ERP Sales / Order Management 구조 |
| 결정 주체 | Claude 주 책임자, Enterprise Architect, 필요 시 EA Board |
| 구현 권한 | Claude 승인 전 AX-ERP 코드와 Approved 기준문서를 변경하지 않는다. |

## 1. 목적

중견기업 운영 현실을 반영해 별도 OMS 솔루션을 구축하지 않고, ERP가 수주부터 출하지시까지 필요한 주문관리 Capability를 제공하도록 제안한다. WMS의 실물 물류, PP/MRP의 계획, CRM의 고객 접점, QMS의 품질 책임은 ERP로 흡수하지 않는다.

## 2. ERP에 필수인 Capability

### 2.1 수주 Lifecycle

- Sales Order Header·Line 등록, 조회, 변경, 확정, 취소.
- 고객 PO 번호와 ERP 수주번호 중복 방지.
- 수량, 단위, 통화, 가격조건 Snapshot, 요청납기 관리.
- 낙관적 버전으로 동시수정 충돌 방지.
- 확정 이후 변경은 Revision 또는 명시적 변경이력으로 감사 가능해야 한다.

### 2.2 납기약속과 가용성 확인

- WMS의 실물 가용재고와 PP/MRP의 계획·생산가능 정보를 조회한다.
- ATP·CTP 결과를 원본으로 저장하지 않고 요청·응답 Snapshot과 근거 ID를 남긴다.
- 요청납기와 약속납기를 분리한다.
- 가용성 서비스 장애 시 임의 확정하지 않고 보류 또는 수동승인 상태로 전환한다.

### 2.3 부분출하와 Back Order

- 수주 Line별 주문수량, 출하지시수량, 출고완료수량, 잔량을 분리한다.
- 누적 출하지시수량은 미출하지시 잔량을 초과할 수 없다.
- 부분출하 후 잔량은 Back Order로 추적하되 별도 재고 원본을 만들지 않는다.
- 전체 취소는 출하지시 전까지만 허용하고 이후에는 잔량취소와 보상절차를 사용한다.

### 2.4 출하지시

- ERP가 Shipment Instruction을 생성해 WMS에 전달한다.
- 출하지시는 수주 Line, 품목, 수량, 출고요청일, 출고창고, 납품처 참조를 포함한다.
- WMS 수락·거절·부분출고·출고완료 결과를 Event로 수신한다.
- Picking, Packing, Lot·Serial, 실물 재고 차감은 WMS에만 존재한다.

### 2.5 청구·회계 연계

- WMS Goods Issue를 근거로 Billing Due를 생성한다.
- Invoice, AR, 매출인식, Credit Memo, 회계전표는 기존 ERP 책임으로 유지한다.
- 출고 완료와 Invoice 상태를 주문 화면에 Projection으로 표시하되 원본 책임은 변경하지 않는다.

### 2.6 예외와 감사

- 신용한도 초과, 가격 미확정, 재고 부족, 생산능력 부족, 납기 불가를 명시적 상태와 사유로 기록한다.
- 동일 `Idempotency-Key` 재요청은 같은 결과를 반환하고 중복 수주·출하지시를 만들지 않는다.
- 확정·취소·납기변경·출하지시·수동승인에 사용자, 시각, 사유를 기록한다.
- Event 발행은 Transactional Outbox를 사용한다.

## 3. ERP 내부 모듈 구조 아이디어

| 모듈 | 책임 | 금지사항 |
|---|---|---|
| `sales-order` | 수주 Aggregate와 Lifecycle | 재고 직접 차감, Invoice 전표 생성 |
| `order-promise` | ATP·CTP 요청 조정과 납기약속 | WMS·PP/MRP 원본 복제 |
| `fulfillment-orchestration` | 부분출하, Back Order, Shipment Instruction | Picking·Packing 구현 |
| `pricing-credit` | 가격조건과 신용검사 | 주문 상태 직접 우회 변경 |
| `billing-accounting` | Billing, Invoice, AR, 매출·전표 | WMS Goods Issue 위조·대체 |
| `wms-adapter` | Shipment Instruction 발행과 WMS 결과 소비 | WMS DB 직접 접근 |
| `crm-adapter` | Opportunity·고객요청 참조 | CRM 접점·클레임 원본 소유 |

모듈은 ERP 내부 배포가 가능하지만 공개 Port, 분리된 책임, Event 계약을 유지해 향후 독립 서비스가 필요해져도 업무 로직을 재작성하지 않도록 한다.

## 4. 데이터 소유권 제안

| 데이터 | Owner | ERP 처리 방식 |
|---|---|---|
| 고객·신용·가격·판매계약 | ERP | 원본 관리 |
| Sales Order·납기약속·Back Order·Shipment Instruction | ERP | 원본 관리 |
| 품목·EBOM | MDM, 향후 PLM | ID 참조와 거래 Snapshot |
| 실물재고·로케이션·입출고 | WMS | API/Event 소비 |
| 생산가능성·계획 | PP/MRP·MES | API/Event 소비 |
| 고객 접점·클레임 | CRM | 참조와 업무 인계 |
| 검사·NCR·CAPA | QMS | 참조와 업무 인계 |
| Invoice·AR·매출인식·회계전표 | ERP | 원본 관리 |

## 5. API·Event 계약 후보

API 후보는 `/api/v1/sales-orders`, `/api/v1/sales-orders/{id}/confirm`, `/api/v1/sales-orders/{id}/cancel`, `/api/v1/sales-orders/{id}/shipment-instructions`다. 쓰기 API는 `Idempotency-Key`, RFC 9457 오류, OIDC RBAC를 적용한다.

Event 후보는 다음과 같다. 명칭과 Payload는 Platform Team·Claude 승인 후 중앙 Catalog에 등록한다.

- `com.ax.erp.sales-order.confirmed.v1`.
- `com.ax.erp.sales-order.cancelled.v1`.
- `com.ax.erp.shipment-instruction.issued.v1`.
- `com.ax.erp.shipment-instruction.cancelled.v1`.

ERP는 WMS의 기존 `goods-issue.recorded.v1`을 소비해 출고완료와 Billing Due를 갱신한다.

## 6. 기존 ERP 구현의 보강 우선순위

1. 현재 `sales_order` 등록과 조회에 상태전이·동시성·멱등성을 추가한다.
2. Delivery API의 직접 재고 차감과 Lot·Serial 처리를 WMS Adapter 호출로 분리한다.
3. 수주 확정 전에 Credit·ATP·CTP 검사를 명시적 Port로 분리한다.
4. 부분출하·Back Order·잔량취소를 Line 단위로 구현한다.
5. Goods Issue Event 이후 Invoice·AR·회계처리가 실행되도록 결합을 해소한다.
6. Order-to-Cash Contract Test를 ERP·WMS·PP/MRP 경계에 추가한다.

## 7. 최소 완료 기준

- 수주 확정·취소·부분출하·Back Order·출하지시 상태전이 테스트 통과.
- 중복 요청과 Event 재전송에서 중복 데이터가 발생하지 않음.
- ERP가 WMS DB와 PP/MRP DB를 직접 읽지 않음.
- Shipment Instruction Mock으로 ERP→WMS 계약 테스트 통과.
- WMS Goods Issue Mock으로 출고완료→Invoice 연계 테스트 통과.
- 역할·민감도·감사로그 검증 통과.
- Claude Evaluator와 책임자의 설계 승인.

## 8. Claude·EA 기준선 변경 검토

본 방향을 채택하려면 다음 기준선 변경이 필요하다.

1. 05 통합개발계획서 §3.2에서 수주·출하지시 Owner를 OMS에서 ERP로 변경한다.
2. P1 로드맵에서 OMS MVP를 제거하고 ERP Order Management 보강으로 대체한다.
3. Gate 6의 Order-to-Cash 시나리오에서 OMS 대신 ERP 주문관리 Capability를 사용한다.
4. WMS의 출하지시 구독 계약을 OMS Event에서 ERP Event로 변경한다.
5. ADR-014의 `oms` 토큰은 향후 확장용 예약 또는 Deprecated 중 하나로 결정한다.

본 문서는 Claude의 설계 판단을 위한 참조 제안이며 직접적인 AX-ERP 변경 지시가 아니다.
