# Evaluation Report — MES/WMS 웹훅 인증 (API Key)

```json
{
  "pass": true,
  "score": 93,
  "independence_check": {
    "existing_files_modified": ["app/integrations.py", "app/seed.py", "app/schema_sqlite.sql", "app/schema_postgres.sql", "simulate_mes_wms.py", "README.md"],
    "new_files": ["task-plan-mes-auth.md"],
    "db_schema_changed": true
  },
  "failures": [],
  "harness_update_needed": false
}
```

task-plan-mes-auth.md에 명시한 범위(X-API-Key 헤더, source_system별 키 분리, RBAC와 별개의
system-to-system 인증) 그대로 구현됨. 신규 의존성 없음.

## 성공 기준 대비 결과
1. X-API-Key 없이 웹훅 호출 → 401 — **PASS**
2. 잘못된 키로 호출 → 401 — **PASS**
3. 다른 source_system 키로 교차 호출(MES 키로 WMS 엔드포인트 등) → 401 — **PASS**
4. 올바른 키로 호출 → 200 및 LOT/재고 반영 확인 — **PASS**
5. `GET /api/integrations/events` 비인증 조회 유지 — **PASS** (기존 RBAC 비범위 결정과 일관)
6. `simulate_mes_wms.py` 전체 흐름 정상 동작 — **PASS** (TestClient로 로그인→생산오더→작업지시→
   MES/WMS 웹훅 전체 시퀀스 재현해 확인. 실제 uvicorn 프로세스를 백그라운드로 띄우는 방식은 이번
   샌드박스 환경에서 안정적이지 않아, 동일 API 호출 시퀀스를 TestClient로 재현하는 방식으로 대체
   검증함 — 사용자 환경에서 실제 `uvicorn` + `python3 simulate_mes_wms.py`로 최종 재확인 권장)

## 발견 및 수정한 버그 (이번 작업 범위와 직접 연관)
- **`simulate_mes_wms.py`가 RBAC 이후 깨져 있었음**: 생산오더/작업지시 생성 엔드포인트가 RBAC로
  보호되는데 시뮬레이터에 로그인 로직이 없었음 → 생산담당 데모 계정 로그인 후 Authorization 헤더
  추가.
- **`simulate_mes_wms.py`의 창고 매칭이 데이터셋 임포트 시 깨져 있었음**: 한글 부분일치("완제품"/
  "원자재")로 찾고 있었는데 prototype_dataset은 영어 창고명을 사용 → 기존 `warehouse_type` 컬럼
  기반 매칭으로 수정.

## 설계상 의도적 비범위 (task-plan에 사전 명시)
- OAuth2/JWT 전환은 실운영 후보로 이월
- API Key 발급/회전 관리 UI 없음(데모 키 고정, README에 명시)
- API Key는 세션 토큰과 동일하게 평문 저장(해시화하지 않음 — RBAC 때와 같은 절충)

## 검증 방법
- `/tmp` 임시 복사본에서 `with TestClient(app) as client:`로 401/403/200 케이스 전부 확인.
- 실제 uvicorn 백그라운드 기동은 샌드박스 환경 제약으로 반복 실패(exit 143, 타임아웃 추정) —
  TestClient로 동일 시퀀스를 재현해 대체 검증. 사용자 로컬 환경에서는 정상적으로 백그라운드
  프로세스 기동이 가능하므로 실제 `python3 simulate_mes_wms.py` 실행으로 최종 확인 권장.
- 사용자의 실제 라이브 DB(erp.db)는 건드리지 않음. 스키마 변경(`integration_api_key` 신규 테이블)이
  있어 RBAC/LOT 작업 때와 동일하게 `app/erp.db` 삭제 후 재기동 필요.
