def test_change_serial_status_success(client, tokens, fg_lot_with_serials):
    serial_no = fg_lot_with_serials["serials"][0]
    r = client.post(
        f"/api/serials/{serial_no}/status",
        json={"status": "DEFECTIVE"},
        headers=tokens["production"],
    )
    assert r.status_code == 200
    assert r.json()["status"] == "DEFECTIVE"

    trace = client.get(f"/api/serials/{serial_no}/trace", headers=tokens["admin"]).json()
    assert trace["serial"]["status"] == "DEFECTIVE"


def test_change_serial_status_forbidden_role(client, tokens, fg_lot_with_serials):
    serial_no = fg_lot_with_serials["serials"][1]
    r = client.post(
        f"/api/serials/{serial_no}/status",
        json={"status": "DEFECTIVE"},
        headers=tokens["sales"],
    )
    assert r.status_code == 403


def test_change_serial_status_invalid_value(client, tokens, fg_lot_with_serials):
    serial_no = fg_lot_with_serials["serials"][2]
    r = client.post(
        f"/api/serials/{serial_no}/status",
        json={"status": "NOT_A_STATUS"},
        headers=tokens["production"],
    )
    assert r.status_code == 400


def test_change_serial_status_not_found(client, tokens):
    r = client.post(
        "/api/serials/SN-NOPE-0000/status",
        json={"status": "SCRAPPED"},
        headers=tokens["production"],
    )
    assert r.status_code == 404
