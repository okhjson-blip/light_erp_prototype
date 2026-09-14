MES_KEY = "mes-demo-key-please-rotate"
WMS_KEY = "wms-demo-key-please-rotate"


def test_wms_missing_api_key_401(client):
    r = client.post("/api/integrations/wms/inventory-movement", json={
        "material_code": "RM-0001", "warehouse_name": "X", "movement_type": "IN", "qty": 1,
    })
    assert r.status_code == 401


def test_wms_wrong_api_key_401(client):
    r = client.post(
        "/api/integrations/wms/inventory-movement",
        json={"material_code": "RM-0001", "warehouse_name": "X", "movement_type": "IN", "qty": 1},
        headers={"X-API-Key": "not-a-real-key"},
    )
    assert r.status_code == 401


def test_wms_cross_source_key_rejected(client):
    """MES 키로 WMS 엔드포인트 호출 시 거부되어야 함 (source_system 별 키 분리)."""
    r = client.post(
        "/api/integrations/wms/inventory-movement",
        json={"material_code": "RM-0001", "warehouse_name": "X", "movement_type": "IN", "qty": 1},
        headers={"X-API-Key": MES_KEY},
    )
    assert r.status_code == 401


def test_wms_correct_key_accepted(client, tokens):
    materials = client.get("/api/materials", headers=tokens["admin"]).json()
    warehouses = client.get("/api/warehouses", headers=tokens["admin"]).json()
    r = client.post(
        "/api/integrations/wms/inventory-movement",
        json={
            "material_code": materials[0]["code"], "warehouse_name": warehouses[0]["name"],
            "movement_type": "IN", "qty": 10,
        },
        headers={"X-API-Key": WMS_KEY},
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "PROCESSED"


def test_mes_missing_api_key_401(client):
    r = client.post("/api/integrations/mes/production-result", json={
        "work_order_id": 1, "qty_good": 1, "warehouse_id": 1,
    })
    assert r.status_code == 401


def test_mes_wrong_key_401(client):
    r = client.post(
        "/api/integrations/mes/production-result",
        json={"work_order_id": 1, "qty_good": 1, "warehouse_id": 1},
        headers={"X-API-Key": WMS_KEY},
    )
    assert r.status_code == 401


def test_mes_correct_key_accepted(client, tokens, plant_id, warehouse_id):
    production = tokens["production"]
    po = client.post(
        "/api/production-orders",
        json={"material_id": 1, "plant_id": plant_id, "qty": 2},
        headers=production,
    )
    assert po.status_code == 200, po.text
    wo = client.post(
        f"/api/production-orders/{po.json()['prod_order_id']}/work-orders", json={}, headers=production
    )
    assert wo.status_code == 200, wo.text
    wo_id = wo.json()["work_order_id"]

    r = client.post(
        "/api/integrations/mes/production-result",
        json={"work_order_id": wo_id, "qty_good": 2, "warehouse_id": warehouse_id},
        headers={"X-API-Key": MES_KEY},
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "PROCESSED"


def test_events_log_requires_login(client):
    r = client.get("/api/integrations/events")
    assert r.status_code == 401


def test_events_log_visible_after_login(client, tokens):
    r = client.get("/api/integrations/events", headers=tokens["admin"])
    assert r.status_code == 200
    assert isinstance(r.json(), list)
