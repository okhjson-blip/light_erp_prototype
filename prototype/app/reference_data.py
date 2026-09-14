"""prototype_dataset에서 임포트한 참조 데이터(조회 전용) API.
demand_forecast / quality_inspection / shipment / finance_summary_monthly / kpi_monthly /
ai_recommendation_log — 비즈니스 로직 없이 목록 조회만 제공한다.
"""
from fastapi import APIRouter, Depends

from .database import get_conn, run, rows_to_list
from .auth import current_user

router = APIRouter(prefix="/api/reference", tags=["reference-data"])


@router.get("/demand-forecast")
def list_demand_forecast(user: dict = Depends(current_user)):
    conn = get_conn()
    rows = rows_to_list(run(
        conn,
        "SELECT f.*, m.code AS material_code, m.name AS material_name FROM demand_forecast f "
        "JOIN material m ON m.material_id = f.material_id ORDER BY f.forecast_month, m.code"
    ))
    conn.close()
    return rows


@router.get("/quality-inspections")
def list_quality_inspections(user: dict = Depends(current_user)):
    conn = get_conn()
    rows = rows_to_list(run(
        conn,
        "SELECT q.*, m.code AS material_code, m.name AS material_name FROM quality_inspection q "
        "JOIN material m ON m.material_id = q.material_id ORDER BY q.inspection_date DESC LIMIT 300"
    ))
    conn.close()
    return rows


@router.get("/shipments")
def list_shipments(user: dict = Depends(current_user)):
    conn = get_conn()
    rows = rows_to_list(run(
        conn,
        "SELECT s.*, c.name AS customer_name, m.code AS material_code FROM shipment s "
        "LEFT JOIN customer c ON c.customer_id = s.customer_id "
        "LEFT JOIN material m ON m.material_id = s.material_id "
        "ORDER BY s.shipment_date DESC LIMIT 300"
    ))
    conn.close()
    return rows


@router.get("/finance-summary")
def list_finance_summary(user: dict = Depends(current_user)):
    conn = get_conn()
    rows = rows_to_list(run(conn, "SELECT * FROM finance_summary_monthly ORDER BY period"))
    conn.close()
    return rows


@router.get("/kpi-monthly")
def list_kpi_monthly(user: dict = Depends(current_user)):
    conn = get_conn()
    rows = rows_to_list(run(conn, "SELECT * FROM kpi_monthly ORDER BY period"))
    conn.close()
    return rows


@router.get("/ai-recommendation-log")
def list_ai_recommendation_log(user: dict = Depends(current_user)):
    """과거 이력 참고용 정적 데이터. 실시간 규칙기반 추천은 /api/ai/buyer|scheduler 참고."""
    conn = get_conn()
    rows = rows_to_list(run(conn, "SELECT * FROM ai_recommendation_log ORDER BY created_at DESC"))
    conn.close()
    return rows
