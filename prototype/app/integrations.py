"""MES/WMS 연계 Mock 어댑터 (v2).
실제 MES/WMS 시스템이 없으므로, 외부 시스템이 보낼 법한 Webhook 페이로드를 그대로 받는
엔드포인트를 제공하고 모든 수신 이벤트를 integration_event_log에 남긴다.
실제 시스템 연동 시에는 이 라우터의 엔드포인트 URL/인증만 실제 MES/WMS 발신 스펙에 맞게
교체하면 되고, 내부 처리 로직(재고 반영 등)은 그대로 재사용 가능하도록 설계했다.
"""
import json

from fastapi import APIRouter, Body, Depends, Header, HTTPException

from .database import get_conn, run, one, rows_to_list, insert_returning
from .helpers import adjust_inventory, require
from .lot_tracking import create_lot, consume_lots_fifo
from .auth import current_user

router = APIRouter(prefix="/api/integrations", tags=["integrations"])


def require_api_key(source_system: str):
    """MES/WMS 웹훅 인증 dependency 팩토리. X-API-Key 헤더를 해당 source_system(MES/WMS)의
    활성 키와 대조한다. 신규 의존성 없음(표준 라이브러리만 사용) — RBAC의 세션 인증과는 별개의,
    시스템 간(system-to-system) 간단한 공유키 방식이다."""
    def _dep(x_api_key: str = Header(None)):
        if not x_api_key:
            raise HTTPException(401, "X-API-Key 헤더가 필요합니다")
        conn = get_conn()
        key = one(run(
            conn, "SELECT key_id FROM integration_api_key WHERE api_key=? AND source_system=? AND active",
            (x_api_key, source_system),
        ))
        conn.close()
        if key is None:
            raise HTTPException(401, "API Key가 유효하지 않습니다")
        return True
    return _dep


def _log_event(conn, source_system, event_type, payload: dict, status="PROCESSED"):
    insert_returning(
        conn,
        "INSERT INTO integration_event_log (source_system, event_type, payload_json, status) VALUES (?,?,?,?)",
        (source_system, event_type, json.dumps(payload, ensure_ascii=False), status),
        "event_id",
    )


@router.get("/events")
def list_events(user: dict = Depends(current_user)):
    conn = get_conn()
    rows = rows_to_list(run(
        conn, "SELECT * FROM integration_event_log ORDER BY event_id DESC LIMIT 100"
    ))
    conn.close()
    return rows


@router.post("/mes/production-result")
def mes_production_result(body: dict = Body(...), _auth: bool = Depends(require_api_key("MES"))):
    """MES가 작업지시 실적을 ERP로 전송한다고 가정한 Webhook.
    payload: {work_order_id, qty_good, qty_defect(선택), warehouse_id}"""
    require(body, "work_order_id", "qty_good", "warehouse_id")
    conn = get_conn()
    wo = one(run(conn, "SELECT * FROM work_order WHERE work_order_id=?", (body["work_order_id"],)))
    if wo is None:
        _log_event(conn, "MES", "PRODUCTION_RESULT", body, status="REJECTED_NOT_FOUND")
        conn.commit()
        conn.close()
        raise HTTPException(404, "작업지시를 찾을 수 없음 (MES 이벤트는 REJECTED로 기록됨)")

    prod_order = one(run(conn, "SELECT * FROM production_order WHERE prod_order_id=?", (wo["prod_order_id"],)))
    qty_good = body["qty_good"]
    qty_defect = body.get("qty_defect", 0)
    warehouse_id = body["warehouse_id"]

    result_id = insert_returning(
        conn, "INSERT INTO production_result (work_order_id, qty_good, qty_defect) VALUES (?,?,?)",
        (body["work_order_id"], qty_good, qty_defect), "result_id",
    )
    bom_lines = rows_to_list(run(conn, "SELECT * FROM bom WHERE parent_material_id=?", (prod_order["material_id"],)))
    for b in bom_lines:
        consumed_qty = qty_good * b["qty"]
        adjust_inventory(
            conn, b["child_material_id"], warehouse_id, -consumed_qty, "OUT", "PRODUCTION_RESULT", result_id
        )
        consume_lots_fifo(conn, b["child_material_id"], warehouse_id, consumed_qty, "PRODUCTION_RESULT", result_id)
    adjust_inventory(conn, prod_order["material_id"], warehouse_id, qty_good, "IN", "PRODUCTION_RESULT", result_id)
    create_lot(conn, prod_order["material_id"], warehouse_id, qty_good, "PRODUCTION_RESULT", result_id)

    run(conn, "UPDATE work_order SET status='DONE' WHERE work_order_id=?", (body["work_order_id"],))
    run(conn, "UPDATE production_order SET status='COMPLETED' WHERE prod_order_id=?", (wo["prod_order_id"],))
    _log_event(conn, "MES", "PRODUCTION_RESULT", body)
    conn.commit()
    conn.close()
    return {"result_id": result_id, "status": "PROCESSED"}


@router.post("/wms/inventory-movement")
def wms_inventory_movement(body: dict = Body(...), _auth: bool = Depends(require_api_key("WMS"))):
    """WMS가 실물 입출고 처리 결과를 ERP로 전송한다고 가정한 Webhook.
    payload: {material_code, warehouse_name, movement_type: 'IN'|'OUT', qty, ref(선택)}"""
    require(body, "material_code", "warehouse_name", "movement_type", "qty")
    if body["movement_type"] not in ("IN", "OUT"):
        raise HTTPException(400, "movement_type은 IN 또는 OUT이어야 함")
    conn = get_conn()
    material = one(run(conn, "SELECT * FROM material WHERE code=?", (body["material_code"],)))
    warehouse = one(run(conn, "SELECT * FROM warehouse WHERE name=?", (body["warehouse_name"],)))
    if material is None or warehouse is None:
        _log_event(conn, "WMS", "INVENTORY_MOVEMENT", body, status="REJECTED_NOT_FOUND")
        conn.commit()
        conn.close()
        raise HTTPException(404, "품목 또는 창고를 찾을 수 없음 (WMS 이벤트는 REJECTED로 기록됨)")

    signed_qty = body["qty"] if body["movement_type"] == "IN" else -body["qty"]
    adjust_inventory(
        conn, material["material_id"], warehouse["warehouse_id"], signed_qty,
        body["movement_type"], "WMS_EVENT", None,
    )
    if body["movement_type"] == "IN":
        create_lot(conn, material["material_id"], warehouse["warehouse_id"], body["qty"], "WMS_EVENT", None)
    else:
        consume_lots_fifo(conn, material["material_id"], warehouse["warehouse_id"], body["qty"], "WMS_EVENT", None)
    _log_event(conn, "WMS", "INVENTORY_MOVEMENT", body)
    conn.commit()
    conn.close()
    return {"status": "PROCESSED"}
