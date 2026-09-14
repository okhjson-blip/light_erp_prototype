def test_rm_lot_created_correctly(rm_lot):
    assert rm_lot["qty"] == 500
    assert rm_lot["status"] == "ACTIVE"


def test_fg_lot_and_serials_created(client, tokens, fg_lot_with_serials):
    """create_lot()의 반환값(work-order/results 응답)은 {lot_id, lot_no}만 담으므로,
    qty는 /lots/{lot_id}/trace로 조회해 확인한다."""
    lot = fg_lot_with_serials["lot"]
    serials = fg_lot_with_serials["serials"]
    assert len(serials) == 8
    trace = client.get(f"/api/lots/{lot['lot_id']}/trace", headers=tokens["admin"]).json()
    assert trace["lot"]["qty"] == 8


def test_rm_lot_consumed_by_bom(client, tokens, rm_lot, fg_lot_with_serials):
    """FG 생산실적 입력 시 BOM 소요로 RM LOT이 FIFO 소진되었는지 확인 (1:1 BOM, qty_good=8)."""
    trace = client.get(f"/api/lots/{rm_lot['lot_id']}/trace", headers=tokens["admin"]).json()
    assert trace["lot"]["qty"] == 500 - 8
    assert any(c["ref_doc_type"] == "PRODUCTION_RESULT" for c in trace["consumptions"])


def test_serial_trace_before_shipment(client, tokens, fg_lot_with_serials):
    serial_no = fg_lot_with_serials["serials"][0]
    trace = client.get(f"/api/serials/{serial_no}/trace", headers=tokens["admin"]).json()
    assert trace["serial"]["status"] == "IN_STOCK"
    assert trace["lot"]["lot_id"] == fg_lot_with_serials["lot"]["lot_id"]


def test_delivery_consumes_fg_lot_and_ships_serials(client, tokens, warehouse_id, fg_lot_with_serials):
    sales = tokens["sales"]
    so = client.post(
        "/api/sales-orders",
        json={"customer_id": 1, "lines": [{"material_id": 1, "qty": 3, "price": 100}]},
        headers=sales,
    )
    assert so.status_code == 200, so.text
    so_id = so.json()["so_id"]
    delivery = client.post(
        f"/api/sales-orders/{so_id}/deliveries",
        json={"warehouse_id": warehouse_id},
        headers=sales,
    )
    assert delivery.status_code == 200, delivery.text

    lot_id = fg_lot_with_serials["lot"]["lot_id"]
    trace = client.get(f"/api/lots/{lot_id}/trace", headers=tokens["admin"]).json()
    assert any(c["ref_doc_type"] == "DELIVERY" for c in trace["consumptions"])

    shipped = [s for s in trace["serials"] if s["status"] == "SHIPPED"]
    assert len(shipped) >= 3
