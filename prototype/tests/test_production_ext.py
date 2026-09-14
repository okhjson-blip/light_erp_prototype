"""v13: 05 Production Management 확장 — MRP/외주생산/재작업/생산마감/OEE/생산Dashboard."""
import sqlite3

VENDOR_ID = 1
FG_MATERIAL_ID = 1


# ---------- MRP ----------

def test_mrp_shape_and_shortage_math(client, tokens):
    r = client.get("/api/production/mrp", headers=tokens["production"])
    assert r.status_code == 200
    body = r.json()
    assert body["period"]  # 시드 demand_forecast 존재
    assert len(body["rows"]) > 0
    row = body["rows"][0]
    for key in ("material_id", "name", "requirement", "onhand", "incoming", "shortage"):
        assert key in row
    # shortage = max(0, requirement - onhand - incoming)
    expected = max(0.0, round(row["requirement"] - row["onhand"] - row["incoming"], 2))
    assert abs(row["shortage"] - expected) < 0.01


# ---------- 외주생산 ----------

def test_outsourced_order_create_and_status(client, tokens, plant_id):
    r = client.post(
        "/api/production-orders",
        json={"material_id": FG_MATERIAL_ID, "plant_id": plant_id, "qty": 5,
              "is_outsourced": True, "vendor_id": VENDOR_ID},
        headers=tokens["production"],
    )
    assert r.status_code == 200
    prod_order_id = r.json()["prod_order_id"]
    rows = client.get("/api/production/outsourcing", headers=tokens["admin"]).json()
    row = next(o for o in rows if o["prod_order_id"] == prod_order_id)
    assert row["vendor_name"] is not None


def test_outsourced_requires_vendor_400(client, tokens, plant_id):
    r = client.post(
        "/api/production-orders",
        json={"material_id": FG_MATERIAL_ID, "plant_id": plant_id, "qty": 5, "is_outsourced": True},
        headers=tokens["production"],
    )
    assert r.status_code == 400


def test_outsourced_unknown_vendor_404(client, tokens, plant_id):
    r = client.post(
        "/api/production-orders",
        json={"material_id": FG_MATERIAL_ID, "plant_id": plant_id, "qty": 5,
              "is_outsourced": True, "vendor_id": 999999},
        headers=tokens["production"],
    )
    assert r.status_code == 404


# ---------- 재작업 ----------

def test_rework_full_flow_reworked(client, tokens, fg_lot_with_serials):
    """DEFECTIVE 등록 → 재작업 → 재투입(IN_STOCK 복귀). 시리얼 [3] 사용([0]~[2]는 test_serial_status 몫."""
    serial_no = fg_lot_with_serials["serials"][3]
    assert client.post(
        f"/api/serials/{serial_no}/status", json={"status": "DEFECTIVE"}, headers=tokens["production"],
    ).status_code == 200

    r = client.post(
        "/api/production/reworks", json={"serial_no": serial_no, "reason": "납땜 불량"},
        headers=tokens["production"],
    )
    assert r.status_code == 200
    rework_id = r.json()["rework_id"]

    # 진행 중 중복 등록 차단
    assert client.post(
        "/api/production/reworks", json={"serial_no": serial_no}, headers=tokens["production"],
    ).status_code == 400

    done = client.post(
        f"/api/production/reworks/{rework_id}/complete", json={"result": "REWORKED"},
        headers=tokens["production"],
    )
    assert done.status_code == 200
    assert done.json()["serial_status"] == "IN_STOCK"

    trace = client.get(f"/api/serials/{serial_no}/trace", headers=tokens["admin"]).json()
    assert trace["serial"]["status"] == "IN_STOCK"


def test_rework_scrap_flow(client, tokens, fg_lot_with_serials):
    serial_no = fg_lot_with_serials["serials"][4]
    client.post(f"/api/serials/{serial_no}/status", json={"status": "DEFECTIVE"}, headers=tokens["production"])
    rework_id = client.post(
        "/api/production/reworks", json={"serial_no": serial_no}, headers=tokens["production"],
    ).json()["rework_id"]
    done = client.post(
        f"/api/production/reworks/{rework_id}/complete", json={"result": "SCRAPPED"},
        headers=tokens["production"],
    )
    assert done.status_code == 200
    assert done.json()["serial_status"] == "SCRAPPED"


def test_rework_rejects_non_defective(client, tokens, fg_lot_with_serials):
    serial_no = fg_lot_with_serials["serials"][5]  # IN_STOCK 상태
    r = client.post("/api/production/reworks", json={"serial_no": serial_no}, headers=tokens["production"])
    assert r.status_code == 400


def test_rework_unknown_serial_404(client, tokens):
    r = client.post("/api/production/reworks", json={"serial_no": "SN-NOPE-1"}, headers=tokens["production"])
    assert r.status_code == 404


# ---------- 생산마감 ----------

def _find_dataset_period(db_path):
    """데이터셋 실적이 있는 과거 월 하나(현재 월 제외 — 다른 테스트의 실적입력을 잠그지 않기 위함)."""
    from datetime import date
    conn = sqlite3.connect(db_path)
    rows = conn.execute(
        "SELECT substr(result_date,1,7) p, COUNT(*) FROM production_result GROUP BY p ORDER BY p",
    ).fetchall()
    conn.close()
    this_month = date.today().isoformat()[:7]
    for p, _ in rows:
        if p != this_month:
            return p
    return None


def test_close_period_creates_doc_and_history(client, tokens, db_path):
    period = _find_dataset_period(db_path)
    assert period, "데이터셋 실적 월이 필요함"
    r = client.post("/api/production/close", json={"period": period}, headers=tokens["admin"])
    assert r.status_code == 200
    body = r.json()
    if body["close_amount"] > 0:
        assert body["acct_doc_id"] is not None
        docs = client.get("/api/accounting/documents", headers=tokens["admin"]).json()
        assert any(d["doc_id"] == body["acct_doc_id"] and d["doc_type"] == "PRODUCTION_CLOSE" for d in docs)
    closes = client.get("/api/production/closes", headers=tokens["admin"]).json()
    assert any(c["period"] == period for c in closes)
    # 중복 마감 차단
    assert client.post("/api/production/close", json={"period": period}, headers=tokens["admin"]).status_code == 400


def test_closed_current_month_blocks_result_then_cleanup(client, tokens, db_path, plant_id, warehouse_id):
    """당월 마감 → 실적입력 400 확인 후, 다른 테스트에 영향 없도록 마감 행을 직접 제거(db_path 픽스처 용도)."""
    from datetime import date
    this_month = date.today().isoformat()[:7]
    assert client.post(
        "/api/production/close", json={"period": this_month}, headers=tokens["admin"],
    ).status_code == 200

    po = client.post(
        "/api/production-orders",
        json={"material_id": FG_MATERIAL_ID, "plant_id": plant_id, "qty": 1},
        headers=tokens["production"],
    ).json()
    wo = client.post(
        f"/api/production-orders/{po['prod_order_id']}/work-orders", json={}, headers=tokens["production"],
    ).json()
    r = client.post(
        f"/api/work-orders/{wo['work_order_id']}/results",
        json={"qty_good": 1, "warehouse_id": warehouse_id},
        headers=tokens["production"],
    )
    assert r.status_code == 400
    assert "생산마감" in r.json()["detail"]

    conn = sqlite3.connect(db_path)
    conn.execute("DELETE FROM production_close WHERE period=?", (this_month,))
    conn.commit()
    conn.close()


def test_close_requires_admin(client, tokens):
    r = client.post("/api/production/close", json={"period": "2030-01"}, headers=tokens["production"])
    assert r.status_code == 403


def test_close_invalid_period_400(client, tokens):
    assert client.post("/api/production/close", json={"period": "202601"}, headers=tokens["admin"]).status_code == 400


# ---------- OEE / Dashboard / 인증 ----------

def test_oee_measured_from_dataset(client, tokens):
    body = client.get("/api/production/oee", headers=tokens["production"]).json()
    assert len(body["measured"]) > 0  # 데이터셋 production_results.csv의 실측 OEE
    row = body["measured"][0]
    for key in ("period", "plant_name", "avg_oee", "result_count"):
        assert key in row
    assert isinstance(body["reference"], list)


def test_dashboard_shape(client, tokens):
    d = client.get("/api/production/dashboard", headers=tokens["sales"]).json()
    for key in (
        "open_order_count", "outsourced_count", "month_good", "month_defect",
        "month_defect_rate", "open_rework_count", "last_closed_period", "avg_oee",
    ):
        assert key in d
    assert d["outsourced_count"] >= 1  # 위 외주 테스트에서 생성


def test_production_ext_requires_login(client):
    assert client.get("/api/production/mrp").status_code == 401
