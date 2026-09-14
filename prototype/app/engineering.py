"""07. Engineering(R&D) 신규 (v15) — BOM관리/ECO·ECR/도면/표준부품/프로젝트/시제품/개발원가/R&D Dashboard.

task-plan-v9-full-menu-rollout.md §3 v15. 신규 테이블 5종 + material.is_standard_part(migrations/0009).

- BOM 관리: 기존 bom 테이블(v1)의 트리 전개 조회. 현 데이터셋 BOM은 1단계지만 다단계도 재귀 전개
  지원(순환 참조 방어 포함). BOM 직접 수정 API는 없음 — 변경은 반드시 ECO를 거친다(설계 의도).
- ECO/ECR: BOM 변경요청(ADD/UPDATE/REMOVE) → approval_workflow 'ECO' 등록(승인함 재사용, v9 패턴)
  → 관리자 승인 시 bom 테이블 자동 적용(apply — main.py decide_approval 분기에서 호출).
- 도면관리: 메타데이터+외부링크만(파일 업로드 비범위 — task-plan 명시).
- 부품/설계 표준화: material.is_standard_part 플래그 토글 + 표준부품 목록.
- 프로젝트/시제품/개발원가: 간이 마스터+등록. 시제품 stage DESIGN→BUILD→TEST→DONE.
- 쓰기 권한: 생산담당+관리자("설계담당" 역할 없음 — v3 QMS와 같은 절충). ECO 승인은 관리자(승인함).

날짜는 date.today() 명시(UTC 기본값 미사용 — 확립된 패턴).
"""
from datetime import date

from fastapi import APIRouter, Body, Depends, HTTPException

from .database import get_conn, run, one, rows_to_list, insert_returning
from .auth import require_roles, current_user

router = APIRouter(prefix="/api/engineering", tags=["engineering"])

ECO_CHANGE_TYPES = {"ADD", "UPDATE", "REMOVE"}
PROJECT_STATUSES = {"PLANNED", "IN_PROGRESS", "DONE", "HOLD"}
PROTO_STAGES = {"DESIGN", "BUILD", "TEST", "DONE"}
DEV_COST_TYPES = {"LABOR", "MATERIAL", "OUTSOURCING", "OTHER"}

_WRITE = ("생산담당", "관리자")


def _require(body: dict, *fields):
    missing = [f for f in fields if body.get(f) in (None, "")]
    if missing:
        raise HTTPException(400, f"필수 항목 누락: {', '.join(missing)}")


def _check_material(conn, material_id, label="품목"):
    if one(run(conn, "SELECT material_id FROM material WHERE material_id=?", (material_id,))) is None:
        conn.close()
        raise HTTPException(404, f"{label}을(를) 찾을 수 없음")


# ---------- BOM 관리 (조회 — 변경은 ECO 경유) ----------

@router.get("/bom-parents")
def bom_parents(user: dict = Depends(current_user)):
    """BOM을 가진 완제품(부모) 목록 + 자재 수."""
    conn = get_conn()
    rows = rows_to_list(run(
        conn,
        "SELECT b.parent_material_id AS material_id, m.code, m.name, COUNT(*) AS child_count "
        "FROM bom b JOIN material m ON m.material_id = b.parent_material_id "
        "GROUP BY b.parent_material_id, m.code, m.name ORDER BY m.material_id",
    ))
    conn.close()
    return rows


@router.get("/bom-tree/{material_id}")
def bom_tree(material_id: int, user: dict = Depends(current_user)):
    """BOM 재귀 전개(다단계 지원, 순환 방어). 현 데이터셋은 1단계."""
    conn = get_conn()
    _check_material(conn, material_id)

    def expand(parent_id, level, visited):
        if parent_id in visited or level > 10:
            return []  # 순환 참조/과도한 깊이 방어
        children = rows_to_list(run(
            conn,
            "SELECT b.bom_id, b.child_material_id, b.qty, b.version, m.code, m.name, m.material_type, "
            "m.std_cost, m.is_standard_part "
            "FROM bom b JOIN material m ON m.material_id = b.child_material_id "
            "WHERE b.parent_material_id=? ORDER BY b.bom_id",
            (parent_id,),
        ))
        result = []
        for c in children:
            node = dict(c)
            node["level"] = level
            node["children"] = expand(c["child_material_id"], level + 1, visited | {parent_id})
            result.append(node)
        return result

    parent = one(run(conn, "SELECT material_id, code, name FROM material WHERE material_id=?", (material_id,)))
    tree = expand(material_id, 1, set())
    conn.close()
    return {"parent": parent, "children": tree}


# ---------- ECO/ECR (승인함 재사용) ----------

@router.get("/eco")
def list_eco(user: dict = Depends(current_user)):
    conn = get_conn()
    rows = rows_to_list(run(
        conn,
        "SELECT e.*, pm.name AS parent_name, cm.name AS child_name FROM eco_request e "
        "JOIN material pm ON pm.material_id = e.parent_material_id "
        "JOIN material cm ON cm.material_id = e.child_material_id "
        "ORDER BY e.eco_id DESC",
    ))
    conn.close()
    return rows


@router.post("/eco")
def create_eco(body: dict = Body(...), user: dict = Depends(require_roles(*_WRITE))):
    _require(body, "title", "parent_material_id", "change_type", "child_material_id")
    if body["change_type"] not in ECO_CHANGE_TYPES:
        raise HTTPException(400, f"change_type은 {', '.join(sorted(ECO_CHANGE_TYPES))} 중 하나여야 함")
    if body["change_type"] in ("ADD", "UPDATE") and not body.get("new_qty"):
        raise HTTPException(400, "ADD/UPDATE는 new_qty가 필요함")
    conn = get_conn()
    _check_material(conn, body["parent_material_id"], "부모 품목")
    _check_material(conn, body["child_material_id"], "자재 품목")
    existing = one(run(
        conn, "SELECT bom_id FROM bom WHERE parent_material_id=? AND child_material_id=?",
        (body["parent_material_id"], body["child_material_id"]),
    ))
    if body["change_type"] == "ADD" and existing is not None:
        conn.close()
        raise HTTPException(400, "이미 BOM에 존재하는 자재 — UPDATE를 사용하세요")
    if body["change_type"] in ("UPDATE", "REMOVE") and existing is None:
        conn.close()
        raise HTTPException(400, "BOM에 없는 자재 — ADD를 사용하세요")
    eco_id = insert_returning(
        conn,
        "INSERT INTO eco_request (title, parent_material_id, change_type, child_material_id, new_qty, "
        "reason, request_date) VALUES (?,?,?,?,?,?,?)",
        (body["title"], body["parent_material_id"], body["change_type"], body["child_material_id"],
         body.get("new_qty"), body.get("reason"), date.today().isoformat()),
        "eco_id",
    )
    # 승인함 재사용 — v9 quotation/sales_return과 동일 패턴
    run(conn, "INSERT INTO approval_workflow (doc_type, doc_id) VALUES ('ECO', ?)", (eco_id,))
    conn.commit()
    conn.close()
    return {"eco_id": eco_id}


def apply_eco(conn, eco_id: int, approved: bool):
    """decide_approval(main.py)의 ECO 분기에서 호출. 승인 시 bom에 실제 적용."""
    eco = one(run(conn, "SELECT * FROM eco_request WHERE eco_id=?", (eco_id,)))
    if eco is None:
        return
    new_status = "APPROVED" if approved else "REJECTED"
    run(conn, "UPDATE eco_request SET status=? WHERE eco_id=?", (new_status, eco_id))
    if not approved:
        return
    if eco["change_type"] == "ADD":
        run(conn, "INSERT INTO bom (parent_material_id, child_material_id, qty) VALUES (?,?,?)",
            (eco["parent_material_id"], eco["child_material_id"], eco["new_qty"]))
    elif eco["change_type"] == "UPDATE":
        run(conn, "UPDATE bom SET qty=? WHERE parent_material_id=? AND child_material_id=?",
            (eco["new_qty"], eco["parent_material_id"], eco["child_material_id"]))
    elif eco["change_type"] == "REMOVE":
        run(conn, "DELETE FROM bom WHERE parent_material_id=? AND child_material_id=?",
            (eco["parent_material_id"], eco["child_material_id"]))
    run(conn, "UPDATE eco_request SET applied=1, applied_date=? WHERE eco_id=?",
        (date.today().isoformat(), eco_id))


# ---------- 도면관리 ----------

@router.get("/drawings")
def list_drawings(user: dict = Depends(current_user)):
    conn = get_conn()
    rows = rows_to_list(run(
        conn,
        "SELECT d.*, m.name AS material_name FROM drawing_doc d "
        "JOIN material m ON m.material_id = d.material_id ORDER BY d.drawing_id DESC",
    ))
    conn.close()
    return rows


@router.post("/drawings")
def create_drawing(body: dict = Body(...), user: dict = Depends(require_roles(*_WRITE))):
    _require(body, "material_id", "doc_no")
    conn = get_conn()
    _check_material(conn, body["material_id"])
    drawing_id = insert_returning(
        conn,
        "INSERT INTO drawing_doc (material_id, doc_no, title, revision, file_url, created_date) "
        "VALUES (?,?,?,?,?,?)",
        (body["material_id"], body["doc_no"], body.get("title"), body.get("revision", "A"),
         body.get("file_url"), date.today().isoformat()),
        "drawing_id",
    )
    conn.commit()
    conn.close()
    return {"drawing_id": drawing_id}


# ---------- 부품/설계 표준화 ----------

@router.get("/standard-parts")
def list_standard_parts(user: dict = Depends(current_user)):
    conn = get_conn()
    rows = rows_to_list(run(
        conn,
        "SELECT material_id, code, name, material_type, uom, is_standard_part, "
        "(SELECT COUNT(*) FROM bom b WHERE b.child_material_id = material.material_id) AS used_in_boms "
        "FROM material ORDER BY is_standard_part DESC, material_id",
    ))
    conn.close()
    return rows


@router.post("/standard-parts/{material_id}/toggle")
def toggle_standard_part(material_id: int, user: dict = Depends(require_roles(*_WRITE))):
    conn = get_conn()
    row = one(run(conn, "SELECT is_standard_part FROM material WHERE material_id=?", (material_id,)))
    if row is None:
        conn.close()
        raise HTTPException(404, "품목을 찾을 수 없음")
    new_val = 0 if row["is_standard_part"] else 1
    run(conn, "UPDATE material SET is_standard_part=? WHERE material_id=?", (new_val, material_id))
    conn.commit()
    conn.close()
    return {"material_id": material_id, "is_standard_part": new_val}


# ---------- 프로젝트관리 ----------

@router.get("/projects")
def list_projects(user: dict = Depends(current_user)):
    conn = get_conn()
    rows = rows_to_list(run(
        conn,
        "SELECT p.*, "
        "(SELECT COALESCE(SUM(amount),0) FROM dev_cost dc WHERE dc.project_id = p.project_id) AS total_cost, "
        "(SELECT COUNT(*) FROM prototype_item pi WHERE pi.project_id = p.project_id) AS proto_count "
        "FROM rnd_project p ORDER BY p.project_id DESC",
    ))
    conn.close()
    return rows


@router.post("/projects")
def create_project(body: dict = Body(...), user: dict = Depends(require_roles(*_WRITE))):
    _require(body, "name")
    conn = get_conn()
    project_id = insert_returning(
        conn,
        "INSERT INTO rnd_project (name, owner, start_date, end_date, budget, notes) VALUES (?,?,?,?,?,?)",
        (body["name"], body.get("owner"), body.get("start_date"), body.get("end_date"),
         body.get("budget"), body.get("notes")),
        "project_id",
    )
    conn.commit()
    conn.close()
    return {"project_id": project_id}


@router.post("/projects/{project_id}/status")
def update_project_status(
    project_id: int, body: dict = Body(...), user: dict = Depends(require_roles(*_WRITE)),
):
    _require(body, "status")
    if body["status"] not in PROJECT_STATUSES:
        raise HTTPException(400, f"status는 {', '.join(sorted(PROJECT_STATUSES))} 중 하나여야 함")
    conn = get_conn()
    if one(run(conn, "SELECT project_id FROM rnd_project WHERE project_id=?", (project_id,))) is None:
        conn.close()
        raise HTTPException(404, "프로젝트를 찾을 수 없음")
    run(conn, "UPDATE rnd_project SET status=? WHERE project_id=?", (body["status"], project_id))
    conn.commit()
    conn.close()
    return {"project_id": project_id, "status": body["status"]}


# ---------- 시제품관리 ----------

@router.get("/prototypes")
def list_prototypes(user: dict = Depends(current_user)):
    conn = get_conn()
    rows = rows_to_list(run(
        conn,
        "SELECT pi.*, p.name AS project_name, m.name AS material_name FROM prototype_item pi "
        "JOIN rnd_project p ON p.project_id = pi.project_id "
        "LEFT JOIN material m ON m.material_id = pi.material_id ORDER BY pi.proto_id DESC",
    ))
    conn.close()
    return rows


@router.post("/prototypes")
def create_prototype(body: dict = Body(...), user: dict = Depends(require_roles(*_WRITE))):
    _require(body, "project_id", "name")
    conn = get_conn()
    if one(run(conn, "SELECT project_id FROM rnd_project WHERE project_id=?", (body["project_id"],))) is None:
        conn.close()
        raise HTTPException(404, "프로젝트를 찾을 수 없음")
    if body.get("material_id"):
        _check_material(conn, body["material_id"])
    proto_id = insert_returning(
        conn,
        "INSERT INTO prototype_item (project_id, material_id, name, created_date) VALUES (?,?,?,?)",
        (body["project_id"], body.get("material_id"), body["name"], date.today().isoformat()),
        "proto_id",
    )
    conn.commit()
    conn.close()
    return {"proto_id": proto_id}


@router.post("/prototypes/{proto_id}/stage")
def update_prototype_stage(
    proto_id: int, body: dict = Body(...), user: dict = Depends(require_roles(*_WRITE)),
):
    _require(body, "stage")
    if body["stage"] not in PROTO_STAGES:
        raise HTTPException(400, f"stage는 {', '.join(sorted(PROTO_STAGES))} 중 하나여야 함")
    conn = get_conn()
    if one(run(conn, "SELECT proto_id FROM prototype_item WHERE proto_id=?", (proto_id,))) is None:
        conn.close()
        raise HTTPException(404, "시제품을 찾을 수 없음")
    run(conn, "UPDATE prototype_item SET stage=?, test_result=? WHERE proto_id=?",
        (body["stage"], body.get("test_result"), proto_id))
    conn.commit()
    conn.close()
    return {"proto_id": proto_id, "stage": body["stage"]}


# ---------- 개발원가관리 ----------

@router.get("/dev-costs")
def list_dev_costs(user: dict = Depends(current_user)):
    conn = get_conn()
    rows = rows_to_list(run(
        conn,
        "SELECT dc.*, p.name AS project_name FROM dev_cost dc "
        "JOIN rnd_project p ON p.project_id = dc.project_id ORDER BY dc.cost_id DESC",
    ))
    conn.close()
    return rows


@router.post("/dev-costs")
def create_dev_cost(body: dict = Body(...), user: dict = Depends(require_roles(*_WRITE))):
    _require(body, "project_id", "cost_type", "amount")
    if body["cost_type"] not in DEV_COST_TYPES:
        raise HTTPException(400, f"cost_type은 {', '.join(sorted(DEV_COST_TYPES))} 중 하나여야 함")
    try:
        amount = float(body["amount"])
    except (TypeError, ValueError):
        raise HTTPException(400, "amount는 숫자여야 함")
    if amount <= 0:
        raise HTTPException(400, "amount는 0보다 커야 함")
    conn = get_conn()
    if one(run(conn, "SELECT project_id FROM rnd_project WHERE project_id=?", (body["project_id"],))) is None:
        conn.close()
        raise HTTPException(404, "프로젝트를 찾을 수 없음")
    cost_id = insert_returning(
        conn,
        "INSERT INTO dev_cost (project_id, cost_type, amount, cost_date, notes) VALUES (?,?,?,?,?)",
        (body["project_id"], body["cost_type"], amount, date.today().isoformat(), body.get("notes")),
        "cost_id",
    )
    conn.commit()
    conn.close()
    return {"cost_id": cost_id}


# ---------- R&D Dashboard ----------

@router.get("/dashboard")
def engineering_dashboard(user: dict = Depends(current_user)):
    conn = get_conn()
    bom_parent_count = one(run(conn, "SELECT COUNT(DISTINCT parent_material_id) c FROM bom"))["c"]
    pending_eco = one(run(conn, "SELECT COUNT(*) c FROM eco_request WHERE status='PENDING'"))["c"]
    applied_eco = one(run(conn, "SELECT COUNT(*) c FROM eco_request WHERE applied=1"))["c"]
    drawing_count = one(run(conn, "SELECT COUNT(*) c FROM drawing_doc"))["c"]
    standard_parts = one(run(conn, "SELECT COUNT(*) c FROM material WHERE is_standard_part=1"))["c"]
    active_projects = one(run(conn, "SELECT COUNT(*) c FROM rnd_project WHERE status='IN_PROGRESS'"))["c"]
    total_dev_cost = one(run(conn, "SELECT COALESCE(SUM(amount),0) s FROM dev_cost"))["s"]
    proto_in_test = one(run(conn, "SELECT COUNT(*) c FROM prototype_item WHERE stage='TEST'"))["c"]
    conn.close()
    return {
        "bom_parent_count": bom_parent_count,
        "pending_eco_count": pending_eco,
        "applied_eco_count": applied_eco,
        "drawing_count": drawing_count,
        "standard_part_count": standard_parts,
        "active_project_count": active_projects,
        "total_dev_cost": total_dev_cost,
        "proto_in_test_count": proto_in_test,
    }
