"""v11: 03 Procurement Management 확장 — 공급업체평가/구매계약/카테고리별구매/PO구분/통관/실적/KPI."""

VENDOR_ID = 1
RM_MATERIAL_ID = 6


def test_vendor_evaluation_create_and_summary(client, tokens):
    r = client.post(
        "/api/vendor-evaluations",
        json={"vendor_id": VENDOR_ID, "delivery_score": 90, "quality_score": 80, "price_score": 70, "notes": "정기평가"},
        headers=tokens["purchase"],
    )
    assert r.status_code == 200
    evals = client.get("/api/vendor-evaluations", headers=tokens["admin"]).json()
    row = next(e for e in evals if e["eval_id"] == r.json()["eval_id"])
    assert row["total_score"] == 80.0

    summary = client.get("/api/vendor-evaluations/summary", headers=tokens["admin"]).json()
    vendor_row = next(s for s in summary if s["vendor_id"] == VENDOR_ID)
    assert vendor_row["eval_count"] >= 1
    assert vendor_row["grade"] in ("A", "B", "C")


def test_vendor_evaluation_unknown_vendor_404(client, tokens):
    r = client.post(
        "/api/vendor-evaluations",
        json={"vendor_id": 999999, "delivery_score": 50, "quality_score": 50, "price_score": 50},
        headers=tokens["purchase"],
    )
    assert r.status_code == 404


def test_purchase_contract_create(client, tokens):
    r = client.post(
        "/api/purchase-contracts", json={"vendor_id": VENDOR_ID, "start_date": "2026-01-01"},
        headers=tokens["purchase"],
    )
    assert r.status_code == 200
    contracts = client.get("/api/purchase-contracts", headers=tokens["purchase"]).json()
    assert any(c["contract_id"] == r.json()["contract_id"] for c in contracts)


def test_purchase_by_category_shape(client, tokens):
    r = client.get("/api/purchase/by-category", headers=tokens["admin"])
    assert r.status_code == 200
    for row in r.json():
        assert "category" in row and "total_amount" in row


def test_purchase_by_category_filter(client, tokens):
    r = client.get("/api/purchase/by-category?category=RM", headers=tokens["admin"])
    assert r.status_code == 200
    for row in r.json():
        assert row["category"] == "RM"


def test_po_type_default_and_explicit(client, tokens):
    r = client.post(
        "/api/purchase-orders",
        json={"vendor_id": VENDOR_ID, "lines": [{"material_id": RM_MATERIAL_ID, "qty": 10, "price": 5}]},
        headers=tokens["purchase"],
    )
    assert r.status_code == 200
    po_id = r.json()["po_id"]
    po = client.get(f"/api/purchase-orders/{po_id}", headers=tokens["purchase"]).json()
    assert po["po_type"] == "STANDARD"

    r2 = client.post(
        "/api/purchase-orders",
        json={"vendor_id": VENDOR_ID, "po_type": "OUTSOURCING", "lines": [{"material_id": RM_MATERIAL_ID, "qty": 5, "price": 5}]},
        headers=tokens["purchase"],
    )
    assert r2.status_code == 200
    po2 = client.get(f"/api/purchase-orders/{r2.json()['po_id']}", headers=tokens["purchase"]).json()
    assert po2["po_type"] == "OUTSOURCING"


def test_po_type_invalid_rejected(client, tokens):
    r = client.post(
        "/api/purchase-orders",
        json={"vendor_id": VENDOR_ID, "po_type": "NOT_A_TYPE", "lines": [{"material_id": RM_MATERIAL_ID, "qty": 1, "price": 1}]},
        headers=tokens["purchase"],
    )
    assert r.status_code == 400


def test_import_customs_lifecycle(client, tokens):
    po = client.post(
        "/api/purchase-orders",
        json={"vendor_id": VENDOR_ID, "lines": [{"material_id": RM_MATERIAL_ID, "qty": 20, "price": 5}]},
        headers=tokens["purchase"],
    ).json()
    po_id = po["po_id"]

    r = client.post("/api/import-customs", json={"po_id": po_id, "declaration_no": "DECL-001"}, headers=tokens["purchase"])
    assert r.status_code == 200
    customs_id = r.json()["customs_id"]

    records = client.get("/api/import-customs", headers=tokens["purchase"]).json()
    row = next(rec for rec in records if rec["customs_id"] == customs_id)
    assert row["customs_status"] == "PENDING"
    assert row["po_id"] == po_id

    upd = client.post(f"/api/import-customs/{customs_id}/status", json={"customs_status": "CLEARED"}, headers=tokens["purchase"])
    assert upd.status_code == 200

    bad = client.post(f"/api/import-customs/{customs_id}/status", json={"customs_status": "NOT_A_STATUS"}, headers=tokens["purchase"])
    assert bad.status_code == 400


def test_import_customs_unknown_po_404(client, tokens):
    r = client.post("/api/import-customs", json={"po_id": 999999}, headers=tokens["purchase"])
    assert r.status_code == 404


def test_purchase_performance_group_by_variants(client, tokens):
    for gb in ("vendor", "material", "month"):
        r = client.get(f"/api/purchase/performance?group_by={gb}", headers=tokens["admin"])
        assert r.status_code == 200


def test_purchase_kpi_shape(client, tokens):
    r = client.get("/api/purchase/kpi", headers=tokens["admin"])
    assert r.status_code == 200
    body = r.json()
    for key in ("open_pr_count", "open_po_count", "spend_this_month", "vendor_count", "avg_vendor_score"):
        assert key in body


def test_procurement_ext_requires_login(client):
    r = client.get("/api/vendor-evaluations")
    assert r.status_code == 401
