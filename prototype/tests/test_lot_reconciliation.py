import sqlite3


def test_reconciliation_consistent_for_untouched_material(client, tokens, rm_lot, warehouse_id):
    rows = client.get("/api/lots/reconciliation", headers=tokens["admin"]).json()
    row = next(r for r in rows if r["material_id"] == rm_lot["material_id"] and r["warehouse_id"] == warehouse_id)
    assert row["consistent"] is True
    assert row["untracked_qty"] >= 0


def test_reconciliation_flags_inconsistency_when_lot_exceeds_inventory(client, tokens, db_path, rm_lot, warehouse_id):
    """실제 버그 시뮬레이션: inventory.qty를 LOT 합계보다 작게 강제로 낮춰 부정합 감지를 검증한다.
    API로는 재현 불가능한 상황이라 db_path로 직접 SQL 조작한다(task-plan-lot-reconciliation.md 참고)."""
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "UPDATE inventory SET qty = 0 WHERE material_id = ? AND warehouse_id = ?",
        (rm_lot["material_id"], warehouse_id),
    )
    conn.commit()
    conn.close()

    rows = client.get("/api/lots/reconciliation", headers=tokens["admin"]).json()
    row = next(r for r in rows if r["material_id"] == rm_lot["material_id"] and r["warehouse_id"] == warehouse_id)
    assert row["consistent"] is False
    assert row["untracked_qty"] < 0
