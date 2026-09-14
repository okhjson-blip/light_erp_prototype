"""06. Quality Management 확장 (v14) — 검사기준/검사구분조회/SPC·공정능력/부적합/8D/고객클레임/CAPA/품질Dashboard.

task-plan-v9-full-menu-rollout.md §3 v14. 신규 테이블 4종(migrations/0008), 나머지는 기존
quality_inspection(inspection_type은 v1부터 존재)/serial_number/rework_order 집계 조회.

- 검사기준: 품목×검사구분별 검사항목 마스터. LSL/USL은 SPC Cp/Cpk의 규격 기준.
- 검사이력 조회: inspection_type(INCOMING/IN_PROCESS/FINAL) 필터 지원 — 등록은 기존
  POST /api/quality/inspections(lot_tracking.py) 그대로 재사용(v3 QMS, 무변경).
- SPC/공정능력: 품목별 defect_ppm 시계열 기준 p-관리도 통계(평균/±3σ UCL·LCL/이탈 건수) +
  검사기준에 LSL/USL이 있으면 Cp/Cpk 계산. **프로토타입 근사**: 측정치 원본이 없어 defect_ppm을
  특성치로 사용(치수 등 실측 SPC는 Enterprise 단계 — 관리도 시각화도 task-plan에서 명시 제외).
- 부적합관리: DEFECTIVE 시리얼 + 진행 중 재작업(v13) 통합 현황(조회 — 처리 플로우는 생산>재작업).
- 8D Report: 간이(문제/근본원인/시정조치), OPEN→IN_PROGRESS→CLOSED.
- 고객클레임: OPEN→INVESTIGATING→RESOLVED/REJECTED.
- CAPA: 등록/상태 변경(OPEN→IN_PROGRESS→DONE). 기존 capa_required='Y' 검사는 CAPA 후보 목록으로 노출.

역할 게이팅은 v3 QMS 절충 그대로: 쓰기 = 생산담당+관리자("품질담당" 역할 없음). 날짜는 date.today() 명시.
"""
from datetime import date
from statistics import mean, stdev

from fastapi import APIRouter, Body, Depends, HTTPException

from .database import get_conn, run, one, rows_to_list, insert_returning
from .auth import require_roles, current_user

router = APIRouter(prefix="/api/quality", tags=["quality-ext"])

INSPECTION_TYPES = {"INCOMING", "IN_PROCESS", "FINAL"}
EIGHT_D_STATUSES = {"OPEN", "IN_PROGRESS", "CLOSED"}
CLAIM_STATUSES = {"OPEN", "INVESTIGATING", "RESOLVED", "REJECTED"}
CLAIM_TYPES = {"QUALITY", "DELIVERY", "OTHER"}
CAPA_STATUSES = {"OPEN", "IN_PROGRESS", "DONE"}
CAPA_TYPES = {"CORRECTIVE", "PREVENTIVE"}
CAPA_SOURCES = {"INSPECTION", "CLAIM", "8D"}

_WRITE = ("생산담당", "관리자")


def _require(body: dict, *fields):
    missing = [f for f in fields if body.get(f) in (None, "")]
    if missing:
        raise HTTPException(400, f"필수 항목 누락: {', '.join(missing)}")


def _check_material(conn, material_id):
    if one(run(conn, "SELECT material_id FROM material WHERE material_id=?", (material_id,))) is None:
        conn.close()
        raise HTTPException(404, "품목을 찾을 수 없음")


# ---------- 검사기준관리 ----------

@router.get("/standards")
def list_standards(user: dict = Depends(current_user)):
    conn = get_conn()
    rows = rows_to_list(run(
        conn,
        "SELECT s.*, m.name AS material_name, m.code AS material_code FROM inspection_standard s "
        "JOIN material m ON m.material_id = s.material_id ORDER BY s.material_id, s.inspection_type",
    ))
    conn.close()
    return rows


@router.post("/standards")
def create_standard(body: dict = Body(...), user: dict = Depends(require_roles(*_WRITE))):
    _require(body, "material_id", "inspection_type", "item_name")
    if body["inspection_type"] not in INSPECTION_TYPES:
        raise HTTPException(400, f"inspection_type은 {', '.join(sorted(INSPECTION_TYPES))} 중 하나여야 함")
    conn = get_conn()
    _check_material(conn, body["material_id"])
    standard_id = insert_returning(
        conn,
        "INSERT INTO inspection_standard (material_id, inspection_type, item_name, method, "
        "spec_target, spec_lsl, spec_usl, unit) VALUES (?,?,?,?,?,?,?,?)",
        (body["material_id"], body["inspection_type"], body["item_name"], body.get("method"),
         body.get("spec_target"), body.get("spec_lsl"), body.get("spec_usl"), body.get("unit")),
        "standard_id",
    )
    conn.commit()
    conn.close()
    return {"standard_id": standard_id}


# ---------- 검사이력 (구분 필터 — 등록은 기존 POST /api/quality/inspections 재사용) ----------

@router.get("/inspections")
def list_inspections(inspection_type: str = None, material_id: int = None, user: dict = Depends(current_user)):
    conn = get_conn()
    where, params = [], []
    if inspection_type:
        where.append("qi.inspection_type = ?")
        params.append(inspection_type)
    if material_id:
        where.append("qi.material_id = ?")
        params.append(material_id)
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    rows = rows_to_list(run(
        conn,
        "SELECT qi.*, m.name AS material_name FROM quality_inspection qi "
        "JOIN material m ON m.material_id = qi.material_id "
        f"{where_sql} ORDER BY qi.inspection_id DESC LIMIT 200",
        tuple(params),
    ))
    conn.close()
    return rows


# ---------- SPC / 공정능력분석 ----------

@router.get("/spc/{material_id}")
def spc_analysis(material_id: int, user: dict = Depends(current_user)):
    """defect_ppm 시계열 기준 관리도 통계 + (검사기준 LSL/USL 존재 시) Cp/Cpk. 프로토타입 근사."""
    conn = get_conn()
    _check_material(conn, material_id)
    rows = rows_to_list(run(
        conn,
        "SELECT inspection_date, inspection_type, defect_ppm FROM quality_inspection "
        "WHERE material_id=? AND defect_ppm IS NOT NULL ORDER BY inspection_id",
        (material_id,),
    ))
    standard = one(run(
        conn,
        "SELECT * FROM inspection_standard WHERE material_id=? AND spec_lsl IS NOT NULL "
        "AND spec_usl IS NOT NULL ORDER BY standard_id LIMIT 1",
        (material_id,),
    ))
    conn.close()
    values = [r["defect_ppm"] for r in rows]
    if len(values) < 2:
        return {"material_id": material_id, "sample_count": len(values), "points": rows,
                "mean": None, "std": None, "ucl": None, "lcl": None,
                "out_of_control_count": None, "cp": None, "cpk": None, "standard": standard}
    m = mean(values)
    s = stdev(values)
    ucl = m + 3 * s
    lcl = max(0.0, m - 3 * s)
    out_of_control = sum(1 for v in values if v > ucl or v < lcl)
    cp = cpk = None
    if standard and s > 0:
        lsl, usl = standard["spec_lsl"], standard["spec_usl"]
        cp = round((usl - lsl) / (6 * s), 3)
        cpk = round(min((usl - m) / (3 * s), (m - lsl) / (3 * s)), 3)
    return {
        "material_id": material_id,
        "sample_count": len(values),
        "points": rows[-50:],  # 최근 50개만(응답 크기 제한)
        "mean": round(m, 1),
        "std": round(s, 1),
        "ucl": round(ucl, 1),
        "lcl": round(lcl, 1),
        "out_of_control_count": out_of_control,
        "cp": cp,
        "cpk": cpk,
        "standard": standard,
    }


# ---------- 부적합관리 (조회 — 처리는 생산 > 재작업) ----------

@router.get("/nonconformance")
def nonconformance(user: dict = Depends(current_user)):
    conn = get_conn()
    defective_serials = rows_to_list(run(
        conn,
        "SELECT s.serial_id, s.serial_no, s.status, m.name AS material_name, "
        "(SELECT COUNT(*) FROM rework_order r WHERE r.serial_id = s.serial_id AND r.status='OPEN') AS open_rework "
        "FROM serial_number s JOIN material m ON m.material_id = s.material_id "
        "WHERE s.status='DEFECTIVE' ORDER BY s.serial_id DESC LIMIT 100",
    ))
    fail_inspections = rows_to_list(run(
        conn,
        "SELECT qi.inspection_id, qi.inspection_date, qi.inspection_type, qi.defect_qty, qi.defect_ppm, "
        "m.name AS material_name FROM quality_inspection qi "
        "JOIN material m ON m.material_id = qi.material_id "
        "WHERE qi.result='FAIL' ORDER BY qi.inspection_id DESC LIMIT 50",
    ))
    conn.close()
    return {"defective_serials": defective_serials, "fail_inspections": fail_inspections}


# ---------- 8D Report ----------

@router.get("/eight-d")
def list_eight_d(user: dict = Depends(current_user)):
    conn = get_conn()
    rows = rows_to_list(run(
        conn,
        "SELECT r.*, m.name AS material_name FROM eight_d_report r "
        "LEFT JOIN material m ON m.material_id = r.material_id ORDER BY r.report_id DESC",
    ))
    conn.close()
    return rows


@router.post("/eight-d")
def create_eight_d(body: dict = Body(...), user: dict = Depends(require_roles(*_WRITE))):
    _require(body, "title")
    conn = get_conn()
    if body.get("material_id"):
        _check_material(conn, body["material_id"])
    report_id = insert_returning(
        conn,
        "INSERT INTO eight_d_report (material_id, inspection_id, title, problem, root_cause, "
        "corrective_action, report_date) VALUES (?,?,?,?,?,?,?)",
        (body.get("material_id"), body.get("inspection_id"), body["title"], body.get("problem"),
         body.get("root_cause"), body.get("corrective_action"), date.today().isoformat()),
        "report_id",
    )
    conn.commit()
    conn.close()
    return {"report_id": report_id}


@router.post("/eight-d/{report_id}/status")
def update_eight_d_status(
    report_id: int, body: dict = Body(...), user: dict = Depends(require_roles(*_WRITE)),
):
    _require(body, "status")
    if body["status"] not in EIGHT_D_STATUSES:
        raise HTTPException(400, f"status는 {', '.join(sorted(EIGHT_D_STATUSES))} 중 하나여야 함")
    conn = get_conn()
    if one(run(conn, "SELECT report_id FROM eight_d_report WHERE report_id=?", (report_id,))) is None:
        conn.close()
        raise HTTPException(404, "8D Report를 찾을 수 없음")
    closed_date = date.today().isoformat() if body["status"] == "CLOSED" else None
    run(conn, "UPDATE eight_d_report SET status=?, closed_date=? WHERE report_id=?",
        (body["status"], closed_date, report_id))
    conn.commit()
    conn.close()
    return {"report_id": report_id, "status": body["status"]}


# ---------- 고객클레임관리 ----------

@router.get("/claims")
def list_claims(user: dict = Depends(current_user)):
    conn = get_conn()
    rows = rows_to_list(run(
        conn,
        "SELECT c.*, cu.name AS customer_name, m.name AS material_name FROM customer_claim c "
        "JOIN customer cu ON cu.customer_id = c.customer_id "
        "LEFT JOIN material m ON m.material_id = c.material_id ORDER BY c.claim_id DESC",
    ))
    conn.close()
    return rows


@router.post("/claims")
def create_claim(body: dict = Body(...), user: dict = Depends(require_roles("영업담당", *_WRITE))):
    """고객 접점이라 영업담당도 등록 가능(처리 상태 변경은 품질 쪽 권한과 동일하게 유지)."""
    _require(body, "customer_id")
    claim_type = body.get("claim_type", "QUALITY")
    if claim_type not in CLAIM_TYPES:
        raise HTTPException(400, f"claim_type은 {', '.join(sorted(CLAIM_TYPES))} 중 하나여야 함")
    conn = get_conn()
    if one(run(conn, "SELECT customer_id FROM customer WHERE customer_id=?", (body["customer_id"],))) is None:
        conn.close()
        raise HTTPException(404, "고객을 찾을 수 없음")
    if body.get("material_id"):
        _check_material(conn, body["material_id"])
    claim_id = insert_returning(
        conn,
        "INSERT INTO customer_claim (customer_id, material_id, claim_type, description, qty, claim_date) "
        "VALUES (?,?,?,?,?,?)",
        (body["customer_id"], body.get("material_id"), claim_type, body.get("description"),
         body.get("qty"), date.today().isoformat()),
        "claim_id",
    )
    conn.commit()
    conn.close()
    return {"claim_id": claim_id}


@router.post("/claims/{claim_id}/status")
def update_claim_status(
    claim_id: int, body: dict = Body(...), user: dict = Depends(require_roles(*_WRITE)),
):
    _require(body, "status")
    if body["status"] not in CLAIM_STATUSES:
        raise HTTPException(400, f"status는 {', '.join(sorted(CLAIM_STATUSES))} 중 하나여야 함")
    conn = get_conn()
    if one(run(conn, "SELECT claim_id FROM customer_claim WHERE claim_id=?", (claim_id,))) is None:
        conn.close()
        raise HTTPException(404, "클레임을 찾을 수 없음")
    resolved_date = date.today().isoformat() if body["status"] in ("RESOLVED", "REJECTED") else None
    run(conn, "UPDATE customer_claim SET status=?, resolved_date=? WHERE claim_id=?",
        (body["status"], resolved_date, claim_id))
    conn.commit()
    conn.close()
    return {"claim_id": claim_id, "status": body["status"]}


# ---------- CAPA ----------

@router.get("/capa")
def list_capa(user: dict = Depends(current_user)):
    conn = get_conn()
    actions = rows_to_list(run(conn, "SELECT * FROM capa_action ORDER BY capa_id DESC"))
    # 기존 capa_required='Y' 검사 중 아직 CAPA 액션이 연결되지 않은 건 = CAPA 후보
    candidates = rows_to_list(run(
        conn,
        "SELECT qi.inspection_id, qi.inspection_date, qi.inspection_type, qi.result, "
        "m.name AS material_name FROM quality_inspection qi "
        "JOIN material m ON m.material_id = qi.material_id "
        "WHERE qi.capa_required='Y' AND qi.inspection_id NOT IN "
        "(SELECT inspection_id FROM capa_action WHERE inspection_id IS NOT NULL) "
        "ORDER BY qi.inspection_id DESC LIMIT 50",
    ))
    conn.close()
    return {"actions": actions, "candidates": candidates}


@router.post("/capa")
def create_capa(body: dict = Body(...), user: dict = Depends(require_roles(*_WRITE))):
    _require(body, "title")
    source = body.get("source", "INSPECTION")
    action_type = body.get("action_type", "CORRECTIVE")
    if source not in CAPA_SOURCES:
        raise HTTPException(400, f"source는 {', '.join(sorted(CAPA_SOURCES))} 중 하나여야 함")
    if action_type not in CAPA_TYPES:
        raise HTTPException(400, f"action_type은 {', '.join(sorted(CAPA_TYPES))} 중 하나여야 함")
    conn = get_conn()
    if body.get("inspection_id"):
        if one(run(conn, "SELECT inspection_id FROM quality_inspection WHERE inspection_id=?",
                   (body["inspection_id"],))) is None:
            conn.close()
            raise HTTPException(404, "검사를 찾을 수 없음")
    capa_id = insert_returning(
        conn,
        "INSERT INTO capa_action (source, inspection_id, title, action_type, due_date, created_date, notes) "
        "VALUES (?,?,?,?,?,?,?)",
        (source, body.get("inspection_id"), body["title"], action_type, body.get("due_date"),
         date.today().isoformat(), body.get("notes")),
        "capa_id",
    )
    conn.commit()
    conn.close()
    return {"capa_id": capa_id}


@router.post("/capa/{capa_id}/status")
def update_capa_status(
    capa_id: int, body: dict = Body(...), user: dict = Depends(require_roles(*_WRITE)),
):
    _require(body, "status")
    if body["status"] not in CAPA_STATUSES:
        raise HTTPException(400, f"status는 {', '.join(sorted(CAPA_STATUSES))} 중 하나여야 함")
    conn = get_conn()
    if one(run(conn, "SELECT capa_id FROM capa_action WHERE capa_id=?", (capa_id,))) is None:
        conn.close()
        raise HTTPException(404, "CAPA를 찾을 수 없음")
    completed_date = date.today().isoformat() if body["status"] == "DONE" else None
    run(conn, "UPDATE capa_action SET status=?, completed_date=? WHERE capa_id=?",
        (body["status"], completed_date, capa_id))
    conn.commit()
    conn.close()
    return {"capa_id": capa_id, "status": body["status"]}


# ---------- 품질 Dashboard ----------

@router.get("/dashboard")
def quality_dashboard(user: dict = Depends(current_user)):
    conn = get_conn()
    total = one(run(conn, "SELECT COUNT(*) c, COALESCE(AVG(defect_ppm),0) ppm FROM quality_inspection"))
    fail_count = one(run(conn, "SELECT COUNT(*) c FROM quality_inspection WHERE result='FAIL'"))["c"]
    defective_serials = one(run(conn, "SELECT COUNT(*) c FROM serial_number WHERE status='DEFECTIVE'"))["c"]
    open_capa = one(run(conn, "SELECT COUNT(*) c FROM capa_action WHERE status != 'DONE'"))["c"]
    capa_candidates = one(run(
        conn,
        "SELECT COUNT(*) c FROM quality_inspection WHERE capa_required='Y' AND inspection_id NOT IN "
        "(SELECT inspection_id FROM capa_action WHERE inspection_id IS NOT NULL)",
    ))["c"]
    open_claims = one(run(conn, "SELECT COUNT(*) c FROM customer_claim WHERE status IN ('OPEN','INVESTIGATING')"))["c"]
    open_8d = one(run(conn, "SELECT COUNT(*) c FROM eight_d_report WHERE status != 'CLOSED'"))["c"]
    standard_count = one(run(conn, "SELECT COUNT(*) c FROM inspection_standard"))["c"]
    conn.close()
    return {
        "inspection_count": total["c"],
        "avg_defect_ppm": round(total["ppm"], 1),
        "fail_count": fail_count,
        "defective_serial_count": defective_serials,
        "open_capa_count": open_capa,
        "capa_candidate_count": capa_candidates,
        "open_claim_count": open_claims,
        "open_8d_count": open_8d,
        "standard_count": standard_count,
    }
