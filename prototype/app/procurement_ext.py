"""03. Procurement Management 확장 (v11) — 공급업체평가/구매계약/구매카테고리뷰/통관관리/구매실적/KPI.

1.0_AX_ERP_Menu_Structure.md "03. Procurement Management" 중 그동안 없던 항목을 추가한다
(task-plan-v9-full-menu-rollout.md §3 v11 참고). 기존 purchase_requisition/purchase_order/
goods_receipt 로직(app/main.py)은 건드리지 않고 이 모듈에서 확장만 한다(po_type 컬럼만 v9의
quotation/sales_return 승인 재사용 패턴과 달리 main.py의 create_po()에 최소 한 줄 추가 — 승인
워크플로가 필요 없는 단순 분류 컬럼이라 이 파일이 아닌 main.py에서 직접 처리).

- 공급업체평가: vendor_evaluation(납기/품질/가격 100점 만점 점수, 평가일). 승인 불필요 — 등록/조회만.
- 구매계약관리: purchase_contract — sales_contract(v9)와 동일 패턴(기간/조건 마스터, 등록/조회만).
- 원재료/부자재/설비/금형 구매: 신규 테이블 없이 material.material_type 필터 뷰로 대체
  (task-plan §3 v11 명시). 현재 시드 데이터셋의 material_type은 RM/FG만 존재 — SUB/EQUIP/MOLD
  카테고리는 향후 그런 material_type 값이 들어오면 별도 코드 변경 없이 자동으로 필터된다(알려진 범위 제한).
- 통관관리/수입관리: import_customs_record(PO 단위, 간이 — 정식 관세사 EDI 연동 없음).
- 구매실적관리: 기존 po_line/goods_receipt/ap_invoice를 집계하는 조회 전용 API(v9 영업실적과 동일 패턴).
- 구매 Dashboard: 위 지표 요약(신규 집계 없이 기존 엔드포인트 재사용 — SCM Control Tower와 동일 패턴).
"""
from datetime import date

from fastapi import APIRouter, Body, Depends, HTTPException

from .database import get_conn, run, one, rows_to_list, insert_returning
from .helpers import require
from .auth import require_roles, current_user

router = APIRouter(prefix="/api", tags=["procurement-ext"])


# ---------- 공급업체평가 ----------

@router.get("/vendor-evaluations")
def list_vendor_evaluations(user: dict = Depends(current_user)):
    conn = get_conn()
    rows = rows_to_list(run(
        conn,
        "SELECT e.*, v.name AS vendor_name FROM vendor_evaluation e "
        "JOIN vendor v ON v.vendor_id = e.vendor_id ORDER BY e.eval_id DESC",
    ))
    conn.close()
    for r in rows:
        r["total_score"] = round(
            (r["delivery_score"] + r["quality_score"] + r["price_score"]) / 3, 1
        )
    return rows


@router.post("/vendor-evaluations")
def create_vendor_evaluation(body: dict = Body(...), user: dict = Depends(require_roles("구매담당", "관리자"))):
    require(body, "vendor_id", "delivery_score", "quality_score", "price_score")
    conn = get_conn()
    vendor = one(run(conn, "SELECT vendor_id FROM vendor WHERE vendor_id=?", (body["vendor_id"],)))
    if vendor is None:
        conn.close()
        raise HTTPException(404, "공급업체를 찾을 수 없음")
    eval_id = insert_returning(
        conn,
        # eval_date를 명시적으로 넣는다 — DB 기본값 date('now')는 UTC라 KST 새벽에 하루 전으로 기록됨
        "INSERT INTO vendor_evaluation (vendor_id, eval_date, delivery_score, quality_score, price_score, notes) "
        "VALUES (?,?,?,?,?,?)",
        (body["vendor_id"], date.today().isoformat(), body["delivery_score"], body["quality_score"], body["price_score"], body.get("notes")),
        "eval_id",
    )
    conn.commit()
    conn.close()
    return {"eval_id": eval_id}


@router.get("/vendor-evaluations/summary")
def vendor_evaluation_summary(user: dict = Depends(current_user)):
    """공급업체별 최신 평가 기준 평균 점수 + 등급(간이 규칙: 80+/60~80/60미만)."""
    conn = get_conn()
    rows = rows_to_list(run(
        conn,
        "SELECT v.vendor_id, v.name AS vendor_name, "
        "AVG(e.delivery_score) AS avg_delivery, AVG(e.quality_score) AS avg_quality, "
        "AVG(e.price_score) AS avg_price, COUNT(*) AS eval_count "
        "FROM vendor_evaluation e JOIN vendor v ON v.vendor_id = e.vendor_id "
        "GROUP BY v.vendor_id, v.name ORDER BY v.name",
    ))
    conn.close()
    for r in rows:
        total = round((r["avg_delivery"] + r["avg_quality"] + r["avg_price"]) / 3, 1)
        r["total_score"] = total
        r["grade"] = "A" if total >= 80 else ("B" if total >= 60 else "C")
    result: list = rows
    return result


# ---------- 구매계약관리 ----------

@router.get("/purchase-contracts")
def list_purchase_contracts(user: dict = Depends(current_user)):
    conn = get_conn()
    rows = rows_to_list(run(
        conn,
        "SELECT pc.*, v.name AS vendor_name FROM purchase_contract pc "
        "JOIN vendor v ON v.vendor_id = pc.vendor_id ORDER BY pc.contract_id DESC",
    ))
    conn.close()
    return rows


@router.post("/purchase-contracts")
def create_purchase_contract(body: dict = Body(...), user: dict = Depends(require_roles("구매담당", "관리자"))):
    require(body, "vendor_id", "start_date")
    conn = get_conn()
    contract_id = insert_returning(
        conn,
        "INSERT INTO purchase_contract (vendor_id, start_date, end_date, terms) VALUES (?,?,?,?)",
        (body["vendor_id"], body["start_date"], body.get("end_date"), body.get("terms")),
        "contract_id",
    )
    conn.commit()
    conn.close()
    return {"contract_id": contract_id}


# ---------- 원재료/부자재/설비/금형 구매 (카테고리 필터 뷰) ----------

@router.get("/purchase/by-category")
def purchase_by_category(category: str | None = None, user: dict = Depends(current_user)):
    """material.material_type 기준 구매(po_line) 집계. category 생략 시 전체 카테고리별 요약.
    현재 시드 데이터는 material_type이 RM/FG만 존재 — 부자재(SUB)/설비(EQUIP)/금형(MOLD)은
    해당 material_type 값이 등록되면 코드 변경 없이 자동 반영된다(알려진 범위 제한)."""
    conn = get_conn()
    if category:
        rows = rows_to_list(run(
            conn,
            "SELECT m.material_type AS category, m.material_id, m.code, m.name, "
            "SUM(pl.qty) AS total_qty, SUM(pl.qty * pl.price) AS total_amount "
            "FROM po_line pl JOIN material m ON m.material_id = pl.material_id "
            "WHERE m.material_type = ? "
            "GROUP BY m.material_id, m.code, m.name, m.material_type ORDER BY total_amount DESC",
            (category,),
        ))
    else:
        rows = rows_to_list(run(
            conn,
            "SELECT m.material_type AS category, SUM(pl.qty) AS total_qty, "
            "SUM(pl.qty * pl.price) AS total_amount, COUNT(DISTINCT pl.po_id) AS po_count "
            "FROM po_line pl JOIN material m ON m.material_id = pl.material_id "
            "GROUP BY m.material_type ORDER BY total_amount DESC",
        ))
    conn.close()
    return rows


# ---------- 통관관리/수입관리 ----------

CUSTOMS_STATUSES = {"PENDING", "DECLARED", "CLEARED", "HOLD"}


@router.get("/import-customs")
def list_import_customs(user: dict = Depends(current_user)):
    conn = get_conn()
    rows = rows_to_list(run(
        conn,
        "SELECT ic.*, po.external_no AS po_external_no, v.name AS vendor_name "
        "FROM import_customs_record ic "
        "JOIN purchase_order po ON po.po_id = ic.po_id "
        "JOIN vendor v ON v.vendor_id = po.vendor_id "
        "ORDER BY ic.customs_id DESC",
    ))
    conn.close()
    return rows


@router.post("/import-customs")
def create_import_customs(body: dict = Body(...), user: dict = Depends(require_roles("구매담당", "관리자"))):
    conn = get_conn()
    # PO 원본번호(PO-2026-XXXXX) 입력도 허용 — po_id가 없으면 po_no(external_no)로 조회
    if not body.get("po_id") and body.get("po_no"):
        found = one(run(conn, "SELECT po_id FROM purchase_order WHERE external_no=?", (str(body["po_no"]).strip(),)))
        if found is None:
            conn.close()
            raise HTTPException(404, "발주를 찾을 수 없음")
        body["po_id"] = found["po_id"]
    if not body.get("po_id"):
        conn.close()
        raise HTTPException(400, "필수 항목 누락: po_id 또는 po_no")
    po = one(run(conn, "SELECT po_id FROM purchase_order WHERE po_id=?", (body["po_id"],)))
    if po is None:
        conn.close()
        raise HTTPException(404, "발주를 찾을 수 없음")
    customs_id = insert_returning(
        conn,
        # customs_date도 eval_date와 동일하게 로컬 날짜를 명시 (UTC 기본값 회피)
        "INSERT INTO import_customs_record (po_id, customs_date, declaration_no, notes) VALUES (?,?,?,?)",
        (body["po_id"], date.today().isoformat(), body.get("declaration_no"), body.get("notes")),
        "customs_id",
    )
    conn.commit()
    conn.close()
    return {"customs_id": customs_id}


@router.post("/import-customs/{customs_id}/status")
def update_customs_status(
    customs_id: int, body: dict = Body(...), user: dict = Depends(require_roles("구매담당", "관리자")),
):
    require(body, "customs_status")
    if body["customs_status"] not in CUSTOMS_STATUSES:
        raise HTTPException(400, f"customs_status는 {', '.join(sorted(CUSTOMS_STATUSES))} 중 하나여야 함")
    conn = get_conn()
    rec = one(run(conn, "SELECT customs_id FROM import_customs_record WHERE customs_id=?", (customs_id,)))
    if rec is None:
        conn.close()
        raise HTTPException(404, "통관 기록을 찾을 수 없음")
    run(conn, "UPDATE import_customs_record SET customs_status=? WHERE customs_id=?", (body["customs_status"], customs_id))
    conn.commit()
    conn.close()
    return {"customs_id": customs_id, "customs_status": body["customs_status"]}


# ---------- 구매실적관리 / 구매 Dashboard ----------

@router.get("/purchase/performance")
def purchase_performance(group_by: str = "vendor", user: dict = Depends(current_user)):
    """vendor/material/month 기준 구매 실적(발주수량/금액) 집계. v9 sales/performance와 동일 패턴."""
    conn = get_conn()
    if group_by == "material":
        rows = rows_to_list(run(
            conn,
            "SELECT m.name AS group_label, SUM(pl.qty) AS total_qty, SUM(pl.qty * pl.price) AS total_amount "
            "FROM po_line pl JOIN material m ON m.material_id = pl.material_id "
            "GROUP BY m.material_id, m.name ORDER BY total_amount DESC",
        ))
    elif group_by == "month":
        rows = rows_to_list(run(
            conn,
            "SELECT substr(po.order_date, 1, 7) AS group_label, COUNT(DISTINCT po.po_id) AS order_count, "
            "SUM(pl.qty * pl.price) AS total_amount FROM purchase_order po "
            "JOIN po_line pl ON pl.po_id = po.po_id "
            "GROUP BY substr(po.order_date, 1, 7) ORDER BY group_label DESC",
        ))
    else:
        rows = rows_to_list(run(
            conn,
            "SELECT v.name AS group_label, COUNT(DISTINCT po.po_id) AS order_count, "
            "SUM(pl.qty * pl.price) AS total_amount FROM purchase_order po "
            "JOIN vendor v ON v.vendor_id = po.vendor_id "
            "JOIN po_line pl ON pl.po_id = po.po_id "
            "GROUP BY v.vendor_id, v.name ORDER BY total_amount DESC",
        ))
    conn.close()
    return rows


@router.get("/purchase/kpi")
def purchase_kpi(user: dict = Depends(current_user)):
    conn = get_conn()
    this_month = date.today().isoformat()[:7]
    open_pr = one(run(conn, "SELECT COUNT(*) c FROM purchase_requisition WHERE status='OPEN'"))["c"]
    open_po = one(run(conn, "SELECT COUNT(*) c FROM purchase_order WHERE status='OPEN'"))["c"]
    spend_this_month = one(run(
        conn,
        "SELECT COALESCE(SUM(pl.qty * pl.price),0) s FROM purchase_order po "
        "JOIN po_line pl ON pl.po_id = po.po_id WHERE substr(po.order_date,1,7)=?",
        (this_month,),
    ))["s"]
    vendor_count = one(run(conn, "SELECT COUNT(*) c FROM vendor"))["c"]
    avg_vendor_score = one(run(
        conn,
        "SELECT AVG((delivery_score + quality_score + price_score) / 3.0) s FROM vendor_evaluation",
    ))["s"]
    conn.close()
    return {
        "open_pr_count": open_pr,
        "open_po_count": open_po,
        "spend_this_month": spend_this_month,
        "vendor_count": vendor_count,
        "avg_vendor_score": round(avg_vendor_score, 1) if avg_vendor_score is not None else None,
    }
