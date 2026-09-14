"""05. Production Management 확장 (v13) — MRP/외주생산/재작업/생산마감/OEE분석/생산Dashboard.

task-plan-v9-full-menu-rollout.md §3 v13. 신규 테이블은 rework_order/production_close 2개만
(migrations/0007, 외주는 production_order 컬럼 2개). 나머지는 기존 테이블 집계 조회.

- MRP: 최신 수요예측월의 FG 수요 × BOM 전개 → 자재별 소요량 vs 현재고+미입고PO → 부족분 산출.
  조회 전용 — 발주 실행은 기존 PR/PO 플로우 또는 AI Buyer 추천(재발주점 기반, 별개 로직) 사용.
- 외주생산: is_outsourced/vendor_id 컬럼(main.py create_prod_order에서 입력) 기준 현황 조회.
- 재작업: DEFECTIVE 시리얼만 등록 가능. 완료 시 REWORKED→시리얼 IN_STOCK 복귀 / SCRAPPED→SCRAPPED.
  시리얼 상태 변경은 v8 audit_log 패턴 그대로 기록.
- 생산마감: 월 단위. 해당월 실적 집계(양품수량×std_cost) → FI 전표(차변 1200 재고자산 / 대변
  5000 매출원가 — 프로토타입 근사, WIP 계정 없음) → 마감 후 해당월 실적입력 잠금(main.py에서
  assert_period_not_closed 호출).
- OEE분석: production_result의 실측 oee/availability/performance/quality_rate를 월×공장 집계
  (dataset 참고데이터의 실측 승격 — task-plan 명시). kpi_monthly.oee_avg는 참고 시계열로 병행 반환.

날짜는 전부 서버 로컬 date.today() 명시(UTC 기본값 미사용 — v11 검증에서 확립된 패턴).
"""
from datetime import date

from fastapi import APIRouter, Body, Depends, HTTPException

from .database import get_conn, run, one, rows_to_list, insert_returning
from .helpers import post_accounting, write_audit_log
from .auth import require_roles, current_user

router = APIRouter(prefix="/api/production", tags=["production-ext"])

REWORK_RESULTS = {"REWORKED", "SCRAPPED"}


def assert_period_not_closed(conn, result_date: str):
    """생산실적 입력 전 해당 월이 마감되지 않았는지 확인 (main.py create_result에서 호출)."""
    period = (result_date or date.today().isoformat())[:7]
    closed = one(run(conn, "SELECT close_id FROM production_close WHERE period=?", (period,)))
    if closed is not None:
        conn.close()
        raise HTTPException(400, f"{period}은(는) 생산마감된 월 — 실적을 입력할 수 없음")


# ---------- MRP (자재소요계획) ----------

@router.get("/mrp")
def mrp(user: dict = Depends(current_user)):
    """최신 수요예측월 기준 BOM 전개 부족자재 산출. 조회 전용."""
    conn = get_conn()
    latest = one(run(conn, "SELECT MAX(substr(forecast_month,1,7)) p FROM demand_forecast"))
    period = latest["p"] if latest else None
    if not period:
        conn.close()
        return {"period": None, "rows": []}
    rows = rows_to_list(run(
        conn,
        "SELECT b.child_material_id AS material_id, m.code, m.name, "
        "SUM(f.forecast_qty * b.qty) AS requirement "
        "FROM demand_forecast f "
        "JOIN bom b ON b.parent_material_id = f.material_id "
        "JOIN material m ON m.material_id = b.child_material_id "
        "WHERE substr(f.forecast_month,1,7) = ? "
        "GROUP BY b.child_material_id, m.code, m.name",
        (period,),
    ))
    for r in rows:
        onhand = one(run(
            conn, "SELECT COALESCE(SUM(qty),0) s FROM inventory WHERE material_id=?", (r["material_id"],),
        ))["s"]
        incoming = one(run(
            conn,
            "SELECT COALESCE(SUM(pl.qty),0) s FROM po_line pl "
            "JOIN purchase_order po ON po.po_id = pl.po_id "
            "WHERE pl.material_id=? AND po.status='OPEN'",
            (r["material_id"],),
        ))["s"]
        r["onhand"] = onhand
        r["incoming"] = incoming
        r["shortage"] = max(0.0, round(r["requirement"] - onhand - incoming, 2))
    conn.close()
    rows.sort(key=lambda r: r["shortage"], reverse=True)
    return {"period": period, "rows": rows}


# ---------- 외주생산 현황 ----------

@router.get("/outsourcing")
def outsourcing_status(user: dict = Depends(current_user)):
    conn = get_conn()
    rows = rows_to_list(run(
        conn,
        "SELECT p.prod_order_id, p.external_no, m.name AS material_name, p.qty, p.status, "
        "p.order_date, v.name AS vendor_name "
        "FROM production_order p "
        "JOIN material m ON m.material_id = p.material_id "
        "LEFT JOIN vendor v ON v.vendor_id = p.vendor_id "
        "WHERE p.is_outsourced = 1 ORDER BY p.prod_order_id DESC",
    ))
    conn.close()
    return rows


# ---------- 재작업관리 ----------

@router.get("/reworks")
def list_reworks(user: dict = Depends(current_user)):
    conn = get_conn()
    rows = rows_to_list(run(
        conn,
        "SELECT r.*, s.serial_no, s.status AS serial_status, m.name AS material_name "
        "FROM rework_order r "
        "JOIN serial_number s ON s.serial_id = r.serial_id "
        "JOIN material m ON m.material_id = s.material_id "
        "ORDER BY r.rework_id DESC",
    ))
    conn.close()
    return rows


@router.post("/reworks")
def create_rework(body: dict = Body(...), user: dict = Depends(require_roles("생산담당", "관리자"))):
    serial_no = body.get("serial_no")
    if not serial_no:
        raise HTTPException(400, "필수 항목 누락: serial_no")
    conn = get_conn()
    serial = one(run(conn, "SELECT * FROM serial_number WHERE serial_no=?", (serial_no,)))
    if serial is None:
        conn.close()
        raise HTTPException(404, "시리얼을 찾을 수 없음")
    if serial["status"] != "DEFECTIVE":
        conn.close()
        raise HTTPException(400, f"DEFECTIVE 상태의 시리얼만 재작업 등록 가능 (현재: {serial['status']})")
    dup = one(run(
        conn, "SELECT rework_id FROM rework_order WHERE serial_id=? AND status='OPEN'", (serial["serial_id"],),
    ))
    if dup is not None:
        conn.close()
        raise HTTPException(400, "이미 진행 중인 재작업이 있음")
    rework_id = insert_returning(
        conn,
        "INSERT INTO rework_order (serial_id, reason, created_date) VALUES (?,?,?)",
        (serial["serial_id"], body.get("reason"), date.today().isoformat()),
        "rework_id",
    )
    conn.commit()
    conn.close()
    return {"rework_id": rework_id}


@router.post("/reworks/{rework_id}/complete")
def complete_rework(
    rework_id: int, body: dict = Body(...), user: dict = Depends(require_roles("생산담당", "관리자")),
):
    result = body.get("result")
    if result not in REWORK_RESULTS:
        raise HTTPException(400, f"result는 {', '.join(sorted(REWORK_RESULTS))} 중 하나여야 함")
    conn = get_conn()
    rework = one(run(conn, "SELECT * FROM rework_order WHERE rework_id=?", (rework_id,)))
    if rework is None:
        conn.close()
        raise HTTPException(404, "재작업을 찾을 수 없음")
    if rework["status"] != "OPEN":
        conn.close()
        raise HTTPException(400, "이미 완료된 재작업")
    serial = one(run(conn, "SELECT * FROM serial_number WHERE serial_id=?", (rework["serial_id"],)))
    new_serial_status = "IN_STOCK" if result == "REWORKED" else "SCRAPPED"
    run(conn, "UPDATE serial_number SET status=? WHERE serial_id=?", (new_serial_status, serial["serial_id"]))
    run(
        conn,
        "UPDATE rework_order SET status=?, completed_date=? WHERE rework_id=?",
        (result, date.today().isoformat(), rework_id),
    )
    # v8 시리얼 상태변경 감사로그 패턴 재사용
    write_audit_log(
        conn, user["user_id"], f"REWORK_{result}:{serial['status']}->{new_serial_status}",
        "serial_number", serial["serial_id"],
    )
    conn.commit()
    conn.close()
    return {"rework_id": rework_id, "status": result, "serial_status": new_serial_status}


# ---------- 생산마감 ----------

@router.get("/closes")
def list_closes(user: dict = Depends(current_user)):
    conn = get_conn()
    rows = rows_to_list(run(conn, "SELECT * FROM production_close ORDER BY period DESC"))
    conn.close()
    return rows


@router.post("/close")
def close_period(body: dict = Body(...), user: dict = Depends(require_roles("관리자"))):
    """월별 생산마감 — 실적 집계 → FI 전표(차변 1200 재고자산 / 대변 5000 매출원가, 근사) → 잠금.

    양품 금액은 qty_good × material.std_cost(v9 손익 근사와 동일 기준). 전표는 금액>0일 때만 생성.
    """
    period = body.get("period")
    if not period or len(period) != 7:
        raise HTTPException(400, "period는 YYYY-MM 형식이어야 함")
    conn = get_conn()
    if one(run(conn, "SELECT close_id FROM production_close WHERE period=?", (period,))) is not None:
        conn.close()
        raise HTTPException(400, f"{period}은(는) 이미 마감된 월")
    agg = one(run(
        conn,
        "SELECT COALESCE(SUM(pr.qty_good),0) good, COALESCE(SUM(pr.qty_defect),0) defect, "
        "COALESCE(SUM(pr.qty_good * COALESCE(m.std_cost,0)),0) amount "
        "FROM production_result pr "
        "JOIN work_order wo ON wo.work_order_id = pr.work_order_id "
        "JOIN production_order po ON po.prod_order_id = wo.prod_order_id "
        "JOIN material m ON m.material_id = po.material_id "
        "WHERE substr(pr.result_date,1,7) = ?",
        (period,),
    ))
    acct_doc_id = None
    if agg["amount"] > 0:
        acct_doc_id = post_accounting(
            conn, "PRODUCTION_CLOSE", f"생산마감 {period} (양품 {agg['good']:.0f}개)",
            [("1200", agg["amount"], 0), ("5000", 0, agg["amount"])],
        )
    close_id = insert_returning(
        conn,
        "INSERT INTO production_close (period, total_good, total_defect, close_amount, acct_doc_id, closed_date, notes) "
        "VALUES (?,?,?,?,?,?,?)",
        (period, agg["good"], agg["defect"], agg["amount"], acct_doc_id,
         date.today().isoformat(), body.get("notes")),
        "close_id",
    )
    conn.commit()
    conn.close()
    return {"close_id": close_id, "period": period, "close_amount": agg["amount"], "acct_doc_id": acct_doc_id}


# ---------- 설비가동현황 / OEE 분석 ----------

@router.get("/oee")
def oee_analysis(user: dict = Depends(current_user)):
    """월×공장별 OEE 실측 집계(production_result) + kpi_monthly.oee_avg 참고 시계열."""
    conn = get_conn()
    measured = rows_to_list(run(
        conn,
        "SELECT substr(pr.result_date,1,7) AS period, pl.name AS plant_name, "
        "ROUND(AVG(pr.oee),1) AS avg_oee, ROUND(AVG(pr.availability),1) AS avg_availability, "
        "ROUND(AVG(pr.performance),1) AS avg_performance, ROUND(AVG(pr.quality_rate),1) AS avg_quality_rate, "
        "COUNT(*) AS result_count "
        "FROM production_result pr "
        "JOIN work_order wo ON wo.work_order_id = pr.work_order_id "
        "JOIN production_order po ON po.prod_order_id = wo.prod_order_id "
        "JOIN plant pl ON pl.plant_id = po.plant_id "
        "WHERE pr.oee IS NOT NULL "
        "GROUP BY substr(pr.result_date,1,7), pl.name "
        "ORDER BY period DESC, plant_name",
    ))
    reference = rows_to_list(run(
        conn, "SELECT period, oee_avg FROM kpi_monthly WHERE oee_avg IS NOT NULL ORDER BY period DESC",
    ))
    conn.close()
    return {"measured": measured, "reference": reference}


# ---------- 생산 Dashboard ----------

@router.get("/dashboard")
def production_dashboard(user: dict = Depends(current_user)):
    conn = get_conn()
    open_orders = one(run(conn, "SELECT COUNT(*) c FROM production_order WHERE status != 'COMPLETED'"))["c"]
    outsourced = one(run(conn, "SELECT COUNT(*) c FROM production_order WHERE is_outsourced=1"))["c"]
    this_month = date.today().isoformat()[:7]
    month_agg = one(run(
        conn,
        "SELECT COALESCE(SUM(qty_good),0) good, COALESCE(SUM(qty_defect),0) defect "
        "FROM production_result WHERE substr(result_date,1,7)=?",
        (this_month,),
    ))
    total = month_agg["good"] + month_agg["defect"]
    open_reworks = one(run(conn, "SELECT COUNT(*) c FROM rework_order WHERE status='OPEN'"))["c"]
    last_close = one(run(conn, "SELECT MAX(period) p FROM production_close"))["p"]
    avg_oee = one(run(conn, "SELECT ROUND(AVG(oee),1) v FROM production_result WHERE oee IS NOT NULL"))["v"]
    conn.close()
    return {
        "open_order_count": open_orders,
        "outsourced_count": outsourced,
        "month_good": month_agg["good"],
        "month_defect": month_agg["defect"],
        "month_defect_rate": round(month_agg["defect"] / total * 100, 2) if total else 0,
        "open_rework_count": open_reworks,
        "last_closed_period": last_close,
        "avg_oee": avg_oee,
    }
