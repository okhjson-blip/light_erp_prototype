"""AX ERP Prototype v1/v2 — FastAPI + SQLAlchemy(SQLite/PostgreSQL 겸용), 단일 파일 모놀리식.
Phase 1 Core 7모듈: MDM / Sales / Procurement / Production / Inventory / FI / Common
v2 확장: PostgreSQL 지원, MES/WMS mock 연계(integrations.py), AI Agent 추천(ai_agent.py)
v4 확장: Alembic 마이그레이션(app/database.py), 헬스체크(/health), 구조화 로깅 — task-plan-mvp-infra.md 참고
"""
import logging
import os
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, Body, Depends, Header
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from .database import get_conn, init_db, run, one, rows_to_list, insert_returning
from .seed import run_seed
from .helpers import adjust_inventory, post_accounting, require, write_audit_log
from .auth import (
    hash_password, verify_password, issue_tokens, delete_refresh_token, rotate_tokens,
    RefreshTokenReuseDetected, current_user, require_roles,
)
from .oidc import OidcTokenInvalid, OidcUnavailable, verify_access_token
from .integrations import router as integrations_router
from .ai_agent import router as ai_agent_router
from .reference_data import router as reference_data_router
from .sales_ext import router as sales_ext_router
from .scm import router as scm_router
from .logistics import router as logistics_router
from .production_ext import router as production_ext_router, assert_period_not_closed
from .quality_ext import router as quality_ext_router
from .procurement_ext import router as procurement_ext_router
from .lot_tracking import (
    router as lot_tracking_router, create_lot, consume_lots_fifo, generate_serials,
    count_lot_inconsistencies,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-5s [%(name)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("standard_erp")

BASE_DIR = Path(__file__).resolve().parent
# v7: 기존 vanilla-JS 프론트(static/index.html)를 React(frontend/)로 완전 이관하며 제거했다
# (task-plan-frontend-react.md "마무리" 단계, 사용자 확인 후 진행 — eval-report-frontend-v5.md 참고).
# 운영 빌드(frontend/dist/)가 있으면 그대로 서빙하고, 없으면(아직 `npm run build`를 안 돌린 경우)
# 개발 서버 안내 메시지를 반환한다.
FRONTEND_DIST_DIR = BASE_DIR.parent / "frontend" / "dist"

app = FastAPI(title="AX ERP Prototype")
app.include_router(integrations_router)
app.include_router(ai_agent_router)
app.include_router(reference_data_router)
app.include_router(lot_tracking_router)
app.include_router(sales_ext_router)
app.include_router(scm_router)
app.include_router(logistics_router)
app.include_router(production_ext_router)
app.include_router(quality_ext_router)
app.include_router(procurement_ext_router)


@app.on_event("startup")
def on_startup():
    logger.info("서버 기동 시작 — 스키마 마이그레이션(alembic) 확인 중")
    is_new = init_db()
    logger.info("마이그레이션 완료 (신규 DB: %s)", is_new)
    if is_new:
        logger.info("신규 DB 감지 — 초기 시드 데이터 적재 시작")
        run_seed()
        logger.info("초기 시드 데이터 적재 완료")


@app.get("/")
def index():
    dist_index = FRONTEND_DIST_DIR / "index.html"
    if dist_index.exists():
        return FileResponse(dist_index)
    return {
        "message": "React 프론트엔드가 아직 빌드되지 않았습니다.",
        "dev": "cd frontend && npm run dev  (http://localhost:5183, /api·/health는 이 서버로 자동 프록시)",
        "build": "cd frontend && npm run build  (완료 후 이 경로(/)에서 바로 서빙됩니다)",
    }


@app.get("/health")
def health():
    """인프라 헬스 프로브용 — 비인증. DB 연결까지 확인한다."""
    try:
        conn = get_conn()
        conn.execute(text("SELECT 1"))
        conn.close()
        return {"status": "ok", "db": "ok"}
    except Exception as e:
        logger.error("헬스체크 실패: %s", e)
        raise HTTPException(503, {"status": "error", "db": "error", "detail": str(e)})


if FRONTEND_DIST_DIR.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST_DIR / "assets"), name="frontend-assets")


# ---------- MDM ----------
@app.get("/api/materials")
def list_materials(user: dict = Depends(current_user)):
    conn = get_conn()
    rows = rows_to_list(run(conn, "SELECT * FROM material ORDER BY material_id"))
    conn.close()
    return rows


@app.post("/api/materials")
def create_material(body: dict = Body(...), user: dict = Depends(require_roles("관리자"))):
    require(body, "code", "name")
    conn = get_conn()
    new_id = insert_returning(
        conn,
        "INSERT INTO material (code, name, material_type, uom, plant_id, reorder_point, target_stock) "
        "VALUES (?,?,?,?,?,?,?)",
        (body["code"], body["name"], body.get("material_type", "FG"), body.get("uom", "EA"),
         body.get("plant_id"), body.get("reorder_point", 0), body.get("target_stock", 0)),
        "material_id",
    )
    conn.commit()
    conn.close()
    return {"material_id": new_id}


@app.get("/api/customers")
def list_customers(user: dict = Depends(current_user)):
    conn = get_conn()
    rows = rows_to_list(run(conn, "SELECT * FROM customer ORDER BY customer_id"))
    conn.close()
    return rows


@app.post("/api/customers")
def create_customer(body: dict = Body(...), user: dict = Depends(require_roles("관리자"))):
    require(body, "name")
    conn = get_conn()
    new_id = insert_returning(
        conn, "INSERT INTO customer (name, credit_limit, currency, payment_term) VALUES (?,?,?,?)",
        (body["name"], body.get("credit_limit", 0), body.get("currency", "KRW"), body.get("payment_term", "NET30")),
        "customer_id",
    )
    conn.commit()
    conn.close()
    return {"customer_id": new_id}


@app.get("/api/vendors")
def list_vendors(user: dict = Depends(current_user)):
    conn = get_conn()
    rows = rows_to_list(run(conn, "SELECT * FROM vendor ORDER BY vendor_id"))
    conn.close()
    return rows


@app.post("/api/vendors")
def create_vendor(body: dict = Body(...), user: dict = Depends(require_roles("관리자"))):
    require(body, "name")
    conn = get_conn()
    new_id = insert_returning(
        conn, "INSERT INTO vendor (name, payment_term, lead_time_days) VALUES (?,?,?)",
        (body["name"], body.get("payment_term", "NET30"), body.get("lead_time_days", 7)),
        "vendor_id",
    )
    conn.commit()
    conn.close()
    return {"vendor_id": new_id}


@app.get("/api/warehouses")
def list_warehouses(user: dict = Depends(current_user)):
    conn = get_conn()
    rows = rows_to_list(run(conn, "SELECT * FROM warehouse ORDER BY warehouse_id"))
    conn.close()
    return rows


@app.get("/api/plants")
def list_plants(user: dict = Depends(current_user)):
    conn = get_conn()
    rows = rows_to_list(run(conn, "SELECT * FROM plant ORDER BY plant_id"))
    conn.close()
    return rows


# ---------- Sales ----------
@app.get("/api/sales-orders")
def list_sales_orders(user: dict = Depends(current_user)):
    conn = get_conn()
    rows = rows_to_list(run(
        conn,
        "SELECT so.*, c.name AS customer_name FROM sales_order so "
        "JOIN customer c ON c.customer_id = so.customer_id ORDER BY so.so_id DESC"
    ))
    conn.close()
    return rows


@app.get("/api/sales-orders/{so_id}")
def get_sales_order(so_id: int, user: dict = Depends(current_user)):
    conn = get_conn()
    so = one(run(conn, "SELECT * FROM sales_order WHERE so_id=?", (so_id,)))
    if so is None:
        conn.close()
        raise HTTPException(404, "수주를 찾을 수 없음")
    lines = rows_to_list(run(
        conn,
        "SELECT l.*, m.name AS material_name FROM sales_order_line l "
        "JOIN material m ON m.material_id = l.material_id WHERE so_id=?",
        (so_id,),
    ))
    conn.close()
    return {**so, "lines": lines}


@app.post("/api/sales-orders")
def create_sales_order(body: dict = Body(...), user: dict = Depends(require_roles("영업담당", "관리자"))):
    require(body, "customer_id", "lines")
    if not body["lines"]:
        raise HTTPException(400, "최소 1개 라인이 필요함")
    conn = get_conn()
    so_id = insert_returning(
        conn, "INSERT INTO sales_order (customer_id) VALUES (?)", (body["customer_id"],), "so_id"
    )
    for line in body["lines"]:
        require(line, "material_id", "qty")
        run(
            conn, "INSERT INTO sales_order_line (so_id, material_id, qty, price) VALUES (?,?,?,?)",
            (so_id, line["material_id"], line["qty"], line.get("price", 0)),
        )
    conn.commit()
    conn.close()
    return {"so_id": so_id}


@app.post("/api/sales-orders/{so_id}/deliveries")
def create_delivery(so_id: int, body: dict = Body(...), user: dict = Depends(require_roles("영업담당", "관리자"))):
    require(body, "warehouse_id")
    conn = get_conn()
    so = one(run(conn, "SELECT * FROM sales_order WHERE so_id=?", (so_id,)))
    if so is None:
        conn.close()
        raise HTTPException(404, "수주를 찾을 수 없음")
    lines = rows_to_list(run(conn, "SELECT * FROM sales_order_line WHERE so_id=?", (so_id,)))
    delivery_id = insert_returning(
        conn, "INSERT INTO delivery (so_id, warehouse_id) VALUES (?,?)", (so_id, body["warehouse_id"]), "delivery_id"
    )
    for line in lines:
        adjust_inventory(
            conn, line["material_id"], body["warehouse_id"], -line["qty"], "OUT", "DELIVERY", delivery_id
        )
        consume_lots_fifo(
            conn, line["material_id"], body["warehouse_id"], line["qty"], "DELIVERY", delivery_id,
            mark_serials_shipped=True,
        )
    run(conn, "UPDATE sales_order SET status='DELIVERED' WHERE so_id=?", (so_id,))
    conn.commit()
    conn.close()
    return {"delivery_id": delivery_id}


@app.post("/api/sales-orders/{so_id}/invoices")
def create_sales_invoice(so_id: int, user: dict = Depends(require_roles("영업담당", "관리자"))):
    conn = get_conn()
    so = one(run(conn, "SELECT * FROM sales_order WHERE so_id=?", (so_id,)))
    if so is None:
        conn.close()
        raise HTTPException(404, "수주를 찾을 수 없음")
    lines = rows_to_list(run(conn, "SELECT * FROM sales_order_line WHERE so_id=?", (so_id,)))
    amount = sum(l["qty"] * l["price"] for l in lines)
    invoice_id = insert_returning(
        conn, "INSERT INTO sales_invoice (so_id, customer_id, amount) VALUES (?,?,?)",
        (so_id, so["customer_id"], amount), "invoice_id",
    )
    post_accounting(
        conn, "SO_INVOICE", f"SO#{so_id} 매출 계상",
        [("1100", amount, 0), ("4000", 0, amount)],
    )
    run(conn, "UPDATE sales_order SET status='INVOICED' WHERE so_id=?", (so_id,))
    conn.commit()
    conn.close()
    return {"invoice_id": invoice_id, "amount": amount}


# ---------- Procurement ----------
@app.get("/api/purchase-requisitions")
def list_prs(user: dict = Depends(current_user)):
    conn = get_conn()
    rows = rows_to_list(run(conn, "SELECT * FROM purchase_requisition ORDER BY pr_id DESC"))
    conn.close()
    return rows


@app.post("/api/purchase-requisitions")
def create_pr(body: dict = Body(...), user: dict = Depends(require_roles("구매담당", "관리자"))):
    require(body, "lines")
    conn = get_conn()
    pr_id = insert_returning(
        conn, "INSERT INTO purchase_requisition (requester_id) VALUES (?)", (body.get("requester_id"),), "pr_id"
    )
    for line in body["lines"]:
        require(line, "material_id", "qty")
        run(conn, "INSERT INTO pr_line (pr_id, material_id, qty) VALUES (?,?,?)",
            (pr_id, line["material_id"], line["qty"]))
    run(conn, "INSERT INTO approval_workflow (doc_type, doc_id) VALUES ('PR', ?)", (pr_id,))
    conn.commit()
    conn.close()
    return {"pr_id": pr_id}


@app.get("/api/purchase-orders")
def list_pos(user: dict = Depends(current_user)):
    conn = get_conn()
    rows = rows_to_list(run(
        conn,
        "SELECT po.*, v.name AS vendor_name FROM purchase_order po "
        "JOIN vendor v ON v.vendor_id = po.vendor_id ORDER BY po.po_id DESC"
    ))
    conn.close()
    return rows


@app.get("/api/purchase-orders/{po_id}")
def get_po(po_id: int, user: dict = Depends(current_user)):
    conn = get_conn()
    po = one(run(conn, "SELECT * FROM purchase_order WHERE po_id=?", (po_id,)))
    if po is None:
        conn.close()
        raise HTTPException(404, "발주를 찾을 수 없음")
    lines = rows_to_list(run(
        conn,
        "SELECT l.*, m.name AS material_name FROM po_line l "
        "JOIN material m ON m.material_id = l.material_id WHERE po_id=?",
        (po_id,),
    ))
    conn.close()
    return {**po, "lines": lines}


PO_TYPES = {"STANDARD", "OUTSOURCING", "CONSIGNMENT"}


@app.post("/api/purchase-orders")
def create_po(body: dict = Body(...), user: dict = Depends(require_roles("구매담당", "관리자"))):
    require(body, "vendor_id", "lines")
    if not body["lines"]:
        raise HTTPException(400, "최소 1개 라인이 필요함")
    po_type = body.get("po_type", "STANDARD")
    if po_type not in PO_TYPES:
        raise HTTPException(400, f"po_type은 {', '.join(sorted(PO_TYPES))} 중 하나여야 함")
    conn = get_conn()
    po_id = insert_returning(
        conn, "INSERT INTO purchase_order (vendor_id, pr_id, po_type) VALUES (?,?,?)",
        (body["vendor_id"], body.get("pr_id"), po_type), "po_id",
    )
    for line in body["lines"]:
        require(line, "material_id", "qty")
        run(conn, "INSERT INTO po_line (po_id, material_id, qty, price) VALUES (?,?,?,?)",
            (po_id, line["material_id"], line["qty"], line.get("price", 0)))
    if body.get("pr_id"):
        run(conn, "UPDATE purchase_requisition SET status='CONVERTED' WHERE pr_id=?", (body["pr_id"],))
    conn.commit()
    conn.close()
    return {"po_id": po_id}


@app.post("/api/purchase-orders/{po_id}/goods-receipts")
def create_goods_receipt(po_id: int, body: dict = Body(...), user: dict = Depends(require_roles("구매담당", "관리자"))):
    require(body, "warehouse_id")
    conn = get_conn()
    po = one(run(conn, "SELECT * FROM purchase_order WHERE po_id=?", (po_id,)))
    if po is None:
        conn.close()
        raise HTTPException(404, "발주를 찾을 수 없음")
    po_lines = rows_to_list(run(conn, "SELECT * FROM po_line WHERE po_id=?", (po_id,)))
    total_amount = 0
    for pl in po_lines:
        gr_id = insert_returning(
            conn, "INSERT INTO goods_receipt (po_line_id, warehouse_id, qty) VALUES (?,?,?)",
            (pl["po_line_id"], body["warehouse_id"], pl["qty"]), "gr_id",
        )
        adjust_inventory(conn, pl["material_id"], body["warehouse_id"], pl["qty"], "IN", "GOODS_RECEIPT", gr_id)
        create_lot(conn, pl["material_id"], body["warehouse_id"], pl["qty"], "GOODS_RECEIPT", gr_id)
        total_amount += pl["qty"] * pl["price"]
    ap_id = insert_returning(
        conn, "INSERT INTO ap_invoice (vendor_id, po_id, amount) VALUES (?,?,?)",
        (po["vendor_id"], po_id, total_amount), "ap_id",
    )
    post_accounting(
        conn, "AP_INVOICE", f"PO#{po_id} 입고 계상",
        [("1200", total_amount, 0), ("2000", 0, total_amount)],
    )
    run(conn, "UPDATE purchase_order SET status='RECEIVED' WHERE po_id=?", (po_id,))
    conn.commit()
    conn.close()
    return {"ap_id": ap_id, "amount": total_amount}


# ---------- Production ----------
@app.get("/api/production-orders")
def list_prod_orders(user: dict = Depends(current_user)):
    conn = get_conn()
    rows = rows_to_list(run(
        conn,
        "SELECT p.*, m.name AS material_name, v.name AS vendor_name FROM production_order p "
        "JOIN material m ON m.material_id = p.material_id "
        "LEFT JOIN vendor v ON v.vendor_id = p.vendor_id ORDER BY p.prod_order_id DESC"
    ))
    conn.close()
    return rows


@app.post("/api/production-orders")
def create_prod_order(body: dict = Body(...), user: dict = Depends(require_roles("생산담당", "관리자"))):
    require(body, "material_id", "plant_id", "qty")
    conn = get_conn()
    # v13: 외주생산 구분 — is_outsourced=1이면 vendor_id(외주처) 필수
    is_outsourced = 1 if body.get("is_outsourced") else 0
    vendor_id = body.get("vendor_id")
    if is_outsourced and not vendor_id:
        conn.close()
        raise HTTPException(400, "외주생산은 vendor_id(외주처)가 필요함")
    if vendor_id is not None:
        if one(run(conn, "SELECT vendor_id FROM vendor WHERE vendor_id=?", (vendor_id,))) is None:
            conn.close()
            raise HTTPException(404, "외주처(공급업체)를 찾을 수 없음")
    prod_order_id = insert_returning(
        conn, "INSERT INTO production_order (material_id, plant_id, qty, is_outsourced, vendor_id) VALUES (?,?,?,?,?)",
        (body["material_id"], body["plant_id"], body["qty"], is_outsourced, vendor_id), "prod_order_id",
    )
    conn.commit()
    conn.close()
    return {"prod_order_id": prod_order_id}


@app.post("/api/production-orders/{prod_order_id}/work-orders")
def create_work_order(prod_order_id: int, body: dict = Body(...), user: dict = Depends(require_roles("생산담당", "관리자"))):
    conn = get_conn()
    po = one(run(conn, "SELECT * FROM production_order WHERE prod_order_id=?", (prod_order_id,)))
    if po is None:
        conn.close()
        raise HTTPException(404, "생산오더를 찾을 수 없음")
    work_order_id = insert_returning(
        conn, "INSERT INTO work_order (prod_order_id, routing_step) VALUES (?,?)",
        (prod_order_id, body.get("routing_step", "ASSEMBLY")), "work_order_id",
    )
    run(conn, "UPDATE production_order SET status='IN_PROGRESS' WHERE prod_order_id=?", (prod_order_id,))
    conn.commit()
    conn.close()
    return {"work_order_id": work_order_id}


@app.post("/api/work-orders/{work_order_id}/results")
def create_result(work_order_id: int, body: dict = Body(...), user: dict = Depends(require_roles("생산담당", "관리자"))):
    require(body, "qty_good", "warehouse_id")
    conn = get_conn()
    wo = one(run(conn, "SELECT * FROM work_order WHERE work_order_id=?", (work_order_id,)))
    if wo is None:
        conn.close()
        raise HTTPException(404, "작업지시를 찾을 수 없음")
    # v13: 생산마감된 월(오늘 날짜 기준)에는 실적 입력 불가
    assert_period_not_closed(conn, None)
    po = one(run(conn, "SELECT * FROM production_order WHERE prod_order_id=?", (wo["prod_order_id"],)))
    qty_good = body["qty_good"]
    qty_defect = body.get("qty_defect", 0)
    warehouse_id = body["warehouse_id"]

    result_id = insert_returning(
        conn, "INSERT INTO production_result (work_order_id, qty_good, qty_defect) VALUES (?,?,?)",
        (work_order_id, qty_good, qty_defect), "result_id",
    )

    bom_lines = rows_to_list(run(conn, "SELECT * FROM bom WHERE parent_material_id=?", (po["material_id"],)))
    for b in bom_lines:
        consumed_qty = qty_good * b["qty"]
        adjust_inventory(
            conn, b["child_material_id"], warehouse_id, -consumed_qty, "OUT", "PRODUCTION_RESULT", result_id
        )
        consume_lots_fifo(conn, b["child_material_id"], warehouse_id, consumed_qty, "PRODUCTION_RESULT", result_id)
    adjust_inventory(conn, po["material_id"], warehouse_id, qty_good, "IN", "PRODUCTION_RESULT", result_id)
    fg_lot = create_lot(conn, po["material_id"], warehouse_id, qty_good, "PRODUCTION_RESULT", result_id)
    serials = []
    if fg_lot and body.get("generate_serials"):
        serials = generate_serials(conn, po["material_id"], fg_lot["lot_id"], qty_good)

    run(conn, "UPDATE work_order SET status='DONE' WHERE work_order_id=?", (work_order_id,))
    run(conn, "UPDATE production_order SET status='COMPLETED' WHERE prod_order_id=?", (wo["prod_order_id"],))
    conn.commit()
    conn.close()
    return {"result_id": result_id, "lot": fg_lot, "serials": serials}


# ---------- Inventory ----------
@app.get("/api/inventory")
def list_inventory(user: dict = Depends(current_user)):
    conn = get_conn()
    rows = rows_to_list(run(
        conn,
        "SELECT i.*, m.code, m.name AS material_name, w.name AS warehouse_name "
        "FROM inventory i JOIN material m ON m.material_id=i.material_id "
        "JOIN warehouse w ON w.warehouse_id=i.warehouse_id ORDER BY i.inventory_id"
    ))
    conn.close()
    return rows


@app.get("/api/inventory/transactions")
def list_inventory_txns(user: dict = Depends(current_user)):
    conn = get_conn()
    rows = rows_to_list(run(
        conn,
        "SELECT t.*, m.name AS material_name FROM inventory_transaction t "
        "JOIN material m ON m.material_id=t.material_id ORDER BY t.txn_id DESC LIMIT 100"
    ))
    conn.close()
    return rows


# ---------- Finance ----------
# v5: 회계 전표/계정과목은 재무 민감정보라 조회도 관리자 전용으로 좁힌다(task-plan-v5.md 참고).
@app.get("/api/accounting/documents")
def list_acc_docs(user: dict = Depends(require_roles("관리자"))):
    conn = get_conn()
    rows = rows_to_list(run(conn, "SELECT * FROM accounting_document ORDER BY doc_id DESC"))
    conn.close()
    return rows


@app.get("/api/accounting/documents/{doc_id}")
def get_acc_doc(doc_id: int, user: dict = Depends(require_roles("관리자"))):
    conn = get_conn()
    doc = one(run(conn, "SELECT * FROM accounting_document WHERE doc_id=?", (doc_id,)))
    if doc is None:
        conn.close()
        raise HTTPException(404, "전표를 찾을 수 없음")
    lines = rows_to_list(run(
        conn,
        "SELECT l.*, a.code, a.name AS account_name FROM accounting_line l "
        "JOIN gl_account a ON a.account_id=l.account_id WHERE doc_id=?",
        (doc_id,),
    ))
    conn.close()
    return {**doc, "lines": lines}


@app.get("/api/gl-accounts")
def list_gl_accounts(user: dict = Depends(require_roles("관리자"))):
    conn = get_conn()
    rows = rows_to_list(run(conn, "SELECT * FROM gl_account ORDER BY account_id"))
    conn.close()
    return rows


@app.post("/api/accounting/documents")
def create_manual_doc(body: dict = Body(...), user: dict = Depends(require_roles("관리자"))):
    require(body, "lines")
    lines = [(l["account_code"], l.get("debit", 0), l.get("credit", 0)) for l in body["lines"]]
    total_debit = sum(l[1] for l in lines)
    total_credit = sum(l[2] for l in lines)
    if round(total_debit, 2) != round(total_credit, 2):
        raise HTTPException(400, "차변/대변 합계가 일치해야 함")
    conn = get_conn()
    doc_id = post_accounting(conn, "MANUAL", body.get("description", ""), lines)
    conn.commit()
    conn.close()
    return {"doc_id": doc_id}


# ---------- Common ----------
@app.get("/api/users")
def list_users(user: dict = Depends(current_user)):
    conn = get_conn()
    rows = rows_to_list(run(conn, "SELECT user_id, name, email FROM app_user ORDER BY user_id"))
    conn.close()
    return rows


# v8: 시리얼 상태변경(불량/폐기 등)과 refresh token 재사용(탈취 의심) 탐지 이벤트를 audit_log에 남긴다
# (app/helpers.py의 write_audit_log, app/lot_tracking.py/app/main.py의 refresh 참고). 조회는 감사
# 이력이라 회계/CFO Copilot과 동일하게 관리자 전용으로 좁힌다.
@app.get("/api/audit-log")
def list_audit_log(user: dict = Depends(require_roles("관리자"))):
    conn = get_conn()
    rows = rows_to_list(run(
        conn,
        "SELECT a.*, u.name AS user_name FROM audit_log a LEFT JOIN app_user u ON u.user_id = a.user_id "
        "ORDER BY a.log_id DESC LIMIT 200",
    ))
    conn.close()
    return rows


# Light ERP Prototype 공통 접속 비밀번호 (역할별 로그인 없음)
ACCESS_PASSWORD = os.environ.get("ACCESS_PASSWORD", "ax2026h2")
ACCESS_USER_EMAIL = os.environ.get("ACCESS_USER_EMAIL", "admin@standard-erp.local")


@app.post("/api/auth/login")
def login(body: dict = Body(...), user_agent: str = Header(None)):
    """단일 접속 비밀번호로 로그인한다. 성공 시 관리자(기본) 세션을 발급한다.
    비밀번호만 보내면 공통 게이트로 처리하고, email+password는 기존 계정 로그인(테스트용)도 허용한다."""
    password = (body or {}).get("password")
    email = (body or {}).get("email")
    if not password:
        raise HTTPException(400, "password는 필수입니다")

    conn = get_conn()
    user = None
    if email:
        user = one(run(conn, "SELECT * FROM app_user WHERE email=?", (email,)))
        if user is None or not verify_password(password, user["password_hash"]):
            conn.close()
            raise HTTPException(401, "접속 비밀번호가 올바르지 않습니다")
    else:
        # 공통 접속 게이트 — 역할별/페이지별 로그인 없음
        if password != ACCESS_PASSWORD:
            conn.close()
            raise HTTPException(401, "접속 비밀번호가 올바르지 않습니다")
        user = one(run(conn, "SELECT * FROM app_user WHERE email=?", (ACCESS_USER_EMAIL,)))
        if user is None:
            conn.close()
            raise HTTPException(500, "접속용 계정이 없습니다. 시드를 먼저 실행하세요")

    if not user.get("is_active", 1):
        conn.close()
        raise HTTPException(403, "비활성화된 계정입니다")
    tokens = issue_tokens(conn, user["user_id"], user["name"], user["email"], user_agent=user_agent)
    conn.commit()
    conn.close()
    return {
        "access_token": tokens["access_token"],
        "refresh_token": tokens["refresh_token"],
        "user": {"user_id": user["user_id"], "name": user["name"], "email": user["email"], "roles": tokens["roles"]},
    }


@app.post("/api/auth/sso")
def login_with_sso(authorization: str = Header(None), user_agent: str = Header(None)):
    """Keycloak access token을 JWKS로 로컬 검증한 뒤 기존 활성 ERP 사용자에게만 도메인 세션을 발급한다.

    검증 항목은 서명(RS256), iss, exp, azp(ax-erp-web), openid scope다. azp를 확인하지 않으면 Realm 내
    다른 클라이언트의 토큰까지 ERP 세션으로 교환되는 confused deputy가 생긴다.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "SSO 토큰이 필요합니다")
    token = authorization[len("Bearer "):].strip()
    try:
        claims = verify_access_token(token)
    except OidcUnavailable:
        raise HTTPException(503, "SSO 사용자 정보를 확인할 수 없습니다")
    except OidcTokenInvalid as e:
        raise HTTPException(401, str(e))
    email = claims.get("email")
    if not email:
        raise HTTPException(401, "SSO 계정 이메일이 없습니다")
    conn = get_conn()
    user = one(run(conn, "SELECT * FROM app_user WHERE email=?", (email,)))
    # is_active는 0010 마이그레이션으로 추가된다. stamp head로 넘어온 구 DB를 대비해 기본값을 둔다.
    if user is None or not user.get("is_active", 1):
        conn.close()
        raise HTTPException(403, "ERP 접근 권한이 없습니다")
    tokens = issue_tokens(conn, user["user_id"], user["name"], user["email"], user_agent=user_agent)
    conn.commit()
    conn.close()
    return {
        "access_token": tokens["access_token"],
        "refresh_token": tokens["refresh_token"],
        "user": {"user_id": user["user_id"], "name": user["name"], "email": user["email"], "roles": tokens["roles"]},
    }


@app.post("/api/auth/refresh")
def refresh(body: dict = Body(...)):
    """refresh_token으로 새 access_token+refresh_token을 재발급한다(v6: 회전+재사용 탐지,
    task-plan-refresh-rotation.md). 이미 회전으로 폐기된 토큰이 다시 제시되면 탈취로 간주해
    해당 로그인의 모든 세션을 무효화하고 401을 반환한다."""
    require(body, "refresh_token")
    conn = get_conn()
    try:
        tokens = rotate_tokens(conn, body["refresh_token"])
    except RefreshTokenReuseDetected as e:
        write_audit_log(conn, e.user_id, "REFRESH_TOKEN_REUSE_DETECTED", "session", None)
        conn.commit()
        conn.close()
        logger.warning(
            "refresh token 재사용 감지(탈취 의심) — user_id=%s family_id=%s, 해당 로그인의 모든 세션 무효화",
            e.user_id, e.family_id,
        )
        raise HTTPException(401, "보안 경고: 이미 사용된 refresh token이 재사용되었습니다. 모든 세션이 무효화되었습니다 — 다시 로그인하세요.")
    conn.commit()
    conn.close()
    if tokens is None:
        raise HTTPException(401, "refresh token이 유효하지 않습니다. 다시 로그인하세요")
    return tokens


@app.post("/api/auth/logout")
def logout(body: dict = Body(...)):
    """refresh_token이 속한 family 전체(회전으로 발급된 이전/이후 토큰 포함)를 즉시 삭제해 재발급을
    차단한다. 이미 발급된 access_token은 자연 만료(최대 30분)까지는 여전히 유효하다 — 완전
    무상태화의 의도된 트레이드오프(task-plan-v5.md)."""
    refresh_token = body.get("refresh_token")
    if refresh_token:
        conn = get_conn()
        delete_refresh_token(conn, refresh_token)
        conn.commit()
        conn.close()
    return {"ok": True}


@app.get("/api/auth/me")
def whoami(user: dict = Depends(current_user)):
    return user


# v8: 디바이스별 다중 세션 조회/개별 로그아웃. family_id별로 회전으로 폐기되지 않은(rotated_at IS NULL)
# 최신 행 하나만 "현재 유효한 세션(기기)"이므로 그 행만 노출한다(migrations/0003_session_device_info.py).
@app.get("/api/auth/sessions")
def list_my_sessions(user: dict = Depends(current_user)):
    conn = get_conn()
    rows = rows_to_list(run(
        conn,
        "SELECT family_id, user_agent, created_at, last_seen_at, expires_at FROM session "
        "WHERE user_id=? AND rotated_at IS NULL ORDER BY last_seen_at DESC",
        (user["user_id"],),
    ))
    conn.close()
    return rows


@app.post("/api/auth/sessions/{family_id}/logout")
def logout_session(family_id: str, user: dict = Depends(current_user)):
    """다른 세션(기기)을 개별 로그아웃한다. family_id를 소유한 사용자 본인인지 반드시 확인한다
    (확인 없이 지우면 family_id를 추측해 남의 세션을 강제 로그아웃시킬 수 있다)."""
    conn = get_conn()
    owner = one(run(conn, "SELECT user_id FROM session WHERE family_id=? LIMIT 1", (family_id,)))
    if owner is None or owner["user_id"] != user["user_id"]:
        conn.close()
        raise HTTPException(404, "세션을 찾을 수 없습니다")
    run(conn, "DELETE FROM session WHERE family_id=?", (family_id,))
    conn.commit()
    conn.close()
    return {"ok": True}


@app.get("/api/approvals")
def list_approvals(user: dict = Depends(current_user)):
    conn = get_conn()
    rows = rows_to_list(run(conn, "SELECT * FROM approval_workflow ORDER BY workflow_id DESC"))
    conn.close()
    return rows


@app.post("/api/approvals/{workflow_id}/decision")
def decide_approval(workflow_id: int, body: dict = Body(...), user: dict = Depends(require_roles("관리자"))):
    require(body, "status")
    if body["status"] not in ("APPROVED", "REJECTED"):
        raise HTTPException(400, "status는 APPROVED 또는 REJECTED여야 함")
    conn = get_conn()
    wf = one(run(conn, "SELECT * FROM approval_workflow WHERE workflow_id=?", (workflow_id,)))
    if wf is None:
        conn.close()
        raise HTTPException(404, "승인건을 찾을 수 없음")
    run(conn, "UPDATE approval_workflow SET status=? WHERE workflow_id=?", (body["status"], workflow_id))
    if wf["doc_type"] == "PR" and body["status"] == "APPROVED":
        run(conn, "UPDATE purchase_requisition SET status='APPROVED' WHERE pr_id=?", (wf["doc_id"],))
    elif wf["doc_type"] == "QUOTATION":
        # v9: 견적 승인/반려. 승인 후 수주 전환은 별도 API(POST /quotations/{id}/convert-to-order)에서 처리.
        new_status = "APPROVED" if body["status"] == "APPROVED" else "REJECTED"
        run(conn, "UPDATE quotation SET status=? WHERE quotation_id=?", (new_status, wf["doc_id"]))
    elif wf["doc_type"] == "SALES_RETURN":
        # v9: 반품 승인 시에만 재고를 복원한다(반려는 상태만 바뀌고 재고는 그대로).
        new_status = "APPROVED" if body["status"] == "APPROVED" else "REJECTED"
        run(conn, "UPDATE sales_return SET status=? WHERE return_id=?", (new_status, wf["doc_id"]))
        if body["status"] == "APPROVED":
            lines = rows_to_list(run(
                conn, "SELECT * FROM sales_return_line WHERE return_id=?", (wf["doc_id"],),
            ))
            for line in lines:
                adjust_inventory(
                    conn, line["material_id"], line["warehouse_id"], line["qty"],
                    "IN", "SALES_RETURN", wf["doc_id"],
                )
            write_audit_log(conn, user["user_id"], "SALES_RETURN_APPROVED", "sales_return", wf["doc_id"])
    conn.commit()
    conn.close()
    return {"ok": True}


# ---------- Dashboard ----------
@app.get("/api/dashboard/kpi")
def dashboard_kpi(user: dict = Depends(current_user)):
    conn = get_conn()
    open_so = one(run(conn, "SELECT COUNT(*) c FROM sales_order WHERE status='OPEN'"))["c"]
    open_po = one(run(conn, "SELECT COUNT(*) c FROM purchase_order WHERE status='OPEN'"))["c"]
    pending_approvals = one(run(conn, "SELECT COUNT(*) c FROM approval_workflow WHERE status='PENDING'"))["c"]
    material_count = one(run(conn, "SELECT COUNT(*) c FROM material"))["c"]
    total_ar = one(run(conn, "SELECT COALESCE(SUM(amount),0) s FROM sales_invoice WHERE status='OPEN'"))["s"]
    total_ap = one(run(conn, "SELECT COALESCE(SUM(amount),0) s FROM ap_invoice WHERE status='OPEN'"))["s"]
    # v8: LOT 정합성 점검(기존엔 /lots/reconciliation 온디맨드 조회만 있었음)을 대시보드에 상시 노출
    lot_inconsistent_count = count_lot_inconsistencies(conn)
    conn.close()
    return {
        "open_so": open_so,
        "open_po": open_po,
        "pending_approvals": pending_approvals,
        "material_count": material_count,
        "total_ar": total_ar,
        "total_ap": total_ap,
        "lot_inconsistent_count": lot_inconsistent_count,
    }


# ---------- SPA fallback ----------
# React Router 딥링크(/procurement 등) 직접 접근/새로고침 시 404가 나지 않도록
# 마지막에 등록하는 catch-all. API/정적 경로는 제외해 기존 404 동작을 유지한다.
@app.get("/{full_path:path}", include_in_schema=False)
def spa_fallback(full_path: str):
    if full_path.startswith(("api/", "assets/")) or full_path == "health":
        raise HTTPException(404, "Not Found")
    dist_index = FRONTEND_DIST_DIR / "index.html"
    if dist_index.exists():
        return FileResponse(dist_index)
    raise HTTPException(404, "Not Found")
