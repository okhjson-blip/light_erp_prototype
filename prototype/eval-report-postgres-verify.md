# Evaluation Report — PostgreSQL 로컬 접속 검증

```json
{
  "pass": true,
  "score": 95,
  "independence_check": {"existing_files_modified": ["docker-compose.yml", ".env.example", "README.md", "requirements.txt"], "db_schema_changed": false},
  "failures": [],
  "harness_update_needed": false
}
```

v2 eval-report(88/100)에서 "샌드박스에 root/Docker 권한이 없어 실제 PostgreSQL 접속 미검증"으로
남겨뒀던 항목을 사용자 로컬 환경(Docker 설치됨)에서 최종 검증 완료.

## 성공 기준 대비 결과
1. PostgreSQL 연결 — **PASS** (`postgresql+psycopg2://erp:erp_local_dev@127.0.0.1:5433/standard_erp`)
2. 스키마 초기화(schema_postgres.sql) — **PASS** (신규 테이블 생성 확인, SQLite와 동일 DDL 경로로 문제 없이 적용)
3. 시드/데이터셋 임포트 — **PASS** (테이블별 행수가 SQLite 버전 eval-report-dataset-import.md와
   정확히 일치: company 4, plant 5, warehouse 8, material 15, sales_order 216, production_order 180,
   demand_forecast 60 — `app/seed.py`의 코드가 SQLite/PostgreSQL 양쪽에 동일하게 동작함을 확인)
4. E2E 스모크 테스트(FastAPI TestClient로 PostgreSQL 백엔드에 실제 SO 생성) — **PASS**

## 발견 및 해결한 이슈 (검증 과정 자체가 가치 있었던 부분)
1. **호스트 포트 충돌**: 사용자 Mac에 이미 네이티브 Postgres 프로세스가 `127.0.0.1:5432`/`[::1]:5432`를
   선점하고 있어, docker-compose의 `5432:5432` 매핑이 컨테이너 자체는 정상 기동해도 호스트에서의 접속은
   기존 프로세스로 가로채이는 문제 발생(`role "erp" does not exist` 오류로 나타남). `docker-compose.yml`
   포트를 `5433:5432`로 변경해 해결. `.env.example`/README도 5433으로 갱신.
2. **볼륨 재사용 문제**: Postgres는 데이터 볼륨이 비어있을 때만 `POSTGRES_USER`/`PASSWORD`로 초기 계정을
   생성하므로, 이전에 다른 설정으로 한 번이라도 뜬 적 있는 볼륨이 남아있으면 이후 계속 계정이 없는 채로
   남는다. `verify_postgres.command`가 매 실행마다 `docker compose down -v`로 볼륨을 초기화한 뒤
   새로 띄우도록 해 idempotent하게 만듦.
3. **테스트 의존성 누락**: `requirements.txt`에 `httpx`가 없어 최신 Starlette의 `TestClient`가
   임포트 단계에서 실패. `httpx==0.27.2` 추가로 해결(런타임 동작에는 영향 없음 — 테스트 전용 의존성).

## 판단
v2 task-plan에서 명시했던 "PostgreSQL 로컬 접속 검증 필요" 조건이 충족되어, **프로토타입 v1~v2 범위는
전체 완료로 확정**한다. SQLite/PostgreSQL 양쪽에서 스키마·시드·API가 동일하게 동작함을 실제 환경에서
확인했으므로, 이후 운영 환경 전환 시 `DATABASE_URL`만 설정하면 된다는 v2 설계 전제가 실증되었다.

## 알려진 제약 (v3 이후로 이월)
- RBAC(역할 기반 접근 제어) 강화, WMS/QMS LOT·Serial 추적, MES 인증(API Key/OAuth) — 애초에 v1~v2
  스코프 밖으로 명시했던 항목, 계속 v3 이후 과제로 유지.
- verify_postgres.command로 띄운 로컬 Postgres는 검증용 — 실제 상시 운영 전환 시에는 프로덕션급
  자격증명/백업 정책이 별도로 필요함(이번 작업 범위 아님).
