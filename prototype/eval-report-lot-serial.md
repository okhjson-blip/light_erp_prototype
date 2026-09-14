# Evaluation Report — WMS/QMS LOT·Serial 추적

```json
{
  "pass": true,
  "score": 91,
  "independence_check": {
    "existing_files_modified": ["app/main.py", "app/integrations.py", "app/schema_sqlite.sql", "app/schema_postgres.sql", "static/index.html", "README.md"],
    "new_files": ["app/lot_tracking.py", "task-plan-lot-serial.md"],
    "db_schema_changed": true
  },
  "failures": [],
  "harness_update_needed": false
}
```

task-plan-lot-serial.md에 명시한 범위(기존 inventory 집계 테이블은 그대로 두고 LOT을 병행 레이어로
추가, FIFO 소진, 선택적 시리얼, QMS 실시간 등록) 그대로 구현됨. 신규 의존성 없음(표준 라이브러리
secrets/datetime만 사용).

## 성공 기준 대비 결과
1. 입고처리 → 새 LOT 생성(`GET /api/lots`) — **PASS** (RM 1000 입고 → LOT qty=1000 확인)
2. 생산실적입력 → RM LOT FIFO 소진 + FG LOT 생성, `generate_serials:true` 시 시리얼 생성 — **PASS**
   (BOM qty=1 × 완제품 10개 = RM 10 소진 확인, 시리얼 10건 생성 확인)
3. 출하 → FG LOT FIFO 소진 — **PASS** (FG LOT 10 → 6, 소진 4 기록 확인)
4. `GET /api/lots/{lot_id}/trace` — **PASS** (생성출처 + 소진이력 + 연결 시리얼 목록 반환 확인)
5. `GET /api/serials/{serial_no}/trace` — **PASS** (시리얼 → 소속 LOT 역추적 확인)
6. `POST /api/quality/inspections` — **PASS** (생산담당 등록 성공, 영업담당 시도 시 403 확인)
7. 기존 E2E 플로우 회귀 없음 — **PASS** (RBAC 401/403 재확인 + PR→PO→입고, 생산오더→작업지시→
   실적입력, 수주→출하 전부 해당 역할 토큰으로 재검증)
8. MES/WMS mock 웹훅도 동일하게 LOT 반영 — **PASS** (MES 생산실적 웹훅 → FG LOT 생성 확인,
   WMS IN/OUT 웹훅 → LOT 생성/소진 확인)

## 설계상 의도적 비범위 (task-plan에 사전 명시)
- 과거 임포트 재고(prototype_dataset 스냅샷)에는 LOT을 소급 생성하지 않음. FIFO 소진 시 가용
  LOT 수량이 부족해도 에러 없이 가능한 만큼만 소진 기록(집계 `inventory.qty`는 정상 차감되므로
  업무 흐름 자체는 막히지 않음 — 다만 이 경우 추적 정보는 불완전함).
- 유효기한(expiry)/리콜(recall) 워크플로 미포함.
- 신규 "품질담당" 역할을 만들지 않고 생산담당+관리자로 QMS 등록 게이팅(현실적 절충 — README에 명시).
- MES/WMS 웹훅 자체의 인증(API Key)은 별도 항목(다음 작업)으로 이월.

## 검증 방법
- `/tmp` 임시 복사본(실제 리포지토리 파일을 그대로 복사)에서 `with TestClient(app) as client:`로
  기존 시드 데이터(FG-1001 + BOM)를 사용해 입고→생산→출하 전체 흐름과 LOT/시리얼/QMS API를 검증.
- 기존 RBAC 401/403 동작 재확인으로 회귀 없음을 함께 확인.
- 프론트엔드는 `GET /`로 정적 HTML을 받아 신규 UI 요소(tbl-lots, tbl-serials, qi-material,
  submitQualityInspection, 시리얼 생성 체크박스) 포함 여부를 확인. JS 문법은 `node --check`로 검증.
- 사용자의 실제 라이브 DB(erp.db)는 건드리지 않음. 스키마가 바뀌었으므로(신규 테이블 3개 +
  quality_inspection.lot_id 컬럼) 실제 반영 시 기존 RBAC 적용 때와 동일하게 `app/erp.db` 삭제 후
  재기동해 재시드가 필요함 — 사용자에게 안내 필요.

## 남은 리스크
- 시리얼 대량 생성(수천 개) 시 안전장치로 1회 500개 상한을 두었으나, 실제 대량 생산 시나리오에서는
  이 상한을 넘길 수 있어 정책 재검토가 필요할 수 있음.
- LOT 재고와 집계 `inventory.qty` 간 실시간 정합성을 검증하는 로직은 없음(각각 독립적으로 기록).
