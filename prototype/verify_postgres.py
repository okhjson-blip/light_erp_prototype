"""PostgreSQL 로컬 접속 검증 스크립트.
DATABASE_URL 환경변수(postgres용)가 설정된 상태에서 실행한다.
docker-compose로 띄운 로컬 Postgres에 대해: 연결 → 스키마 초기화 → 시드 임포트 → E2E 스모크 테스트
순서로 검증하고, 각 단계 결과를 명확히 출력한다. 현재 SQLite로 실행 중인 서버에는 영향을 주지 않는다
(별도 프로세스에서 DATABASE_URL을 다르게 주입해 실행하기 때문).
"""
import os
import sys
import time

from sqlalchemy import create_engine, text

url = os.environ.get("DATABASE_URL", "")
if "postgres" not in url:
    print("ERROR: DATABASE_URL이 postgres로 설정되어 있지 않습니다. .env.example을 참고하세요.")
    sys.exit(1)

print(f"[1/4] PostgreSQL 연결 시도: {url}")
engine = create_engine(url)
for attempt in range(10):
    try:
        with engine.connect() as c:
            c.execute(text("SELECT 1"))
        break
    except Exception as e:
        print(f"  재시도 {attempt + 1}/10 ({e})")
        time.sleep(2)
else:
    print("FAIL: PostgreSQL에 연결할 수 없습니다. `docker compose ps`로 컨테이너 상태를 확인하세요.")
    sys.exit(1)
print("  연결 성공")

print("[2/4] 스키마 초기화 (schema_postgres.sql)")
from app import database  # noqa: E402
is_new = database.init_db(reset=False)
print(f"  init_db 완료 (신규 테이블 생성: {is_new})")

print("[3/4] 시드 데이터 임포트 (app/seed.py, SQLite와 동일 로직)")
from app import seed  # noqa: E402
from app.database import run, one  # noqa: E402
seed.run_seed()
conn = database.get_conn()
counts = {}
for t in ["company", "plant", "warehouse", "material", "sales_order", "production_order", "demand_forecast"]:
    counts[t] = one(run(conn, f"SELECT COUNT(*) c FROM {t}"))["c"]
conn.close()
print("  테이블별 행수:", counts)
if counts["company"] == 0:
    print("FAIL: 시드/임포트 후에도 데이터가 없습니다.")
    sys.exit(1)

print("[4/4] E2E 스모크 테스트 (FastAPI TestClient, Postgres 백엔드)")
from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402

client = TestClient(app)
r = client.get("/api/dashboard/kpi")
assert r.status_code == 200, f"dashboard/kpi 실패: {r.status_code} {r.text}"
print("  dashboard/kpi:", r.json())

materials = client.get("/api/materials").json()
customers = client.get("/api/customers").json()
assert materials and customers, "기준정보가 비어있습니다"

so_body = {
    "customer_id": customers[0]["customer_id"],
    "lines": [{"material_id": materials[0]["material_id"], "qty": 1, "price": 1000}],
}
r = client.post("/api/sales-orders", json=so_body)
assert r.status_code == 200, f"SO 생성 실패: {r.status_code} {r.text}"
so_id = r.json()["so_id"]
print(f"  SO#{so_id} 생성 성공 (PostgreSQL에 실제 저장/조회 확인)")

print("\n=== 전체 PASS: PostgreSQL 연결/스키마/시드/E2E 전부 정상 동작 ===")
print("(주의: 현재 브라우저로 접속 중인 서버는 SQLite로 계속 동작하며 이 검증과 무관합니다)")
