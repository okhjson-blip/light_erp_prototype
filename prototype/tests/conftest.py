"""pytest 공용 fixture.
실제 개발용 app/erp.db는 절대 건드리지 않고, 테스트 전용 임시 SQLite 파일을 사용한다
(DATABASE_URL을 app.* 모듈 임포트 전에 설정해야 하므로 이 파일 최상단에서 처리).
"""
import os
import tempfile
from pathlib import Path

import pytest

_TMP_DB = Path(tempfile.gettempdir()) / "standard_erp_pytest.db"
if _TMP_DB.exists():
    _TMP_DB.unlink()
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP_DB}"

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

DEMO_PASSWORD = "demo1234"


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def db_path():
    """API로 표현하기 어려운 예외 상황(버그 시뮬레이션 등)을 검증할 때만 직접 DB를 조작하기 위함."""
    return _TMP_DB


def _login(client, email):
    r = client.post("/api/auth/login", json={"email": email, "password": DEMO_PASSWORD})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _login_full(client, email):
    """access_token/refresh_token 둘 다 필요한 테스트(refresh/logout 시나리오)용."""
    r = client.post("/api/auth/login", json={"email": email, "password": DEMO_PASSWORD})
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture(scope="session")
def tokens(client):
    return {
        "admin": _login(client, "admin@standard-erp.local"),
        "sales": _login(client, "sales@standard-erp.local"),
        "purchase": _login(client, "purchase@standard-erp.local"),
        "production": _login(client, "production@standard-erp.local"),
    }


@pytest.fixture(scope="session")
def plant_id(client, tokens):
    return client.get("/api/plants", headers=tokens["admin"]).json()[0]["plant_id"]


@pytest.fixture(scope="session")
def warehouse_id(client, tokens):
    return client.get("/api/warehouses", headers=tokens["admin"]).json()[0]["warehouse_id"]


# 시드 데이터셋의 FG-1001(material_id=1)은 BOM에 RM-0001(material_id=6)을 1:1로 사용한다
# (app/prototype_dataset/bom_items.csv 기준 — dataset 임포트 실패 시 데모시드로 대체되므로
# 실제 환경에 따라 이 가정이 깨질 수 있어 각 테스트가 아니라 fixture 한 곳에서만 하드코딩한다).
FG_MATERIAL_ID = 1
RM_MATERIAL_ID = 6
VENDOR_ID = 1
CUSTOMER_ID = 1


@pytest.fixture(scope="session")
def rm_lot(client, tokens, warehouse_id):
    """RM 원자재를 500개 입고 처리해 새 LOT을 만들고 그 정보를 반환한다."""
    purchase, admin = tokens["purchase"], tokens["admin"]
    pr = client.post(
        "/api/purchase-requisitions",
        json={"lines": [{"material_id": RM_MATERIAL_ID, "qty": 500}]},
        headers=purchase,
    )
    assert pr.status_code == 200, pr.text
    pr_id = pr.json()["pr_id"]
    approvals = client.get("/api/approvals", headers=admin).json()
    wf_id = next(a["workflow_id"] for a in approvals if a["doc_type"] == "PR" and a["doc_id"] == pr_id)
    assert client.post(f"/api/approvals/{wf_id}/decision", json={"status": "APPROVED"}, headers=admin).status_code == 200

    po = client.post(
        "/api/purchase-orders",
        json={"vendor_id": VENDOR_ID, "pr_id": pr_id, "lines": [{"material_id": RM_MATERIAL_ID, "qty": 500, "price": 10}]},
        headers=purchase,
    )
    assert po.status_code == 200, po.text
    po_id = po.json()["po_id"]
    gr = client.post(f"/api/purchase-orders/{po_id}/goods-receipts", json={"warehouse_id": warehouse_id}, headers=purchase)
    assert gr.status_code == 200, gr.text

    lots = client.get(f"/api/lots?material_id={RM_MATERIAL_ID}", headers=admin).json()
    lot = next(l for l in lots if l["warehouse_id"] == warehouse_id and l["qty"] == 500)
    return lot


@pytest.fixture(scope="session")
def fg_lot_with_serials(client, tokens, plant_id, warehouse_id, rm_lot):
    """완제품 생산실적(시리얼 생성 포함)을 만들어 LOT+시리얼 목록을 반환한다.
    rm_lot에 의존 — BOM 소요로 RM LOT을 소진하는 시나리오를 함께 검증하기 위함."""
    production = tokens["production"]
    po_prod = client.post(
        "/api/production-orders",
        json={"material_id": FG_MATERIAL_ID, "plant_id": plant_id, "qty": 8},
        headers=production,
    )
    assert po_prod.status_code == 200, po_prod.text
    prod_order_id = po_prod.json()["prod_order_id"]
    wo = client.post(f"/api/production-orders/{prod_order_id}/work-orders", json={}, headers=production)
    assert wo.status_code == 200, wo.text
    wo_id = wo.json()["work_order_id"]
    result = client.post(
        f"/api/work-orders/{wo_id}/results",
        json={"qty_good": 8, "warehouse_id": warehouse_id, "generate_serials": True},
        headers=production,
    )
    assert result.status_code == 200, result.text
    body = result.json()
    assert body["lot"] is not None
    assert len(body["serials"]) == 8
    return {"lot": body["lot"], "serials": body["serials"], "prod_order_id": prod_order_id}
