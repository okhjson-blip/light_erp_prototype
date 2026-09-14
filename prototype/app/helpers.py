"""main.py / integrations.py / ai_agent.py가 공유하는 헬퍼.
순환 임포트를 피하기 위해 별도 모듈로 분리."""
from fastapi import HTTPException

from .database import run, one, insert_returning


def adjust_inventory(conn, material_id, warehouse_id, delta, txn_type, ref_doc_type, ref_doc_id):
    row = one(run(
        conn, "SELECT inventory_id, qty FROM inventory WHERE material_id=? AND warehouse_id=?",
        (material_id, warehouse_id),
    ))
    if row is None:
        run(conn, "INSERT INTO inventory (material_id, warehouse_id, qty) VALUES (?,?,?)",
            (material_id, warehouse_id, delta))
    else:
        new_qty = row["qty"] + delta
        run(conn, "UPDATE inventory SET qty=? WHERE inventory_id=?", (new_qty, row["inventory_id"]))
    run(
        conn,
        "INSERT INTO inventory_transaction (material_id, warehouse_id, txn_type, qty, ref_doc_type, ref_doc_id) "
        "VALUES (?,?,?,?,?,?)",
        (material_id, warehouse_id, txn_type, abs(delta), ref_doc_type, ref_doc_id),
    )


def post_accounting(conn, doc_type, description, lines):
    """lines: [(account_code, debit, credit), ...]"""
    doc_id = insert_returning(
        conn, "INSERT INTO accounting_document (doc_type, description) VALUES (?,?)",
        (doc_type, description), "doc_id",
    )
    for account_code, debit, credit in lines:
        acc = one(run(conn, "SELECT account_id FROM gl_account WHERE code=?", (account_code,)))
        if acc is None:
            raise HTTPException(400, f"GL 계정 코드 없음: {account_code}")
        run(
            conn, "INSERT INTO accounting_line (doc_id, account_id, debit, credit) VALUES (?,?,?,?)",
            (doc_id, acc["account_id"], debit, credit),
        )
    return doc_id


def require(body: dict, *fields):
    missing = [f for f in fields if body.get(f) in (None, "")]
    if missing:
        raise HTTPException(400, f"필수 항목 누락: {', '.join(missing)}")


def write_audit_log(conn, user_id, action: str, entity: str, entity_id: int = None):
    """audit_log(v1 스키마부터 존재하나 그동안 아무 코드도 쓰지 않던 테이블)에 감사 이벤트를 남긴다.
    스키마에 별도 detail 컬럼이 없어, 상태 전이처럼 부가 정보가 필요한 경우 action 문자열에
    "STATUS_CHANGE:IN_STOCK->DEFECTIVE"처럼 인코딩한다(신규 컬럼/마이그레이션 불필요)."""
    run(
        conn, "INSERT INTO audit_log (user_id, action, entity, entity_id) VALUES (?,?,?,?)",
        (user_id, action, entity, entity_id),
    )
