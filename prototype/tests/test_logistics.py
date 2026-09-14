"""v12: 04 Logistics Management 확장 — 창고Location/컨테이너/운송/물류비정산/수출현황/보험·클레임/Dashboard."""
import pytest


@pytest.fixture(scope="module")
def shipment_id(client, tokens):
    """시드 데이터셋의 출하 중 첫 건 — 운송/컨테이너/클레임 연결용."""
    rows = client.get("/api/logistics/export-status", headers=tokens["admin"]).json()
    assert len(rows) > 0, "시드 출하 데이터가 필요함"
    return rows[0]["shipment_id"]


# ---------- 창고 Location ----------

def test_location_create_and_list(client, tokens, warehouse_id):
    r = client.post(
        "/api/logistics/locations",
        json={"warehouse_id": warehouse_id, "code": "A-01-01", "name": "A동 1랙 1단", "location_type": "BIN"},
        headers=tokens["admin"],
    )
    assert r.status_code == 200
    rows = client.get("/api/logistics/locations", headers=tokens["sales"]).json()
    row = next(l for l in rows if l["location_id"] == r.json()["location_id"])
    assert row["code"] == "A-01-01"
    assert row["warehouse_name"]


def test_location_duplicate_code_400(client, tokens, warehouse_id):
    body = {"warehouse_id": warehouse_id, "code": "DUP-01"}
    assert client.post("/api/logistics/locations", json=body, headers=tokens["admin"]).status_code == 200
    assert client.post("/api/logistics/locations", json=body, headers=tokens["admin"]).status_code == 400


def test_location_unknown_warehouse_404(client, tokens):
    r = client.post(
        "/api/logistics/locations", json={"warehouse_id": 999999, "code": "X-01"}, headers=tokens["admin"],
    )
    assert r.status_code == 404


def test_location_create_requires_admin(client, tokens, warehouse_id):
    r = client.post(
        "/api/logistics/locations", json={"warehouse_id": warehouse_id, "code": "B-01"}, headers=tokens["sales"],
    )
    assert r.status_code == 403


# ---------- 컨테이너 ----------

def test_container_create_and_status(client, tokens, shipment_id):
    r = client.post(
        "/api/logistics/containers",
        json={"container_no": "TCLU1234567", "container_type": "40FT", "shipment_id": shipment_id},
        headers=tokens["sales"],
    )
    assert r.status_code == 200
    cid = r.json()["container_id"]
    assert client.post(
        f"/api/logistics/containers/{cid}/status", json={"status": "SEALED"}, headers=tokens["sales"],
    ).status_code == 200
    rows = client.get("/api/logistics/containers", headers=tokens["sales"]).json()
    row = next(c for c in rows if c["container_id"] == cid)
    assert row["status"] == "SEALED"
    assert row["shipment_no"] is not None


def test_container_invalid_status_400(client, tokens):
    r = client.post("/api/logistics/containers", json={"container_no": "MSKU0000001"}, headers=tokens["sales"])
    cid = r.json()["container_id"]
    assert client.post(
        f"/api/logistics/containers/{cid}/status", json={"status": "FLYING"}, headers=tokens["sales"],
    ).status_code == 400


# ---------- 운송관리 ----------

def test_transport_create_and_status(client, tokens, shipment_id):
    r = client.post(
        "/api/logistics/transports",
        json={"shipment_id": shipment_id, "carrier": "한진", "vehicle_no": "12가3456", "freight_cost": 150000},
        headers=tokens["sales"],
    )
    assert r.status_code == 200
    tid = r.json()["transport_id"]
    assert client.post(
        f"/api/logistics/transports/{tid}/status", json={"status": "IN_TRANSIT"}, headers=tokens["sales"],
    ).status_code == 200
    rows = client.get("/api/logistics/transports", headers=tokens["admin"]).json()
    row = next(t for t in rows if t["transport_id"] == tid)
    assert row["status"] == "IN_TRANSIT"
    assert row["transport_date"]  # 서버 로컬 날짜 명시 입력(UTC 기본값 미사용)


def test_transport_unknown_shipment_404(client, tokens):
    r = client.post(
        "/api/logistics/transports", json={"shipment_id": 999999, "carrier": "한진"}, headers=tokens["sales"],
    )
    assert r.status_code == 404


# ---------- 물류비 정산 ----------

def test_cost_create_settle_creates_accounting_doc(client, tokens, shipment_id):
    r = client.post(
        "/api/logistics/costs",
        json={"cost_type": "FREIGHT", "amount": 250000, "shipment_id": shipment_id, "notes": "해상운임"},
        headers=tokens["sales"],
    )
    assert r.status_code == 200
    cost_id = r.json()["cost_id"]

    settle = client.post(f"/api/logistics/costs/{cost_id}/settle", headers=tokens["admin"])
    assert settle.status_code == 200
    doc_id = settle.json()["acct_doc_id"]
    assert doc_id is not None

    # 전표가 실제로 생성되고 차대변이 일치하는지(5100 물류비 / 2000 매입채무)
    docs = client.get("/api/accounting/documents", headers=tokens["admin"]).json()
    doc = next(d for d in docs if d["doc_id"] == doc_id)
    assert doc["doc_type"] == "LOGISTICS_COST"

    rows = client.get("/api/logistics/costs", headers=tokens["admin"]).json()
    row = next(c for c in rows if c["cost_id"] == cost_id)
    assert row["settled"] == 1
    assert row["acct_doc_id"] == doc_id


def test_cost_double_settle_400(client, tokens):
    cost_id = client.post(
        "/api/logistics/costs", json={"cost_type": "HANDLING", "amount": 10000}, headers=tokens["sales"],
    ).json()["cost_id"]
    assert client.post(f"/api/logistics/costs/{cost_id}/settle", headers=tokens["admin"]).status_code == 200
    assert client.post(f"/api/logistics/costs/{cost_id}/settle", headers=tokens["admin"]).status_code == 400


def test_cost_settle_requires_admin(client, tokens):
    cost_id = client.post(
        "/api/logistics/costs", json={"cost_type": "OTHER", "amount": 5000}, headers=tokens["sales"],
    ).json()["cost_id"]
    assert client.post(f"/api/logistics/costs/{cost_id}/settle", headers=tokens["sales"]).status_code == 403


def test_cost_invalid_type_and_amount_400(client, tokens):
    assert client.post(
        "/api/logistics/costs", json={"cost_type": "BRIBE", "amount": 100}, headers=tokens["sales"],
    ).status_code == 400
    assert client.post(
        "/api/logistics/costs", json={"cost_type": "FREIGHT", "amount": -5}, headers=tokens["sales"],
    ).status_code == 400


# ---------- 보험·클레임 ----------

def test_insurance_create_and_list(client, tokens):
    r = client.post(
        "/api/logistics/insurance",
        json={"policy_no": "MAR-2026-001", "insurer": "한국해상보험", "coverage": "적하보험 전위험담보"},
        headers=tokens["sales"],
    )
    assert r.status_code == 200
    rows = client.get("/api/logistics/insurance", headers=tokens["admin"]).json()
    assert any(p["policy_id"] == r.json()["policy_id"] for p in rows)


def test_claim_create_and_status(client, tokens, shipment_id):
    r = client.post(
        "/api/logistics/claims",
        json={"claim_type": "DAMAGE", "shipment_id": shipment_id, "amount": 300000, "notes": "포장 파손"},
        headers=tokens["sales"],
    )
    assert r.status_code == 200
    claim_id = r.json()["claim_id"]
    assert client.post(
        f"/api/logistics/claims/{claim_id}/status", json={"status": "RESOLVED"}, headers=tokens["sales"],
    ).status_code == 200
    rows = client.get("/api/logistics/claims", headers=tokens["admin"]).json()
    assert next(c for c in rows if c["claim_id"] == claim_id)["status"] == "RESOLVED"


def test_claim_invalid_type_400(client, tokens):
    assert client.post(
        "/api/logistics/claims", json={"claim_type": "MOOD"}, headers=tokens["sales"],
    ).status_code == 400


# ---------- 수출현황 / Dashboard / 인증 ----------

def test_export_status_shape(client, tokens):
    rows = client.get("/api/logistics/export-status", headers=tokens["sales"]).json()
    assert len(rows) > 0
    for key in ("shipment_id", "shipment_date", "transport_count", "container_count"):
        assert key in rows[0]


def test_dashboard_shape(client, tokens):
    d = client.get("/api/logistics/dashboard", headers=tokens["production"]).json()
    for key in (
        "location_count", "container_active", "transport_in_transit",
        "unsettled_cost_count", "unsettled_cost_amount", "open_claim_count", "shipment_count",
    ):
        assert key in d


def test_logistics_requires_login(client):
    assert client.get("/api/logistics/dashboard").status_code == 401
