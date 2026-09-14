"""WMS/QMS LOT·Serial 추적 (v3).
기존 inventory(집계) 테이블과 adjust_inventory()는 건드리지 않고, 같은 호출부에서
병행 기록되는 별도 레이어로 LOT을 추가한다. 신규 의존성 없음(표준 라이브러리만 사용).

설계 결정 요약(task-plan-lot-serial.md 참고):
- LOT 생성: 입고(GR)/생산실적(FG)/WMS IN 이벤트
- LOT 소진(FIFO): 출하/생산실적 BOM 소요(RM)/WMS OUT 이벤트
- 과거 임포트 재고는 LOT이 없어 FIFO 소진 시 가용 수량 부족해도 에러 없이 가능한 만큼만 처리
- 시리얼은 선택 기능(생산실적입력 시 generate_serials:true인 경우만, 1회 최대 500개)
"""
import secrets
from datetime import datetime

from fastapi import APIRouter, Body, Depends, HTTPException

from .database import get_conn, run, one, rows_to_list, insert_returning
from .helpers import require, write_audit_log
from .auth import require_roles, current_user

router = APIRouter(prefix="/api", tags=["lot-serial"])

MAX_SERIALS_PER_CALL = 500


def _material_code(conn, material_id):
    m = one(run(conn, "SELECT code FROM material WHERE material_id=?", (material_id,)))
    return m["code"] if m else "UNKNOWN"


def generate_lot_no(material_code: str) -> str:
    return f"LOT-{material_code}-{datetime.utcnow():%Y%m%d%H%M%S}-{secrets.token_hex(2).upper()}"


def create_lot(conn, material_id, warehouse_id, qty, source_type, source_ref_id) -> dict:
    """새 LOT을 생성해 {lot_id, lot_no}를 반환한다. qty<=0이면 생성하지 않는다."""
    if qty is None or qty <= 0:
        return None
    lot_no = generate_lot_no(_material_code(conn, material_id))
    lot_id = insert_returning(
        conn,
        "INSERT INTO lot (lot_no, material_id, warehouse_id, qty, source_type, source_ref_id) "
        "VALUES (?,?,?,?,?,?)",
        (lot_no, material_id, warehouse_id, qty, source_type, source_ref_id),
        "lot_id",
    )
    return {"lot_id": lot_id, "lot_no": lot_no}


def _ship_serials_from_lot(conn, lot_id, count):
    """해당 LOT에 속한 IN_STOCK 시리얼 중 count개를(생성순) SHIPPED로 반영한다.
    시리얼이 없거나 부족해도 에러 없이 가능한 만큼만 처리한다(시리얼은 선택 기능이라 없을 수 있음)."""
    count = int(count)
    if count <= 0:
        return
    serials = rows_to_list(run(
        conn, "SELECT serial_id FROM serial_number WHERE lot_id=? AND status='IN_STOCK' "
        "ORDER BY serial_id ASC LIMIT ?",
        (lot_id, count),
    ))
    for s in serials:
        run(conn, "UPDATE serial_number SET status='SHIPPED' WHERE serial_id=?", (s["serial_id"],))


def consume_lots_fifo(conn, material_id, warehouse_id, qty, ref_doc_type, ref_doc_id, mark_serials_shipped=False) -> list:
    """가장 오래된 ACTIVE LOT부터 순서대로 qty를 소진한다.
    가용 LOT 수량이 부족해도(과거 임포트 재고 등) 에러 없이 가능한 만큼만 소진하고 반환한다
    (명시적 비범위 — task-plan-lot-serial.md 참고).
    mark_serials_shipped=True이면(출하 흐름에서만 사용) 소진된 수량만큼 해당 LOT의 시리얼을
    SHIPPED로 반영한다(생산 자재소요 등 출하가 아닌 소진에는 적용하지 않음)."""
    remaining = qty
    consumed = []
    if remaining is None or remaining <= 0:
        return consumed
    lots = rows_to_list(run(
        conn,
        "SELECT * FROM lot WHERE material_id=? AND warehouse_id=? AND status='ACTIVE' "
        "ORDER BY created_date ASC, lot_id ASC",
        (material_id, warehouse_id),
    ))
    for lot in lots:
        if remaining <= 0:
            break
        take = min(lot["qty"], remaining)
        if take <= 0:
            continue
        new_qty = lot["qty"] - take
        new_status = "CONSUMED" if new_qty <= 0 else "ACTIVE"
        run(conn, "UPDATE lot SET qty=?, status=? WHERE lot_id=?", (new_qty, new_status, lot["lot_id"]))
        run(
            conn,
            "INSERT INTO lot_consumption (lot_id, qty, ref_doc_type, ref_doc_id) VALUES (?,?,?,?)",
            (lot["lot_id"], take, ref_doc_type, ref_doc_id),
        )
        if mark_serials_shipped:
            _ship_serials_from_lot(conn, lot["lot_id"], take)
        consumed.append({"lot_id": lot["lot_id"], "lot_no": lot["lot_no"], "qty_consumed": take})
        remaining -= take
    return consumed


def generate_serials(conn, material_id, lot_id, count: int) -> list:
    count = int(count)
    if count <= 0:
        return []
    if count > MAX_SERIALS_PER_CALL:
        raise HTTPException(400, f"시리얼 생성은 1회 최대 {MAX_SERIALS_PER_CALL}개까지 가능합니다")
    code = _material_code(conn, material_id)
    serials = []
    for _ in range(count):
        serial_no = f"SN-{code}-{secrets.token_hex(4).upper()}"
        run(
            conn,
            "INSERT INTO serial_number (serial_no, material_id, lot_id) VALUES (?,?,?)",
            (serial_no, material_id, lot_id),
        )
        serials.append(serial_no)
    return serials


# ===== 조회 API =====

@router.get("/lots")
def list_lots(material_id: int = None, warehouse_id: int = None, status: str = None, user: dict = Depends(current_user)):
    conn = get_conn()
    sql = (
        "SELECT l.*, m.code AS material_code, m.name AS material_name, w.name AS warehouse_name "
        "FROM lot l JOIN material m ON m.material_id = l.material_id "
        "JOIN warehouse w ON w.warehouse_id = l.warehouse_id WHERE 1=1"
    )
    params = []
    if material_id is not None:
        sql += " AND l.material_id=?"
        params.append(material_id)
    if warehouse_id is not None:
        sql += " AND l.warehouse_id=?"
        params.append(warehouse_id)
    if status is not None:
        sql += " AND l.status=?"
        params.append(status)
    sql += " ORDER BY l.created_date DESC LIMIT 300"
    rows = rows_to_list(run(conn, sql, tuple(params)))
    conn.close()
    return rows


RECONCILIATION_EPSILON = 1e-6


@router.get("/lots/reconciliation")
def lot_reconciliation(user: dict = Depends(current_user)):
    """LOT 재고(집계) ↔ inventory.qty(집계) 정합성 점검.
    과거 임포트 재고 등 LOT이 없는 부분(untracked_qty > 0)은 정상 범위다(task-plan-lot-serial.md에
    명시한 비범위). 반대로 active LOT 합계가 inventory.qty를 초과하는 경우(untracked_qty < 0)는
    LOT 레이어와 집계 레이어가 어긋난 실제 버그 신호이므로 inconsistent=true로 표시한다."""
    conn = get_conn()
    rows = rows_to_list(run(
        conn,
        "SELECT l.material_id, l.warehouse_id, m.code AS material_code, m.name AS material_name, "
        "w.name AS warehouse_name, "
        "SUM(CASE WHEN l.status='ACTIVE' THEN l.qty ELSE 0 END) AS active_lot_qty, "
        "COALESCE(inv.qty, 0) AS inventory_qty "
        "FROM lot l "
        "JOIN material m ON m.material_id = l.material_id "
        "JOIN warehouse w ON w.warehouse_id = l.warehouse_id "
        "LEFT JOIN inventory inv ON inv.material_id = l.material_id AND inv.warehouse_id = l.warehouse_id "
        "GROUP BY l.material_id, l.warehouse_id, m.code, m.name, w.name, inv.qty "
        "ORDER BY m.code",
    ))
    conn.close()
    for r in rows:
        r["untracked_qty"] = round(r["inventory_qty"] - r["active_lot_qty"], 6)
        r["consistent"] = r["untracked_qty"] >= -RECONCILIATION_EPSILON
    return rows


def count_lot_inconsistencies(conn) -> int:
    """lot_reconciliation()과 동일한 판정을 집계 쿼리 하나로 계산한다(행 전체를 안 가져와도 됨).
    v8: 대시보드 KPI에 상시 노출해 "온디맨드 조회"를 넘어 부정합을 바로 눈에 띄게 한다."""
    row = one(run(
        conn,
        "SELECT COUNT(*) c FROM ("
        "  SELECT l.material_id, l.warehouse_id, "
        "  SUM(CASE WHEN l.status='ACTIVE' THEN l.qty ELSE 0 END) AS active_lot_qty, "
        "  COALESCE(inv.qty, 0) AS inventory_qty "
        "  FROM lot l "
        "  LEFT JOIN inventory inv ON inv.material_id = l.material_id AND inv.warehouse_id = l.warehouse_id "
        "  GROUP BY l.material_id, l.warehouse_id, inv.qty"
        f") t WHERE (t.inventory_qty - t.active_lot_qty) < -{RECONCILIATION_EPSILON}",
    ))
    return row["c"]


@router.get("/lots/{lot_id}/trace")
def trace_lot(lot_id: int, user: dict = Depends(current_user)):
    conn = get_conn()
    lot = one(run(
        conn,
        "SELECT l.*, m.code AS material_code, m.name AS material_name, w.name AS warehouse_name "
        "FROM lot l JOIN material m ON m.material_id = l.material_id "
        "JOIN warehouse w ON w.warehouse_id = l.warehouse_id WHERE l.lot_id=?",
        (lot_id,),
    ))
    if lot is None:
        conn.close()
        raise HTTPException(404, "LOT을 찾을 수 없음")
    consumptions = rows_to_list(run(
        conn, "SELECT * FROM lot_consumption WHERE lot_id=? ORDER BY consumed_date ASC", (lot_id,)
    ))
    serials = rows_to_list(run(conn, "SELECT * FROM serial_number WHERE lot_id=?", (lot_id,)))
    conn.close()
    return {"lot": lot, "consumptions": consumptions, "serials": serials}


@router.get("/serials")
def list_serials(material_id: int = None, status: str = None, user: dict = Depends(current_user)):
    conn = get_conn()
    sql = (
        "SELECT s.*, m.code AS material_code, m.name AS material_name, l.lot_no "
        "FROM serial_number s JOIN material m ON m.material_id = s.material_id "
        "LEFT JOIN lot l ON l.lot_id = s.lot_id WHERE 1=1"
    )
    params = []
    if material_id is not None:
        sql += " AND s.material_id=?"
        params.append(material_id)
    if status is not None:
        sql += " AND s.status=?"
        params.append(status)
    sql += " ORDER BY s.created_date DESC LIMIT 300"
    rows = rows_to_list(run(conn, sql, tuple(params)))
    conn.close()
    return rows


@router.get("/serials/{serial_no}/trace")
def trace_serial(serial_no: str, user: dict = Depends(current_user)):
    conn = get_conn()
    serial = one(run(
        conn,
        "SELECT s.*, m.code AS material_code, m.name AS material_name "
        "FROM serial_number s JOIN material m ON m.material_id = s.material_id WHERE s.serial_no=?",
        (serial_no,),
    ))
    if serial is None:
        conn.close()
        raise HTTPException(404, "시리얼을 찾을 수 없음")
    lot = None
    if serial["lot_id"] is not None:
        lot = one(run(conn, "SELECT * FROM lot WHERE lot_id=?", (serial["lot_id"],)))
    conn.close()
    return {"serial": serial, "lot": lot}


SERIAL_STATUSES = {"IN_STOCK", "SHIPPED", "DEFECTIVE", "SCRAPPED"}


@router.post("/serials/{serial_no}/status")
def update_serial_status(serial_no: str, body: dict = Body(...), user: dict = Depends(require_roles("생산담당", "관리자"))):
    """시리얼 상태 수동 변경(불량/폐기 등). 출하 시 SHIPPED 반영은 consume_lots_fifo에서 자동 처리되므로
    여기서는 사람이 직접 조정해야 하는 케이스(품질 불량 발견, 폐기 결정 등)를 다룬다."""
    require(body, "status")
    if body["status"] not in SERIAL_STATUSES:
        raise HTTPException(400, f"status는 {', '.join(sorted(SERIAL_STATUSES))} 중 하나여야 함")
    conn = get_conn()
    serial = one(run(conn, "SELECT serial_id, status FROM serial_number WHERE serial_no=?", (serial_no,)))
    if serial is None:
        conn.close()
        raise HTTPException(404, "시리얼을 찾을 수 없음")
    old_status = serial["status"]
    run(conn, "UPDATE serial_number SET status=? WHERE serial_id=?", (body["status"], serial["serial_id"]))
    write_audit_log(
        conn, user["user_id"], f"STATUS_CHANGE:{old_status}->{body['status']}",
        "serial_number", serial["serial_id"],
    )
    conn.commit()
    conn.close()
    return {"serial_no": serial_no, "status": body["status"]}


# ===== QMS 실시간 검사 등록 =====
# "품질담당" 역할이 프로젝트에 없어, 생산현장 검사라는 현실적 가정 하에 생산담당+관리자로 게이팅한다.

@router.post("/quality/inspections")
def create_quality_inspection(body: dict = Body(...), user: dict = Depends(require_roles("생산담당", "관리자"))):
    require(body, "material_id", "inspection_type", "sample_qty", "result")
    conn = get_conn()
    material = one(run(conn, "SELECT * FROM material WHERE material_id=?", (body["material_id"],)))
    if material is None:
        conn.close()
        raise HTTPException(404, "품목을 찾을 수 없음")
    lot_id = body.get("lot_id")
    if lot_id is not None:
        lot = one(run(conn, "SELECT lot_id FROM lot WHERE lot_id=?", (lot_id,)))
        if lot is None:
            conn.close()
            raise HTTPException(404, "LOT을 찾을 수 없음")
    defect_qty = body.get("defect_qty", 0)
    sample_qty = body["sample_qty"]
    defect_ppm = (defect_qty / sample_qty * 1_000_000) if sample_qty else None
    inspection_id = insert_returning(
        conn,
        "INSERT INTO quality_inspection "
        "(inspection_date, plant_id, material_id, inspection_type, sample_qty, defect_qty, "
        "defect_ppm, result, capa_required, lot_id) "
        "VALUES (?,?,?,?,?,?,?,?,?,?)",
        (
            datetime.utcnow().strftime("%Y-%m-%d"), material.get("plant_id"), body["material_id"],
            body["inspection_type"], sample_qty, defect_qty, defect_ppm, body["result"],
            body.get("capa_required", "N"), lot_id,
        ),
        "inspection_id",
    )
    conn.commit()
    conn.close()
    return {"inspection_id": inspection_id}
