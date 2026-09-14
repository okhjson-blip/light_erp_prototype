# Task Plan v1 — AX ERP Prototype

## 목표
Phase 1 Core 7개 모듈(MDM/Sales/Procurement/Production/Inventory/FI/Common)을
단일 프로세스 FastAPI + SQLite로 구현. E2E 트랜잭션 체인 1개(수주→출하→매출채권,
구매요청→발주→입고→매입채무, 생산오더→실적→재고반영) 동작 확인이 성공 기준.

## 성공 기준 (측정 가능)
1. `uvicorn` 기동 후 에러 없이 `/` 접속 시 대시보드 렌더링
2. 자재 등록 → 수주 등록 → 출하 처리 시 inventory.qty 감소 + sales_invoice 자동 생성 확인
3. PR → PO → 입고 처리 시 inventory.qty 증가 + ap_invoice 자동 생성 확인
4. 생산오더 → 작업실적 입력 시 완제품 inventory 증가 확인
5. 대시보드 KPI(오픈 SO/PO/재고품목수/대기승인) 숫자가 실제 데이터와 일치

## DB 스키마
`app/schema.sql` — 신규 테이블 30개 (기존 테이블 없음, ALTER 없음)

## API 목록
`app/main.py` 참조 — REST 엔드포인트 약 25개 (materials/customers/vendors/
sales-orders/purchase-requisitions/purchase-orders/production-orders/
work-orders/inventory/accounting/approvals/dashboard)

## 컴포넌트 구조
- `app/database.py` : SQLite 연결 + 스키마 초기화
- `app/seed.py` : 기준정보 초기 데이터
- `app/main.py` : FastAPI 라우트 전체 (모놀리식 — 단일 프로세스 프로토타입이므로
  모듈별 라우터 분리는 v2 이후로 보류, 단일 파일이 진단/디버그에 더 유리)
- `static/index.html` : 탭 기반 단일 페이지 UI (순수 JS fetch, 빌드 도구 없음)

## 기존 코드 영향범위
없음 (신규 프로젝트, 신규 파일만 생성)

## 미결 질문
- 없음 (사용자가 스택/범위를 사전 확정: 경량 Python, Phase1 Core 7모듈)
