"""AI Agent 시나리오 (v2/v3) — 규칙 기반(rule-based) 구현, LLM 미호출(토큰 비용 없음).
설계문서(2.8 §12.2) 거버넌스 원칙: AI Agent는 추천만 제공하고 자동 실행하지 않는다.
실제 PR 생성/계획값 변경 등은 사람이 /apply 엔드포인트(버튼)를 눌러야 실행된다(Human-in-the-loop).

구현 범위: AI Buyer(재발주 추천), AI Production Scheduler(생산우선순위 추천),
AI Demand Planner(수요예측 기반 재발주점/목표재고 조정 추천), AI Quality Engineer(품질 리스크 추천, 조회전용),
CFO Copilot(재무/현금흐름 인사이트, 조회전용) — task-plan-ai-agent-v3.md 참고.

v3 LLM 고도화(1단계, task-plan-llm-narrative.md 참고): 추천 대상/수치 산출 로직은 그대로 규칙기반을
유지하고, 각 추천 항목에 사람이 읽기 편한 자연어 문단(`ai_narrative`)을 추가했다. 현재는 템플릿 기반
생성(app/llm_rationale.py)만 제공하며 외부 LLM API는 호출하지 않는다(신규 의존성/토큰 비용 없음).
"""
from fastapi import APIRouter, Body, Depends, HTTPException

from .database import get_conn, run, one, rows_to_list, insert_returning
from .helpers import require
from .auth import require_roles, current_user
from .llm_rationale import (
    narrate_buyer, narrate_scheduler, narrate_demand_planner, narrate_quality, narrate_cfo,
)

router = APIRouter(prefix="/api/ai", tags=["ai-agent"])


# ---------- AI Buyer: 재고부족 원자재 재발주 추천 ----------
@router.get("/buyer/recommendations")
def buyer_recommendations(user: dict = Depends(current_user)):
    conn = get_conn()
    materials = rows_to_list(run(
        conn, "SELECT * FROM material WHERE material_type='RM' AND reorder_point > 0"
    ))
    vendors = rows_to_list(run(conn, "SELECT * FROM vendor ORDER BY lead_time_days ASC"))
    best_vendor = vendors[0] if vendors else None

    recs = []
    for m in materials:
        current_qty = one(run(
            conn, "SELECT COALESCE(SUM(qty),0) s FROM inventory WHERE material_id=?", (m["material_id"],)
        ))["s"]
        if current_qty < m["reorder_point"]:
            suggested_qty = max(m["target_stock"] - current_qty, m["reorder_point"])
            rec = {
                "material_id": m["material_id"],
                "code": m["code"],
                "name": m["name"],
                "current_qty": current_qty,
                "reorder_point": m["reorder_point"],
                "target_stock": m["target_stock"],
                "suggested_qty": suggested_qty,
                "recommended_vendor_id": best_vendor["vendor_id"] if best_vendor else None,
                "recommended_vendor_name": best_vendor["name"] if best_vendor else None,
                "rationale": (
                    f"현재고 {current_qty} < 재발주점 {m['reorder_point']} → 목표재고 "
                    f"{m['target_stock']}까지 {suggested_qty} 발주 추천"
                    + (f" (리드타임 최短 공급사: {best_vendor['name']})" if best_vendor else "")
                ),
            }
            rec["ai_narrative"] = narrate_buyer(rec)
            recs.append(rec)
    conn.close()
    return recs


@router.post("/buyer/apply")
def buyer_apply(body: dict = Body(...), user: dict = Depends(require_roles("관리자"))):
    """추천을 사람이 검토 후 실제 PR로 전환(Human-in-the-loop). body: {material_id, qty, vendor_id(선택,미사용)}"""
    require(body, "material_id", "qty")
    conn = get_conn()
    pr_id = insert_returning(
        conn, "INSERT INTO purchase_requisition (requester_id) VALUES (NULL)", (), "pr_id"
    )
    run(conn, "INSERT INTO pr_line (pr_id, material_id, qty) VALUES (?,?,?)",
        (pr_id, body["material_id"], body["qty"]))
    run(conn, "INSERT INTO approval_workflow (doc_type, doc_id) VALUES ('PR', ?)", (pr_id,))
    conn.commit()
    conn.close()
    return {"pr_id": pr_id, "status": "PR_CREATED_PENDING_APPROVAL"}


# ---------- AI Production Scheduler: 생산오더 우선순위 추천 ----------
@router.get("/scheduler/recommendations")
def scheduler_recommendations(user: dict = Depends(current_user)):
    conn = get_conn()
    orders = rows_to_list(run(
        conn,
        "SELECT p.*, m.name AS material_name FROM production_order p "
        "JOIN material m ON m.material_id = p.material_id "
        "WHERE p.status IN ('PLANNED','IN_PROGRESS') ORDER BY p.order_date ASC, p.prod_order_id ASC"
    ))

    evaluated = []
    for o in orders:
        bom_lines = rows_to_list(run(conn, "SELECT * FROM bom WHERE parent_material_id=?", (o["material_id"],)))
        shortages = []
        for b in bom_lines:
            required = o["qty"] * b["qty"]
            available = one(run(
                conn, "SELECT COALESCE(SUM(qty),0) s FROM inventory WHERE material_id=?", (b["child_material_id"],)
            ))["s"]
            if available < required:
                comp = one(run(conn, "SELECT code, name FROM material WHERE material_id=?", (b["child_material_id"],)))
                shortages.append(f"{comp['name']}({comp['code']}) 부족: 필요 {required} / 가용 {available}")
        evaluated.append({
            "prod_order_id": o["prod_order_id"],
            "material_name": o["material_name"],
            "qty": o["qty"],
            "status": o["status"],
            "order_date": o["order_date"],
            "feasible": len(shortages) == 0,
            "shortages": shortages,
        })
    conn.close()

    # 우선순위: 즉시 착수 가능(feasible) 오더를 먼저, 그 안에서는 주문일 순(FIFO) — 이미 order_date ASC 정렬됨
    evaluated.sort(key=lambda x: (not x["feasible"],))
    for i, e in enumerate(evaluated, start=1):
        e["priority_rank"] = i
        e["rationale"] = (
            "자재 충족 → 즉시 착수 가능" if e["feasible"] else "자재 부족 → " + "; ".join(e["shortages"])
        )
        e["ai_narrative"] = narrate_scheduler(e)
    return evaluated


# ---------- AI Demand Planner: 수요예측 오차 기반 재발주점/목표재고 조정 추천 ----------
MAPE_THRESHOLD = 10.0  # 이 값(%) 이상이면 예측 정확도 저하로 간주(제조업 S&OP 통상 기준)


@router.get("/demand-planner/recommendations")
def demand_planner_recommendations(user: dict = Depends(current_user)):
    conn = get_conn()
    materials = rows_to_list(run(conn, "SELECT * FROM material"))
    recs = []
    for m in materials:
        fc = rows_to_list(run(
            conn,
            "SELECT * FROM demand_forecast WHERE material_id=? ORDER BY forecast_month DESC LIMIT 3",
            (m["material_id"],),
        ))
        mapes = [f["mape"] for f in fc if f["mape"] is not None]
        if not mapes:
            continue
        avg_mape = sum(mapes) / len(mapes)
        if avg_mape < MAPE_THRESHOLD:
            continue
        gaps = [(f["actual_sales_qty"] or 0) - (f["forecast_qty"] or 0) for f in fc]
        avg_gap = sum(gaps) / len(gaps)
        buffer_qty = round(abs(avg_gap))
        under_forecast = avg_gap > 0
        direction = "과소예측(품절 위험)" if under_forecast else "과대예측(과잉재고 위험)"
        suggested_reorder = round(m["reorder_point"] + buffer_qty) if under_forecast else m["reorder_point"]
        suggested_target = (
            round(m["target_stock"] + buffer_qty) if under_forecast
            else max(round(m["target_stock"] - buffer_qty), m["reorder_point"])
        )
        rec = {
            "material_id": m["material_id"],
            "code": m["code"],
            "name": m["name"],
            "avg_mape": round(avg_mape, 1),
            "avg_gap_qty": round(avg_gap, 1),
            "direction": direction,
            "current_reorder_point": m["reorder_point"],
            "current_target_stock": m["target_stock"],
            "suggested_reorder_point": suggested_reorder,
            "suggested_target_stock": suggested_target,
            "rationale": (
                f"최근 {len(fc)}개월 평균 예측오차(MAPE) {round(avg_mape,1)}% — {direction}. "
                f"재발주점 {m['reorder_point']}→{suggested_reorder}, 목표재고 {m['target_stock']}→{suggested_target} 조정 추천"
            ),
        }
        rec["ai_narrative"] = narrate_demand_planner(rec)
        recs.append(rec)
    conn.close()
    recs.sort(key=lambda r: -r["avg_mape"])
    return recs


@router.post("/demand-planner/apply")
def demand_planner_apply(body: dict = Body(...), user: dict = Depends(require_roles("관리자"))):
    """추천을 사람이 검토 후 material의 재발주점/목표재고에 실제 반영(Human-in-the-loop).
    금액이 이동하는 거래가 아닌 계획 파라미터 조정이라 승인 워크플로 없이 즉시 반영한다."""
    require(body, "material_id", "reorder_point", "target_stock")
    conn = get_conn()
    run(conn, "UPDATE material SET reorder_point=?, target_stock=? WHERE material_id=?",
        (body["reorder_point"], body["target_stock"], body["material_id"]))
    conn.commit()
    conn.close()
    return {"material_id": body["material_id"], "status": "MATERIAL_PLANNING_UPDATED"}


# ---------- AI Quality Engineer: 품질 리스크 추천 (조회전용 — CAPA 실행 워크플로 없음) ----------
@router.get("/quality/recommendations")
def quality_recommendations(user: dict = Depends(current_user)):
    conn = get_conn()
    materials = rows_to_list(run(conn, "SELECT * FROM material"))
    recs = []
    for m in materials:
        recent = rows_to_list(run(
            conn,
            "SELECT * FROM quality_inspection WHERE material_id=? ORDER BY inspection_date DESC LIMIT 6",
            (m["material_id"],),
        ))
        if not recent:
            continue
        avg_ppm = sum(r["defect_ppm"] or 0 for r in recent) / len(recent)
        fail_count = sum(1 for r in recent if r["result"] == "FAIL")
        capa_count = sum(1 for r in recent if r["capa_required"] == "Y")
        if fail_count == 0 and capa_count < len(recent) / 2:
            continue
        risk_level = "높음" if fail_count > 0 else "중간"
        rec = {
            "material_id": m["material_id"],
            "code": m["code"],
            "name": m["name"],
            "avg_defect_ppm": round(avg_ppm, 1),
            "recent_fail_count": fail_count,
            "recent_capa_count": capa_count,
            "sample_size": len(recent),
            "risk_level": risk_level,
            "rationale": (
                f"최근 {len(recent)}건 검사 중 불량(FAIL) {fail_count}건, CAPA 필요 {capa_count}건, "
                f"평균 불량률 {round(avg_ppm,1)}PPM → "
                + ("공급사/공정 정밀조사 및 CAPA 우선 처리 필요" if fail_count > 0 else "예방적 공정 점검 권장")
            ),
        }
        rec["ai_narrative"] = narrate_quality(rec)
        recs.append(rec)
    conn.close()
    recs.sort(key=lambda r: (-r["recent_fail_count"], -r["recent_capa_count"]))
    return recs


# ---------- CFO Copilot: 재무/현금흐름 인사이트 (조회전용 — 자문 역할) ----------
# v5: 재무 민감정보라 조회도 관리자 전용으로 좁힌다(task-plan-v5.md 참고).
@router.get("/cfo-copilot/insights")
def cfo_copilot_insights(user: dict = Depends(require_roles("관리자"))):
    conn = get_conn()
    insights = []

    fin = rows_to_list(run(conn, "SELECT * FROM finance_summary_monthly ORDER BY period"))
    if len(fin) >= 2:
        latest, prev = fin[-1], fin[-2]

        def margin(row):
            return (row["operating_profit"] / row["revenue"] * 100) if row["revenue"] else 0

        latest_margin, prev_margin = margin(latest), margin(prev)
        margin_delta = latest_margin - prev_margin
        insight = {
            "title": f"{latest['period']} 영업이익률 {'개선' if margin_delta >= 0 else '악화'}",
            "detail": (
                f"{prev['period']} {round(prev_margin,1)}% → {latest['period']} {round(latest_margin,1)}% "
                f"({'+' if margin_delta >= 0 else ''}{round(margin_delta,1)}%p)"
            ),
            "severity": "GOOD" if margin_delta >= 2 else ("WARN" if margin_delta < -2 else "INFO"),
        }
        insight["ai_narrative"] = narrate_cfo(insight)
        insights.append(insight)

        cash_gap = (latest["operating_profit"] or 0) - (latest["cash_flow"] or 0)
        if latest["operating_profit"] and abs(cash_gap) > abs(latest["operating_profit"]) * 0.15:
            insight = {
                "title": f"{latest['period']} 영업이익 대비 현금흐름 괴리",
                "detail": (
                    f"영업이익 {int(latest['operating_profit']):,} vs 현금흐름 {int(latest['cash_flow'] or 0):,} "
                    f"(차이 {int(cash_gap):,}) → 운전자본(매출채권/재고) 점검 필요"
                ),
                "severity": "WARN",
            }
            insight["ai_narrative"] = narrate_cfo(insight)
            insights.append(insight)

    kpi = rows_to_list(run(conn, "SELECT * FROM kpi_monthly ORDER BY period"))
    if kpi:
        latest_kpi = kpi[-1]
        if latest_kpi.get("supply_risk_count"):
            insight = {
                "title": f"{latest_kpi['period']} 공급 리스크 {int(latest_kpi['supply_risk_count'])}건 감지",
                "detail": f"OTD {latest_kpi['otd_rate']}%, 평균 PPM {latest_kpi['ppm_avg']} — 공급망 리스크 모니터링 권장",
                "severity": "WARN",
            }
            insight["ai_narrative"] = narrate_cfo(insight)
            insights.append(insight)

    ar = one(run(conn, "SELECT COALESCE(SUM(amount),0) s FROM sales_invoice WHERE status='OPEN'"))["s"]
    ap = one(run(conn, "SELECT COALESCE(SUM(amount),0) s FROM ap_invoice WHERE status='OPEN'"))["s"]
    insight = {
        "title": "현재 매출채권/매입채무 현황 (라이브)",
        "detail": f"매출채권(AR) {int(ar):,}원, 매입채무(AP) {int(ap):,}원 — 실시간 트랜잭션 기준",
        "severity": "INFO",
    }
    insight["ai_narrative"] = narrate_cfo(insight)
    insights.append(insight)

    conn.close()
    return insights
