"""v10: 02 Supply Chain Management 신규 — 전부 조회 전용(GET) 엔드포인트 검증."""


def test_demand_forecast_accuracy_shape(client, tokens):
    r = client.get("/api/scm/demand-forecast/accuracy", headers=tokens["admin"])
    assert r.status_code == 200
    for row in r.json():
        assert "avg_mape" in row and "direction" in row


def test_sop_gap_matches_same_month_period_format(client, tokens):
    """수요예측(forecast_month)과 생산계획(production_order.order_date)의 월 포맷이 일치해야
    실제로 매칭되어 gap이 계산된다 — 최초 구현 시 포맷 불일치(YYYY-MM-DD vs YYYY-MM)로 항상
    planned_qty=0이 되는 버그가 있었다(수동 검증 중 발견, substr(forecast_month,1,7)로 수정)."""
    r = client.get("/api/scm/sop", headers=tokens["admin"])
    assert r.status_code == 200
    rows = r.json()
    assert rows
    for row in rows[:5]:
        assert len(row["period"]) == 7  # "YYYY-MM"
    # 최소 한 건은 실제 매칭(planned_qty>0)되어야 한다 — 시드 데이터셋에 생산오더가 있으므로.
    assert any(row["planned_qty"] > 0 for row in rows)


def test_supply_plan_shape(client, tokens):
    r = client.get("/api/scm/supply-plan", headers=tokens["admin"])
    assert r.status_code == 200
    for row in r.json():
        assert row["available_qty"] == row["on_hand_qty"] + row["incoming_po_qty"]


def test_mps_view_shape(client, tokens):
    r = client.get("/api/scm/mps", headers=tokens["admin"])
    assert r.status_code == 200
    for row in r.json():
        assert len(row["period"]) == 7


def test_inventory_plan_shape(client, tokens):
    r = client.get("/api/scm/inventory-plan", headers=tokens["admin"])
    assert r.status_code == 200
    for row in r.json():
        assert row["risk"] in ("LOW_STOCK", "OK")


def test_supply_risk_shape(client, tokens):
    r = client.get("/api/scm/supply-risk", headers=tokens["admin"])
    assert r.status_code == 200
    for row in r.json():
        assert row["risk_level"] in ("HIGH", "MEDIUM", "LOW")


def test_control_tower_shape(client, tokens):
    r = client.get("/api/scm/control-tower", headers=tokens["admin"])
    assert r.status_code == 200
    body = r.json()
    for key in ("below_reorder_point_count", "low_stock_count", "high_risk_vendor_count", "vendor_count"):
        assert key in body


def test_scm_requires_login(client):
    r = client.get("/api/scm/control-tower")
    assert r.status_code == 401
