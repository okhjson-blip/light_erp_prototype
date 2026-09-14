"""01. Sales Management 확장 (v9) — 가격정책/견적/판매계약/반품/서비스오더 + 영업 KPI/실적/손익.

1.0_AX_ERP_Menu_Structure.md "01. Sales Management" 중 그동안 없던 항목을 추가한다
(task-plan-v9-full-menu-rollout.md §3 v9 참고). 기존 sales_order/sales_invoice 로직(app/main.py)은
건드리지 않고 이 모듈에서 확장만 한다.

견적(quotation)/반품(sales_return)은 기존 범용 approval_workflow(PR/PO와 동일 테이블)에 등록해
승인함(GET /api/approvals, POST /api/approvals/{id}/decision — app/main.py)을 그대로 재사용한다.
승인 후 처리(quotation→APPROVED, sales_return→재고복원)는 app/main.py의 decide_approval()에서
doc_type 분기로 처리한다(이 파일에는 승인 후처리 로직을 두지 않음 — 단일 지점에서만 승인을 처리해
"승인 처리가 두 곳에 흩어지는" 혼란을 피한다).
"""
from datetime import date

from fastapi import APIRouter, Body, Depends, HTTPException

from .database import get_conn, run, one, rows_to_list, insert_returning
from .helpers import require
from .auth import require_roles, current_user

router = APIRouter(prefix="/api", tags=["sales-ext"])


# ---------- 가격정책 관리 ----------

@router.get("/price-policies")
def list_price_policies(user: dict = Depends(current_user)):
    conn = get_conn()
    rows = rows_to_list(run(
        conn,
        "SELECT p.*, m.name AS material_name, c.name AS customer_name FROM price_policy p "
        "JOIN material m ON m.material_id = p.material_id "
        "LEFT JOIN customer c ON c.customer_id = p.customer_id "
        "ORDER BY p.price_policy_id DESC",
    ))
    conn.close()
    return rows


@router.post("/price-policies")
def create_price_policy(body: dict = Body(...), user: dict = Depends(require_roles("영업담당", "관리자"))):
    require(body, "material_id", "unit_price")
    conn = get_conn()
    price_policy_id = insert_returning(
        conn,
        "INSERT INTO price_policy (material_id, customer_id, unit_price, valid_to) VALUES (?,?,?,?)",
        (body["material_id"], body.get("customer_id"), body["unit_price"], body.get("valid_to")),
        "price_policy_id",
    )
    conn.commit()
    conn.close()
    return {"price_policy_id": price_policy_id}


@router.get("/price-policies/lookup")
def lookup_price(material_id: int, customer_id: int | None = None, user: dict = Depends(current_user)):
    """견적/수주 라인 단가 자동제안용. 고객전용 정책이 있으면 우선, 없으면 일반(전체고객) 정책,
    둘 다 없으면 unit_price=None을 반환해(404 아님) 프론트가 수동입력으로 자연스럽게 넘어가게 한다."""
    conn = get_conn()
    today = date.today().isoformat()
    row = None
    if customer_id is not None:
        row = one(run(
            conn,
            "SELECT * FROM price_policy WHERE material_id=? AND customer_id=? "
            "AND valid_from <= ? AND (valid_to IS NULL OR valid_to >= ?) "
            "ORDER BY valid_from DESC LIMIT 1",
            (material_id, customer_id, today, today),
        ))
    if row is None:
        row = one(run(
            conn,
            "SELECT * FROM price_policy WHERE material_id=? AND customer_id IS NULL "
            "AND valid_from <= ? AND (valid_to IS NULL OR valid_to >= ?) "
            "ORDER BY valid_from DESC LIMIT 1",
            (material_id, today, today),
        ))
    conn.close()
    return {"unit_price": row["unit_price"] if row else None}


# ---------- 견적관리 ----------

@router.get("/quotations")
def list_quotations(user: dict = Depends(current_user)):
    conn = get_conn()
    rows = rows_to_list(run(
        conn,
        "SELECT q.*, c.name AS customer_name FROM quotation q "
        "JOIN customer c ON c.customer_id = q.customer_id ORDER BY q.quotation_id DESC",
    ))
    conn.close()
    return rows


@router.get("/quotations/{quotation_id}")
def get_quotation(quotation_id: int, user: dict = Depends(current_user)):
    conn = get_conn()
    q = one(run(conn, "SELECT * FROM quotation WHERE quotation_id=?", (quotation_id,)))
    if q is None:
        conn.close()
        raise HTTPException(404, "견적을 찾을 수 없음")
    lines = rows_to_list(run(
        conn,
        "SELECT l.*, m.name AS material_name FROM quotation_line l "
        "JOIN material m ON m.material_id = l.material_id WHERE quotation_id=?",
        (quotation_id,),
    ))
    conn.close()
    return {**q, "lines": lines}


@router.post("/quotations")
def create_quotation(body: dict = Body(...), user: dict = Depends(require_roles("영업담당", "관리자"))):
    require(body, "customer_id", "lines")
    if not body["lines"]:
        raise HTTPException(400, "최소 1개 라인이 필요함")
    conn = get_conn()
    quotation_id = insert_returning(
        conn, "INSERT INTO quotation (customer_id) VALUES (?)", (body["customer_id"],), "quotation_id",
    )
    for line in body["lines"]:
        require(line, "material_id", "qty")
        unit_price = line.get("unit_price")
        if unit_price is None:
            priced = one(run(
                conn,
                "SELECT unit_price FROM price_policy WHERE material_id=? AND "
                "(customer_id=? OR customer_id IS NULL) AND valid_from <= date('now') "
                "AND (valid_to IS NULL OR valid_to >= date('now')) "
                "ORDER BY customer_id IS NULL, valid_from DESC LIMIT 1",
                (line["material_id"], body["customer_id"]),
            ))
            unit_price = priced["unit_price"] if priced else 0
        run(
            conn, "INSERT INTO quotation_line (quotation_id, material_id, qty, unit_price) VALUES (?,?,?,?)",
            (quotation_id, line["material_id"], line["qty"], unit_price),
        )
    run(conn, "INSERT INTO approval_workflow (doc_type, doc_id) VALUES ('QUOTATION', ?)", (quotation_id,))
    conn.commit()
    conn.close()
    return {"quotation_id": quotation_id}


@router.post("/quotations/{quotation_id}/convert-to-order")
def convert_quotation(quotation_id: int, user: dict = Depends(require_roles("영업담당", "관리자"))):
    conn = get_conn()
    q = one(run(conn, "SELECT * FROM quotation WHERE quotation_id=?", (quotation_id,)))
    if q is None:
        conn.close()
        raise HTTPException(404, "견적을 찾을 수 없음")
    if q["status"] != "APPROVED":
        conn.close()
        raise HTTPException(400, "승인된 견적만 수주로 전환할 수 있음")
    lines = rows_to_list(run(conn, "SELECT * FROM quotation_line WHERE quotation_id=?", (quotation_id,)))
    so_id = insert_returning(
        conn, "INSERT INTO sales_order (customer_id) VALUES (?)", (q["customer_id"],), "so_id",
    )
    for line in lines:
        run(
            conn, "INSERT INTO sales_order_line (so_id, material_id, qty, price) VALUES (?,?,?,?)",
            (so_id, line["material_id"], line["qty"], line["unit_price"]),
        )
    run(conn, "UPDATE quotation SET status='CONVERTED', converted_so_id=? WHERE quotation_id=?", (so_id, quotation_id))
    conn.commit()
    conn.close()
    return {"so_id": so_id}


# ---------- 판매계약관리 ----------

@router.get("/sales-contracts")
def list_sales_contracts(user: dict = Depends(current_user)):
    conn = get_conn()
    rows = rows_to_list(run(
        conn,
        "SELECT sc.*, c.name AS customer_name FROM sales_contract sc "
        "JOIN customer c ON c.customer_id = sc.customer_id ORDER BY sc.contract_id DESC",
    ))
    conn.close()
    return rows


@router.post("/sales-contracts")
def create_sales_contract(body: dict = Body(...), user: dict = Depends(require_roles("영업담당", "관리자"))):
    require(body, "customer_id", "start_date")
    conn = get_conn()
    contract_id = insert_returning(
        conn,
        "INSERT INTO sales_contract (customer_id, start_date, end_date, terms) VALUES (?,?,?,?)",
        (body["customer_id"], body["start_date"], body.get("end_date"), body.get("terms")),
        "contract_id",
    )
    conn.commit()
    conn.close()
    return {"contract_id": contract_id}


# ---------- 반품관리 ----------

@router.get("/sales-returns")
def list_sales_returns(user: dict = Depends(current_user)):
    conn = get_conn()
    rows = rows_to_list(run(
        conn,
        "SELECT sr.*, c.name AS customer_name FROM sales_return sr "
        "JOIN customer c ON c.customer_id = sr.customer_id ORDER BY sr.return_id DESC",
    ))
    conn.close()
    return rows


@router.post("/sales-returns")
def create_sales_return(body: dict = Body(...), user: dict = Depends(require_roles("영업담당", "관리자"))):
    require(body, "so_id", "lines")
    if not body["lines"]:
        raise HTTPException(400, "최소 1개 라인이 필요함")
    conn = get_conn()
    so = one(run(conn, "SELECT * FROM sales_order WHERE so_id=?", (body["so_id"],)))
    if so is None:
        conn.close()
        raise HTTPException(404, "원본 수주를 찾을 수 없음")
    return_id = insert_returning(
        conn,
        "INSERT INTO sales_return (so_id, customer_id, reason) VALUES (?,?,?)",
        (body["so_id"], so["customer_id"], body.get("reason")),
        "return_id",
    )
    for line in body["lines"]:
        require(line, "material_id", "qty", "warehouse_id")
        run(
            conn, "INSERT INTO sales_return_line (return_id, material_id, qty, warehouse_id) VALUES (?,?,?,?)",
            (return_id, line["material_id"], line["qty"], line["warehouse_id"]),
        )
    run(conn, "INSERT INTO approval_workflow (doc_type, doc_id) VALUES ('SALES_RETURN', ?)", (return_id,))
    conn.commit()
    conn.close()
    return {"return_id": return_id}


# ---------- 서비스오더관리 ----------

SERVICE_ORDER_STATUSES = {"RECEIVED", "IN_PROGRESS", "COMPLETED", "CANCELLED"}


@router.get("/service-orders")
def list_service_orders(user: dict = Depends(current_user)):
    conn = get_conn()
    rows = rows_to_list(run(
        conn,
        "SELECT so.*, c.name AS customer_name, m.name AS material_name FROM service_order so "
        "JOIN customer c ON c.customer_id = so.customer_id "
        "LEFT JOIN material m ON m.material_id = so.material_id "
        "ORDER BY so.service_order_id DESC",
    ))
    conn.close()
    return rows


@router.post("/service-orders")
def create_service_order(body: dict = Body(...), user: dict = Depends(require_roles("영업담당", "관리자"))):
    require(body, "customer_id")
    conn = get_conn()
    service_order_id = insert_returning(
        conn,
        "INSERT INTO service_order (customer_id, material_id, symptom) VALUES (?,?,?)",
        (body["customer_id"], body.get("material_id"), body.get("symptom")),
        "service_order_id",
    )
    conn.commit()
    conn.close()
    return {"service_order_id": service_order_id}


@router.post("/service-orders/{service_order_id}/status")
def update_service_order_status(
    service_order_id: int, body: dict = Body(...), user: dict = Depends(require_roles("영업담당", "관리자")),
):
    require(body, "status")
    if body["status"] not in SERVICE_ORDER_STATUSES:
        raise HTTPException(400, f"status는 {', '.join(sorted(SERVICE_ORDER_STATUSES))} 중 하나여야 함")
    conn = get_conn()
    so = one(run(conn, "SELECT service_order_id FROM service_order WHERE service_order_id=?", (service_order_id,)))
    if so is None:
        conn.close()
        raise HTTPException(404, "서비스오더를 찾을 수 없음")
    run(conn, "UPDATE service_order SET status=? WHERE service_order_id=?", (body["status"], service_order_id))
    conn.commit()
    conn.close()
    return {"service_order_id": service_order_id, "status": body["status"]}


# ---------- 채권조회 / 영업실적 / 손익분석 / 영업 KPI ----------

@router.get("/ar/receivables")
def ar_receivables(user: dict = Depends(current_user)):
    """미결(OPEN) 매출채권을 고객별로 상세 조회한다. payment_term(NET30 등)에서 숫자만 뽑아
    invoice_date + N일을 근사 만기일로 계산하고, 오늘 기준 초과 여부를 overdue로 표시한다."""
    conn = get_conn()
    rows = rows_to_list(run(
        conn,
        "SELECT si.*, c.name AS customer_name, c.payment_term FROM sales_invoice si "
        "JOIN customer c ON c.customer_id = si.customer_id WHERE si.status='OPEN' "
        "ORDER BY si.invoice_date",
    ))
    conn.close()
    today = date.today()
    for r in rows:
        term = r.get("payment_term") or "NET30"
        digits = "".join(ch for ch in term if ch.isdigit())
        net_days = int(digits) if digits else 30
        due = date.fromisoformat(r["invoice_date"][:10])
        due = date.fromordinal(due.toordinal() + net_days)
        r["due_date"] = due.isoformat()
        r["overdue"] = due < today
    return rows


@router.get("/sales/performance")
def sales_performance(group_by: str = "customer", user: dict = Depends(current_user)):
    """담당자별 실적은 sales_order에 담당자 컬럼이 없어 비범위 — 고객/품목/월 기준 집계만 제공."""
    conn = get_conn()
    if group_by == "material":
        rows = rows_to_list(run(
            conn,
            "SELECT m.name AS group_label, SUM(l.qty) AS total_qty, SUM(l.qty * l.price) AS total_amount "
            "FROM sales_order_line l JOIN material m ON m.material_id = l.material_id "
            "GROUP BY m.material_id, m.name ORDER BY total_amount DESC",
        ))
    elif group_by == "month":
        rows = rows_to_list(run(
            conn,
            "SELECT substr(so.order_date, 1, 7) AS group_label, COUNT(DISTINCT so.so_id) AS order_count, "
            "SUM(l.qty * l.price) AS total_amount FROM sales_order so "
            "JOIN sales_order_line l ON l.so_id = so.so_id "
            "GROUP BY substr(so.order_date, 1, 7) ORDER BY group_label DESC",
        ))
    else:
        rows = rows_to_list(run(
            conn,
            "SELECT c.name AS group_label, COUNT(DISTINCT so.so_id) AS order_count, "
            "SUM(l.qty * l.price) AS total_amount FROM sales_order so "
            "JOIN customer c ON c.customer_id = so.customer_id "
            "JOIN sales_order_line l ON l.so_id = so.so_id "
            "GROUP BY c.customer_id, c.name ORDER BY total_amount DESC",
        ))
    conn.close()
    return rows


@router.get("/sales/profitability")
def sales_profitability(group_by: str = "customer", user: dict = Depends(current_user)):
    """매출(qty*price) - 원가(qty*material.std_cost, 미설정 시 0)의 단순 차감 손익.
    실제 배부/공통비는 09.Controlling(COPA) 완료 후 정교화 예정 — 이번은 간이 근사치."""
    conn = get_conn()
    if group_by == "material":
        rows = rows_to_list(run(
            conn,
            "SELECT m.name AS group_label, SUM(l.qty * l.price) AS revenue, "
            "SUM(l.qty * COALESCE(m.std_cost, 0)) AS cost "
            "FROM sales_order_line l JOIN material m ON m.material_id = l.material_id "
            "GROUP BY m.material_id, m.name ORDER BY revenue DESC",
        ))
    else:
        rows = rows_to_list(run(
            conn,
            "SELECT c.name AS group_label, SUM(l.qty * l.price) AS revenue, "
            "SUM(l.qty * COALESCE(m.std_cost, 0)) AS cost "
            "FROM sales_order so JOIN customer c ON c.customer_id = so.customer_id "
            "JOIN sales_order_line l ON l.so_id = so.so_id "
            "JOIN material m ON m.material_id = l.material_id "
            "GROUP BY c.customer_id, c.name ORDER BY revenue DESC",
        ))
    conn.close()
    for r in rows:
        r["profit"] = round((r["revenue"] or 0) - (r["cost"] or 0), 2)
    return rows


@router.get("/sales/kpi")
def sales_kpi(user: dict = Depends(current_user)):
    conn = get_conn()
    this_month = date.today().isoformat()[:7]
    revenue_this_month = one(run(
        conn, "SELECT COALESCE(SUM(amount),0) s FROM sales_invoice WHERE substr(invoice_date,1,7)=?",
        (this_month,),
    ))["s"]
    backlog = one(run(
        conn,
        "SELECT COALESCE(SUM(l.qty * l.price),0) s FROM sales_order so "
        "JOIN sales_order_line l ON l.so_id = so.so_id WHERE so.status='OPEN'",
    ))["s"]
    orders_this_month = one(run(
        conn, "SELECT COUNT(*) c FROM sales_order WHERE substr(order_date,1,7)=?", (this_month,),
    ))["c"]
    customers_this_month = one(run(
        conn,
        "SELECT COUNT(DISTINCT customer_id) c FROM sales_order WHERE substr(order_date,1,7)=?",
        (this_month,),
    ))["c"]
    conn.close()
    return {
        "revenue_this_month": revenue_this_month,
        "open_backlog": backlog,
        "orders_this_month": orders_this_month,
        "customers_this_month": customers_this_month,
    }
