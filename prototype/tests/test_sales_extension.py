"""v9: 01 Sales Management 확장 — 가격정책/견적/판매계약/반품/서비스오더/채권/실적/손익/KPI."""

FG_MATERIAL_ID = 1
CUSTOMER_ID = 1


def _inventory_qty(client, headers, material_id, warehouse_id):
    """GET /api/inventory는 필터 파라미터가 없어 전체 목록을 반환한다 — 클라이언트 측에서 골라낸다."""
    rows = client.get("/api/inventory", headers=headers).json()
    match = next((r for r in rows if r["material_id"] == material_id and r["warehouse_id"] == warehouse_id), None)
    return match["qty"] if match else 0


def test_price_policy_create_and_lookup(client, tokens):
    r = client.post(
        "/api/price-policies", json={"material_id": FG_MATERIAL_ID, "unit_price": 777},
        headers=tokens["sales"],
    )
    assert r.status_code == 200

    r = client.get(f"/api/price-policies/lookup?material_id={FG_MATERIAL_ID}", headers=tokens["sales"])
    assert r.status_code == 200
    assert r.json()["unit_price"] == 777


def test_price_policy_lookup_no_match_returns_none(client, tokens):
    r = client.get("/api/price-policies/lookup?material_id=999999", headers=tokens["sales"])
    assert r.status_code == 200
    assert r.json()["unit_price"] is None


def test_quotation_lifecycle_create_approve_convert(client, tokens):
    r = client.post(
        "/api/quotations",
        json={"customer_id": CUSTOMER_ID, "lines": [{"material_id": FG_MATERIAL_ID, "qty": 5, "unit_price": 1000}]},
        headers=tokens["sales"],
    )
    assert r.status_code == 200
    quotation_id = r.json()["quotation_id"]

    detail = client.get(f"/api/quotations/{quotation_id}", headers=tokens["sales"])
    assert detail.status_code == 200
    assert detail.json()["status"] == "DRAFT"
    assert len(detail.json()["lines"]) == 1

    # 승인 전 전환 시도 -> 400
    early = client.post(f"/api/quotations/{quotation_id}/convert-to-order", headers=tokens["sales"])
    assert early.status_code == 400

    approvals = client.get("/api/approvals", headers=tokens["admin"]).json()
    wf = next(a for a in approvals if a["doc_type"] == "QUOTATION" and a["doc_id"] == quotation_id)
    decide = client.post(
        f"/api/approvals/{wf['workflow_id']}/decision", json={"status": "APPROVED"}, headers=tokens["admin"],
    )
    assert decide.status_code == 200

    convert = client.post(f"/api/quotations/{quotation_id}/convert-to-order", headers=tokens["sales"])
    assert convert.status_code == 200
    so_id = convert.json()["so_id"]

    so = client.get(f"/api/sales-orders/{so_id}", headers=tokens["sales"]).json()
    assert so["lines"][0]["qty"] == 5
    assert so["lines"][0]["price"] == 1000


def test_sales_contract_create(client, tokens):
    r = client.post(
        "/api/sales-contracts", json={"customer_id": CUSTOMER_ID, "start_date": "2026-01-01"},
        headers=tokens["sales"],
    )
    assert r.status_code == 200
    contracts = client.get("/api/sales-contracts", headers=tokens["sales"]).json()
    assert any(c["contract_id"] == r.json()["contract_id"] for c in contracts)


def test_sales_return_approval_restores_inventory(client, tokens, warehouse_id):
    so = client.post(
        "/api/sales-orders",
        json={"customer_id": CUSTOMER_ID, "lines": [{"material_id": FG_MATERIAL_ID, "qty": 3, "price": 100}]},
        headers=tokens["sales"],
    ).json()
    so_id = so["so_id"]
    deliver = client.post(
        f"/api/sales-orders/{so_id}/deliveries", json={"warehouse_id": warehouse_id}, headers=tokens["sales"],
    )
    assert deliver.status_code == 200

    qty_before = _inventory_qty(client, tokens["admin"], FG_MATERIAL_ID, warehouse_id)

    ret = client.post(
        "/api/sales-returns",
        json={"so_id": so_id, "reason": "defect", "lines": [{"material_id": FG_MATERIAL_ID, "qty": 2, "warehouse_id": warehouse_id}]},
        headers=tokens["sales"],
    )
    assert ret.status_code == 200
    return_id = ret.json()["return_id"]

    approvals = client.get("/api/approvals", headers=tokens["admin"]).json()
    wf = next(a for a in approvals if a["doc_type"] == "SALES_RETURN" and a["doc_id"] == return_id)
    decide = client.post(
        f"/api/approvals/{wf['workflow_id']}/decision", json={"status": "APPROVED"}, headers=tokens["admin"],
    )
    assert decide.status_code == 200

    qty_after = _inventory_qty(client, tokens["admin"], FG_MATERIAL_ID, warehouse_id)
    assert qty_after == qty_before + 2

    log = client.get("/api/audit-log", headers=tokens["admin"]).json()
    assert any(e["entity"] == "sales_return" and e["entity_id"] == return_id for e in log)


def test_sales_return_rejection_does_not_restore_inventory(client, tokens, warehouse_id):
    so = client.post(
        "/api/sales-orders",
        json={"customer_id": CUSTOMER_ID, "lines": [{"material_id": FG_MATERIAL_ID, "qty": 1, "price": 100}]},
        headers=tokens["sales"],
    ).json()
    so_id = so["so_id"]
    client.post(f"/api/sales-orders/{so_id}/deliveries", json={"warehouse_id": warehouse_id}, headers=tokens["sales"])

    qty_before = _inventory_qty(client, tokens["admin"], FG_MATERIAL_ID, warehouse_id)

    ret = client.post(
        "/api/sales-returns",
        json={"so_id": so_id, "lines": [{"material_id": FG_MATERIAL_ID, "qty": 1, "warehouse_id": warehouse_id}]},
        headers=tokens["sales"],
    )
    return_id = ret.json()["return_id"]
    approvals = client.get("/api/approvals", headers=tokens["admin"]).json()
    wf = next(a for a in approvals if a["doc_type"] == "SALES_RETURN" and a["doc_id"] == return_id)
    client.post(f"/api/approvals/{wf['workflow_id']}/decision", json={"status": "REJECTED"}, headers=tokens["admin"])

    qty_after = _inventory_qty(client, tokens["admin"], FG_MATERIAL_ID, warehouse_id)
    assert qty_after == qty_before


def test_service_order_lifecycle(client, tokens):
    r = client.post(
        "/api/service-orders", json={"customer_id": CUSTOMER_ID, "material_id": FG_MATERIAL_ID, "symptom": "no power"},
        headers=tokens["sales"],
    )
    assert r.status_code == 200
    service_order_id = r.json()["service_order_id"]

    r = client.post(f"/api/service-orders/{service_order_id}/status", json={"status": "COMPLETED"}, headers=tokens["sales"])
    assert r.status_code == 200

    r = client.post(f"/api/service-orders/{service_order_id}/status", json={"status": "NOT_A_STATUS"}, headers=tokens["sales"])
    assert r.status_code == 400


def test_ar_receivables_shape(client, tokens):
    r = client.get("/api/ar/receivables", headers=tokens["admin"])
    assert r.status_code == 200
    for row in r.json():
        assert "due_date" in row and "overdue" in row


def test_sales_performance_group_by_variants(client, tokens):
    for gb in ("customer", "material", "month"):
        r = client.get(f"/api/sales/performance?group_by={gb}", headers=tokens["admin"])
        assert r.status_code == 200


def test_sales_profitability_shape(client, tokens):
    r = client.get("/api/sales/profitability?group_by=customer", headers=tokens["admin"])
    assert r.status_code == 200
    for row in r.json():
        assert "profit" in row


def test_sales_kpi_shape(client, tokens):
    r = client.get("/api/sales/kpi", headers=tokens["admin"])
    assert r.status_code == 200
    body = r.json()
    for key in ("revenue_this_month", "open_backlog", "orders_this_month", "customers_this_month"):
        assert key in body
