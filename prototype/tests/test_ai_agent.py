import sqlite3


def _pick_low_stock_rm(client, tokens, exclude_ids):
    materials = client.get("/api/materials", headers=tokens["admin"]).json()
    candidates = [
        m for m in materials
        if m["material_type"] == "RM" and m.get("reorder_point") and m["reorder_point"] > 0
        and m["material_id"] not in exclude_ids
    ]
    assert candidates, "reorder_point>0인 RM 품목이 없음 — 시드 데이터 확인 필요"
    return candidates[-1]


def test_buyer_recommendation_triggered_by_low_stock(client, tokens, db_path):
    """RM_MATERIAL_ID(6)는 다른 fixture(rm_lot)가 사용 중이므로 건드리지 않고,
    별도 RM 품목의 재고를 강제로 0으로 낮춰 재발주 추천이 뜨는지 검증한다."""
    material = _pick_low_stock_rm(client, tokens, exclude_ids={6})
    conn = sqlite3.connect(str(db_path))
    conn.execute("UPDATE inventory SET qty = 0 WHERE material_id = ?", (material["material_id"],))
    conn.commit()
    conn.close()

    recs = client.get("/api/ai/buyer/recommendations", headers=tokens["admin"]).json()
    rec = next((r for r in recs if r["material_id"] == material["material_id"]), None)
    assert rec is not None
    assert rec["current_qty"] < rec["reorder_point"]
    assert "ai_narrative" in rec
    assert "rationale" in rec


def test_buyer_recommendations_requires_login(client):
    r = client.get("/api/ai/buyer/recommendations")
    assert r.status_code == 401


def test_scheduler_recommendations_narrative(client, tokens):
    r = client.get("/api/ai/scheduler/recommendations", headers=tokens["admin"])
    assert r.status_code == 200
    for item in r.json():
        assert "ai_narrative" in item
        assert "rationale" in item


def test_quality_recommendations_narrative(client, tokens):
    r = client.get("/api/ai/quality/recommendations", headers=tokens["admin"])
    assert r.status_code == 200
    for item in r.json():
        assert "ai_narrative" in item
        assert "rationale" in item


def test_demand_planner_recommendations_narrative(client, tokens):
    r = client.get("/api/ai/demand-planner/recommendations", headers=tokens["admin"])
    assert r.status_code == 200
    for item in r.json():
        assert "ai_narrative" in item
        assert "rationale" in item


def test_cfo_copilot_insights_narrative(client, tokens):
    r = client.get("/api/ai/cfo-copilot/insights", headers=tokens["admin"])
    assert r.status_code == 200
    insights = r.json()
    assert len(insights) >= 1  # 매출채권/매입채무 현황 인사이트는 항상 존재
    for item in insights:
        assert "ai_narrative" in item
        assert "detail" in item
