"""02. Supply Chain Management 신규 (v10).

1.0_AX_ERP_Menu_Structure.md "02. Supply Chain Management" 중 그동안 없던 항목을 추가한다
(task-plan-v9-full-menu-rollout.md §3 v10 참고). 신규 테이블/스키마 변경 없이 기존 테이블
(demand_forecast/production_order/inventory/purchase_order/goods_receipt/vendor/material)을
집계·대조하는 조회 전용 API만 제공한다(전부 GET, 상태를 바꾸는 쓰기 작업 없음).

**비범위(사용자 확인 후 이번 로드맵 전체에서 제외)**: 공급망 시뮬레이션(What-if). S&OP/공급계획/
재고계획/공급위험관리/Control Tower만 이번 웨이브에서 구현한다.
"""
from datetime import date, datetime

from fastapi import APIRouter, Depends

from .database import get_conn, run, one, rows_to_list
from .auth import current_user

router = APIRouter(prefix="/api/scm", tags=["scm"])


def _parse_date(s: str) -> date:
    return datetime.fromisoformat(s[:10]).date()


# ---------- 수요예측 고도화 ----------

@router.get("/demand-forecast/accuracy")
def demand_forecast_accuracy(user: dict = Depends(current_user)):
    """품목별 평균 MAPE + 최근 예측 대비 실판매 방향성. 기존 /api/reference/demand-forecast(조회
    전용 원본 목록)를 품목 단위로 집계해 "정확도" 관점으로 승격한다."""
    conn = get_conn()
    rows = rows_to_list(run(
        conn,
        "SELECT m.material_id, m.code, m.name, AVG(f.mape) AS avg_mape, "
        "SUM(f.forecast_qty) AS total_forecast_qty, SUM(f.actual_sales_qty) AS total_actual_qty, "
        "COUNT(*) AS forecast_count "
        "FROM demand_forecast f JOIN material m ON m.material_id = f.material_id "
        "GROUP BY m.material_id, m.code, m.name ORDER BY avg_mape DESC",
    ))
    conn.close()
    for r in rows:
        forecast_total = r["total_forecast_qty"] or 0
        actual_total = r["total_actual_qty"] or 0
        r["direction"] = "UNDER_FORECAST" if actual_total > forecast_total else "OVER_FORECAST"
    return rows


# ---------- S&OP ----------

@router.get("/sop")
def sop_gap(user: dict = Depends(current_user)):
    """판매계획(수요예측 forecast_qty) vs 생산계획(production_order qty)을 품목+월 기준으로 대조.
    gap = 생산계획 - 수요예측(양수면 과잉계획, 음수면 계획 부족)."""
    conn = get_conn()
    demand = rows_to_list(run(
        conn,
        "SELECT material_id, substr(forecast_month, 1, 7) AS period, SUM(forecast_qty) AS demand_qty "
        "FROM demand_forecast GROUP BY material_id, substr(forecast_month, 1, 7)",
    ))
    supply = rows_to_list(run(
        conn,
        "SELECT material_id, substr(order_date, 1, 7) AS period, SUM(qty) AS planned_qty "
        "FROM production_order GROUP BY material_id, substr(order_date, 1, 7)",
    ))
    materials = {m["material_id"]: m for m in rows_to_list(run(conn, "SELECT material_id, code, name FROM material"))}
    conn.close()
    supply_map = {(s["material_id"], s["period"]): s["planned_qty"] for s in supply}
    result = []
    for d in demand:
        key = (d["material_id"], d["period"])
        planned = supply_map.get(key, 0)
        mat = materials.get(d["material_id"], {})
        result.append({
            "material_id": d["material_id"],
            "material_code": mat.get("code"),
            "material_name": mat.get("name"),
            "period": d["period"],
            "demand_qty": d["demand_qty"] or 0,
            "planned_qty": planned,
            "gap": round(planned - (d["demand_qty"] or 0), 2),
        })
    result.sort(key=lambda r: r["period"], reverse=True)
    return result


# ---------- 공급계획 ----------

@router.get("/supply-plan")
def supply_plan(user: dict = Depends(current_user)):
    """품목별 공급가능수량(현재고 + 미입고 OPEN PO 수량) vs 재주문점/목표재고."""
    conn = get_conn()
    inv = rows_to_list(run(conn, "SELECT material_id, SUM(qty) AS qty FROM inventory GROUP BY material_id"))
    inv_map = {r["material_id"]: r["qty"] for r in inv}
    open_po = rows_to_list(run(
        conn,
        "SELECT pl.material_id, SUM(pl.qty) AS qty FROM po_line pl "
        "JOIN purchase_order po ON po.po_id = pl.po_id WHERE po.status='OPEN' GROUP BY pl.material_id",
    ))
    open_po_map = {r["material_id"]: r["qty"] for r in open_po}
    materials = rows_to_list(run(conn, "SELECT material_id, code, name, reorder_point, target_stock FROM material"))
    conn.close()
    result = []
    for m in materials:
        on_hand = inv_map.get(m["material_id"], 0) or 0
        incoming = open_po_map.get(m["material_id"], 0) or 0
        available = on_hand + incoming
        result.append({
            "material_id": m["material_id"], "code": m["code"], "name": m["name"],
            "on_hand_qty": on_hand, "incoming_po_qty": incoming, "available_qty": available,
            "reorder_point": m["reorder_point"], "target_stock": m["target_stock"],
            "below_reorder_point": available < m["reorder_point"],
        })
    result.sort(key=lambda r: r["available_qty"] - r["reorder_point"])
    return result


# ---------- 생산계획(MPS) 뷰 ----------

@router.get("/mps")
def mps_view(user: dict = Depends(current_user)):
    """기존 생산오더 목록을 월별 MPS(Master Production Schedule) 뷰로 재구성한다(신규 테이블 불필요)."""
    conn = get_conn()
    rows = rows_to_list(run(
        conn,
        "SELECT m.material_id, m.code, m.name, substr(po.order_date, 1, 7) AS period, "
        "SUM(po.qty) AS planned_qty, COUNT(*) AS order_count "
        "FROM production_order po JOIN material m ON m.material_id = po.material_id "
        "GROUP BY m.material_id, m.code, m.name, substr(po.order_date, 1, 7) "
        "ORDER BY period DESC, m.code",
    ))
    conn.close()
    return rows


# ---------- 재고계획 ----------

@router.get("/inventory-plan")
def inventory_plan(user: dict = Depends(current_user)):
    """안전재고(reorder_point)/목표재고(target_stock) 대비 현재고 갭 리포트(LOT 정합성 KPI와 유사한
    패턴 — 신규 테이블 없이 기존 material/inventory 집계만 사용)."""
    conn = get_conn()
    inv = rows_to_list(run(conn, "SELECT material_id, SUM(qty) AS qty FROM inventory GROUP BY material_id"))
    inv_map = {r["material_id"]: r["qty"] for r in inv}
    materials = rows_to_list(run(conn, "SELECT material_id, code, name, reorder_point, target_stock FROM material"))
    conn.close()
    result = []
    for m in materials:
        current = inv_map.get(m["material_id"], 0) or 0
        result.append({
            "material_id": m["material_id"], "code": m["code"], "name": m["name"],
            "current_qty": current, "reorder_point": m["reorder_point"], "target_stock": m["target_stock"],
            "gap_to_target": round(m["target_stock"] - current, 2),
            "risk": "LOW_STOCK" if current < m["reorder_point"] else "OK",
        })
    return result


# ---------- 공급위험관리 ----------

@router.get("/supply-risk")
def supply_risk(user: dict = Depends(current_user)):
    """공급사별 납기지연 이력 집계 → 리스크 스코어(규칙기반, 정교한 ML 없음).
    vendor.lead_time_days(기준 리드타임) 대비 실제 입고(goods_receipt.received_date -
    purchase_order.order_date)가 초과된 건수 비율로 계산한다."""
    conn = get_conn()
    rows = rows_to_list(run(
        conn,
        "SELECT v.vendor_id, v.name AS vendor_name, v.lead_time_days, "
        "po.order_date, gr.received_date "
        "FROM goods_receipt gr "
        "JOIN po_line pl ON pl.po_line_id = gr.po_line_id "
        "JOIN purchase_order po ON po.po_id = pl.po_id "
        "JOIN vendor v ON v.vendor_id = po.vendor_id",
    ))
    conn.close()
    stats: dict[int, dict] = {}
    for r in rows:
        vid = r["vendor_id"]
        s = stats.setdefault(vid, {"vendor_id": vid, "vendor_name": r["vendor_name"], "total": 0, "delayed": 0})
        s["total"] += 1
        try:
            actual_days = (_parse_date(r["received_date"]) - _parse_date(r["order_date"])).days
            if actual_days > r["lead_time_days"]:
                s["delayed"] += 1
        except (ValueError, TypeError):
            continue
    result = []
    for s in stats.values():
        rate = round(s["delayed"] / s["total"], 3) if s["total"] else 0
        s["delay_rate"] = rate
        s["risk_level"] = "HIGH" if rate >= 0.3 else ("MEDIUM" if rate >= 0.1 else "LOW")
        result.append(s)
    result.sort(key=lambda r: r["delay_rate"], reverse=True)
    return result


# ---------- 공급망 가시성 (Control Tower) / SCM Dashboard ----------

@router.get("/control-tower")
def control_tower(user: dict = Depends(current_user)):
    """S&OP/공급계획/재고계획/공급위험관리를 한 화면에 모으는 요약(신규 집계 없이 위 엔드포인트들의
    핵심 지표만 재사용 — SCM Dashboard와 동일 데이터)."""
    supply = supply_plan(user)  # type: ignore[arg-type]
    inv_plan = inventory_plan(user)  # type: ignore[arg-type]
    risk = supply_risk(user)  # type: ignore[arg-type]
    return {
        "below_reorder_point_count": sum(1 for r in supply if r["below_reorder_point"]),
        "low_stock_count": sum(1 for r in inv_plan if r["risk"] == "LOW_STOCK"),
        "high_risk_vendor_count": sum(1 for r in risk if r["risk_level"] == "HIGH"),
        "vendor_count": len(risk),
    }
