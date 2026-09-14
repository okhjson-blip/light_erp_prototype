"""04. Logistics Management 확장 (v12) — 창고Location/컨테이너/운송/물류비정산/수출입현황/보험·클레임.

task-plan-v9-full-menu-rollout.md §3 v12. 기존 shipment(출하)/import_customs_record(03 통관) 테이블을
공유하고, 신규 테이블 6종(migrations/0006)은 전부 additive.

- 창고관리(Location): warehouse_location 마스터 등록/조회만. 재고 트랜잭션과의 바인딩은
  Enterprise 단계로 이연(현 inventory는 창고 단위 집계라 Location 차원이 없음 — 알려진 범위 제한).
- 컨테이너: 출하(선택)와 연결, 상태 EMPTY→STUFFING→SEALED→SHIPPED→RETURNED.
- 운송관리(TMS 간이): shipment 단위 배차 기록(운송사/차량/기사), 상태 PLANNED→IN_TRANSIT→DELIVERED.
- 물류비 정산: 비용 입력(FREIGHT/INSURANCE/CUSTOMS/HANDLING/OTHER) → 정산 시 회계 전표
  (차변 5100 물류비 / 대변 2000 매입채무) 연동 — 정산은 관리자 전용(v5 회계 제한 정책과 일치).
- 수출관리: shipment + 운송/컨테이너 연결 현황 조회(수입관리는 03 통관 화면/API 재사용).
- 보험/클레임: 간이 마스터+등록. 클레임 상태 OPEN→RESOLVED/REJECTED.
- 물류 Dashboard: 위 지표 요약(SCM Control Tower와 동일 패턴 — 신규 집계 없이 카운트/합계만).

날짜 컬럼은 DB 기본값(date('now')=UTC)에 맡기지 않고 서버 로컬 date.today()를 명시한다
(v11 검증에서 발견된 KST 새벽 하루 밀림 문제의 재발 방지 — procurement_ext.py와 동일 패턴).
"""
from datetime import date

from fastapi import APIRouter, Body, Depends, HTTPException

from .database import get_conn, run, one, rows_to_list, insert_returning
from .helpers import post_accounting
from .auth import require_roles, current_user

router = APIRouter(prefix="/api/logistics", tags=["logistics"])

CONTAINER_STATUSES = {"EMPTY", "STUFFING", "SEALED", "SHIPPED", "RETURNED"}
TRANSPORT_STATUSES = {"PLANNED", "IN_TRANSIT", "DELIVERED"}
COST_TYPES = {"FREIGHT", "INSURANCE", "CUSTOMS", "HANDLING", "OTHER"}
CLAIM_STATUSES = {"OPEN", "RESOLVED", "REJECTED"}
CLAIM_TYPES = {"DAMAGE", "LOSS", "DELAY", "OTHER"}

_WRITE_ROLES = ("영업담당", "관리자")  # 출하 파생 업무라 영업담당 기준(정산만 관리자 전용)


def _require(body: dict, *fields):
    missing = [f for f in fields if body.get(f) in (None, "")]
    if missing:
        raise HTTPException(400, f"필수 항목 누락: {', '.join(missing)}")


def _check_shipment(conn, shipment_id, *, optional=False):
    if shipment_id in (None, ""):
        if optional:
            return None
        raise HTTPException(400, "필수 항목 누락: shipment_id")
    row = one(run(conn, "SELECT shipment_id FROM shipment WHERE shipment_id=?", (shipment_id,)))
    if row is None:
        conn.close()
        raise HTTPException(404, "출하를 찾을 수 없음")
    return shipment_id


# ---------- 창고관리 (Location) ----------

@router.get("/locations")
def list_locations(user: dict = Depends(current_user)):
    conn = get_conn()
    rows = rows_to_list(run(
        conn,
        "SELECT l.*, w.name AS warehouse_name FROM warehouse_location l "
        "JOIN warehouse w ON w.warehouse_id = l.warehouse_id "
        "ORDER BY l.warehouse_id, l.code",
    ))
    conn.close()
    return rows


@router.post("/locations")
def create_location(body: dict = Body(...), user: dict = Depends(require_roles("관리자"))):
    _require(body, "warehouse_id", "code")
    conn = get_conn()
    wh = one(run(conn, "SELECT warehouse_id FROM warehouse WHERE warehouse_id=?", (body["warehouse_id"],)))
    if wh is None:
        conn.close()
        raise HTTPException(404, "창고를 찾을 수 없음")
    dup = one(run(
        conn, "SELECT location_id FROM warehouse_location WHERE warehouse_id=? AND code=?",
        (body["warehouse_id"], body["code"]),
    ))
    if dup is not None:
        conn.close()
        raise HTTPException(400, "이미 존재하는 Location 코드")
    location_id = insert_returning(
        conn,
        "INSERT INTO warehouse_location (warehouse_id, code, name, location_type) VALUES (?,?,?,?)",
        (body["warehouse_id"], body["code"], body.get("name"), body.get("location_type", "BIN")),
        "location_id",
    )
    conn.commit()
    conn.close()
    return {"location_id": location_id}


# ---------- 컨테이너 관리 ----------

@router.get("/containers")
def list_containers(user: dict = Depends(current_user)):
    conn = get_conn()
    rows = rows_to_list(run(
        conn,
        "SELECT c.*, s.external_no AS shipment_no FROM container c "
        "LEFT JOIN shipment s ON s.shipment_id = c.shipment_id "
        "ORDER BY c.container_id DESC",
    ))
    conn.close()
    return rows


@router.post("/containers")
def create_container(body: dict = Body(...), user: dict = Depends(require_roles(*_WRITE_ROLES))):
    _require(body, "container_no")
    conn = get_conn()
    _check_shipment(conn, body.get("shipment_id"), optional=True)
    container_id = insert_returning(
        conn,
        "INSERT INTO container (container_no, container_type, shipment_id, notes) VALUES (?,?,?,?)",
        (body["container_no"], body.get("container_type", "40FT"), body.get("shipment_id"), body.get("notes")),
        "container_id",
    )
    conn.commit()
    conn.close()
    return {"container_id": container_id}


@router.post("/containers/{container_id}/status")
def update_container_status(
    container_id: int, body: dict = Body(...), user: dict = Depends(require_roles(*_WRITE_ROLES)),
):
    _require(body, "status")
    if body["status"] not in CONTAINER_STATUSES:
        raise HTTPException(400, f"status는 {', '.join(sorted(CONTAINER_STATUSES))} 중 하나여야 함")
    conn = get_conn()
    row = one(run(conn, "SELECT container_id FROM container WHERE container_id=?", (container_id,)))
    if row is None:
        conn.close()
        raise HTTPException(404, "컨테이너를 찾을 수 없음")
    run(conn, "UPDATE container SET status=? WHERE container_id=?", (body["status"], container_id))
    conn.commit()
    conn.close()
    return {"container_id": container_id, "status": body["status"]}


# ---------- 운송관리 (TMS 간이) ----------

@router.get("/transports")
def list_transports(user: dict = Depends(current_user)):
    conn = get_conn()
    rows = rows_to_list(run(
        conn,
        "SELECT t.*, s.external_no AS shipment_no, s.carrier AS shipment_carrier "
        "FROM shipment_transport t JOIN shipment s ON s.shipment_id = t.shipment_id "
        "ORDER BY t.transport_id DESC",
    ))
    conn.close()
    return rows


@router.post("/transports")
def create_transport(body: dict = Body(...), user: dict = Depends(require_roles(*_WRITE_ROLES))):
    _require(body, "shipment_id")
    conn = get_conn()
    _check_shipment(conn, body["shipment_id"])
    transport_id = insert_returning(
        conn,
        "INSERT INTO shipment_transport (shipment_id, carrier, vehicle_no, driver, transport_date, freight_cost) "
        "VALUES (?,?,?,?,?,?)",
        (body["shipment_id"], body.get("carrier"), body.get("vehicle_no"), body.get("driver"),
         date.today().isoformat(), body.get("freight_cost")),
        "transport_id",
    )
    conn.commit()
    conn.close()
    return {"transport_id": transport_id}


@router.post("/transports/{transport_id}/status")
def update_transport_status(
    transport_id: int, body: dict = Body(...), user: dict = Depends(require_roles(*_WRITE_ROLES)),
):
    _require(body, "status")
    if body["status"] not in TRANSPORT_STATUSES:
        raise HTTPException(400, f"status는 {', '.join(sorted(TRANSPORT_STATUSES))} 중 하나여야 함")
    conn = get_conn()
    row = one(run(conn, "SELECT transport_id FROM shipment_transport WHERE transport_id=?", (transport_id,)))
    if row is None:
        conn.close()
        raise HTTPException(404, "운송 기록을 찾을 수 없음")
    run(conn, "UPDATE shipment_transport SET status=? WHERE transport_id=?", (body["status"], transport_id))
    conn.commit()
    conn.close()
    return {"transport_id": transport_id, "status": body["status"]}


# ---------- 물류비 정산 ----------

@router.get("/costs")
def list_costs(user: dict = Depends(current_user)):
    conn = get_conn()
    rows = rows_to_list(run(
        conn,
        "SELECT lc.*, s.external_no AS shipment_no FROM logistics_cost lc "
        "LEFT JOIN shipment s ON s.shipment_id = lc.shipment_id "
        "ORDER BY lc.cost_id DESC",
    ))
    conn.close()
    return rows


@router.post("/costs")
def create_cost(body: dict = Body(...), user: dict = Depends(require_roles(*_WRITE_ROLES))):
    _require(body, "cost_type", "amount")
    if body["cost_type"] not in COST_TYPES:
        raise HTTPException(400, f"cost_type은 {', '.join(sorted(COST_TYPES))} 중 하나여야 함")
    try:
        amount = float(body["amount"])
    except (TypeError, ValueError):
        raise HTTPException(400, "amount는 숫자여야 함")
    if amount <= 0:
        raise HTTPException(400, "amount는 0보다 커야 함")
    conn = get_conn()
    _check_shipment(conn, body.get("shipment_id"), optional=True)
    cost_id = insert_returning(
        conn,
        "INSERT INTO logistics_cost (shipment_id, cost_type, amount, cost_date, notes) VALUES (?,?,?,?,?)",
        (body.get("shipment_id"), body["cost_type"], amount, date.today().isoformat(), body.get("notes")),
        "cost_id",
    )
    conn.commit()
    conn.close()
    return {"cost_id": cost_id}


@router.post("/costs/{cost_id}/settle")
def settle_cost(cost_id: int, user: dict = Depends(require_roles("관리자"))):
    """정산 — 회계 전표(차변 5100 물류비 / 대변 2000 매입채무) 생성 후 settled 마킹.

    전표가 만들어지는 금액 이동이라 관리자 전용(v5의 회계 조회 제한과 같은 선상의 정책).
    """
    conn = get_conn()
    cost = one(run(conn, "SELECT * FROM logistics_cost WHERE cost_id=?", (cost_id,)))
    if cost is None:
        conn.close()
        raise HTTPException(404, "물류비를 찾을 수 없음")
    if cost["settled"]:
        conn.close()
        raise HTTPException(400, "이미 정산된 물류비")
    doc_id = post_accounting(
        conn, "LOGISTICS_COST",
        f"물류비 정산 #{cost_id} ({cost['cost_type']})",
        [("5100", cost["amount"], 0), ("2000", 0, cost["amount"])],
    )
    run(conn, "UPDATE logistics_cost SET settled=1, acct_doc_id=? WHERE cost_id=?", (doc_id, cost_id))
    conn.commit()
    conn.close()
    return {"cost_id": cost_id, "settled": True, "acct_doc_id": doc_id}


# ---------- 수출관리 (조회 전용 — 수입관리는 03 통관 API 재사용) ----------

@router.get("/export-status")
def export_status(user: dict = Depends(current_user)):
    """출하별 운송/컨테이너 연결 현황. 별도 수출 테이블 없이 기존 shipment를 물류 관점으로 재구성."""
    conn = get_conn()
    rows = rows_to_list(run(
        conn,
        "SELECT s.shipment_id, s.external_no, s.shipment_date, s.carrier, s.status, "
        "c.name AS customer_name, m.name AS material_name, s.shipped_qty, "
        "(SELECT COUNT(*) FROM shipment_transport t WHERE t.shipment_id = s.shipment_id) AS transport_count, "
        "(SELECT COUNT(*) FROM container ct WHERE ct.shipment_id = s.shipment_id) AS container_count "
        "FROM shipment s "
        "LEFT JOIN customer c ON c.customer_id = s.customer_id "
        "LEFT JOIN material m ON m.material_id = s.material_id "
        "ORDER BY s.shipment_id DESC LIMIT 100",
    ))
    conn.close()
    return rows


# ---------- 보험관리 / 클레임관리 ----------

@router.get("/insurance")
def list_insurance(user: dict = Depends(current_user)):
    conn = get_conn()
    rows = rows_to_list(run(conn, "SELECT * FROM insurance_policy ORDER BY policy_id DESC"))
    conn.close()
    return rows


@router.post("/insurance")
def create_insurance(body: dict = Body(...), user: dict = Depends(require_roles(*_WRITE_ROLES))):
    _require(body, "policy_no", "insurer")
    conn = get_conn()
    policy_id = insert_returning(
        conn,
        "INSERT INTO insurance_policy (policy_no, insurer, coverage, valid_from, valid_to) VALUES (?,?,?,?,?)",
        (body["policy_no"], body["insurer"], body.get("coverage"), body.get("valid_from"), body.get("valid_to")),
        "policy_id",
    )
    conn.commit()
    conn.close()
    return {"policy_id": policy_id}


@router.get("/claims")
def list_claims(user: dict = Depends(current_user)):
    conn = get_conn()
    rows = rows_to_list(run(
        conn,
        "SELECT lc.*, s.external_no AS shipment_no FROM logistics_claim lc "
        "LEFT JOIN shipment s ON s.shipment_id = lc.shipment_id "
        "ORDER BY lc.claim_id DESC",
    ))
    conn.close()
    return rows


@router.post("/claims")
def create_claim(body: dict = Body(...), user: dict = Depends(require_roles(*_WRITE_ROLES))):
    _require(body, "claim_type")
    if body["claim_type"] not in CLAIM_TYPES:
        raise HTTPException(400, f"claim_type은 {', '.join(sorted(CLAIM_TYPES))} 중 하나여야 함")
    conn = get_conn()
    _check_shipment(conn, body.get("shipment_id"), optional=True)
    claim_id = insert_returning(
        conn,
        "INSERT INTO logistics_claim (shipment_id, claim_type, amount, claim_date, notes) VALUES (?,?,?,?,?)",
        (body.get("shipment_id"), body["claim_type"], body.get("amount"), date.today().isoformat(), body.get("notes")),
        "claim_id",
    )
    conn.commit()
    conn.close()
    return {"claim_id": claim_id}


@router.post("/claims/{claim_id}/status")
def update_claim_status(
    claim_id: int, body: dict = Body(...), user: dict = Depends(require_roles(*_WRITE_ROLES)),
):
    _require(body, "status")
    if body["status"] not in CLAIM_STATUSES:
        raise HTTPException(400, f"status는 {', '.join(sorted(CLAIM_STATUSES))} 중 하나여야 함")
    conn = get_conn()
    row = one(run(conn, "SELECT claim_id FROM logistics_claim WHERE claim_id=?", (claim_id,)))
    if row is None:
        conn.close()
        raise HTTPException(404, "클레임을 찾을 수 없음")
    run(conn, "UPDATE logistics_claim SET status=? WHERE claim_id=?", (body["status"], claim_id))
    conn.commit()
    conn.close()
    return {"claim_id": claim_id, "status": body["status"]}


# ---------- 물류 Dashboard ----------

@router.get("/dashboard")
def logistics_dashboard(user: dict = Depends(current_user)):
    """물류 지표 요약 — SCM Control Tower와 동일 패턴(신규 집계 없이 카운트/합계만)."""
    conn = get_conn()
    location_count = one(run(conn, "SELECT COUNT(*) c FROM warehouse_location"))["c"]
    container_active = one(run(
        conn, "SELECT COUNT(*) c FROM container WHERE status NOT IN ('RETURNED')",
    ))["c"]
    transport_in_transit = one(run(
        conn, "SELECT COUNT(*) c FROM shipment_transport WHERE status='IN_TRANSIT'",
    ))["c"]
    unsettled = one(run(
        conn, "SELECT COUNT(*) c, COALESCE(SUM(amount),0) s FROM logistics_cost WHERE settled=0",
    ))
    open_claims = one(run(conn, "SELECT COUNT(*) c FROM logistics_claim WHERE status='OPEN'"))["c"]
    shipment_count = one(run(conn, "SELECT COUNT(*) c FROM shipment"))["c"]
    conn.close()
    return {
        "location_count": location_count,
        "container_active": container_active,
        "transport_in_transit": transport_in_transit,
        "unsettled_cost_count": unsettled["c"],
        "unsettled_cost_amount": unsettled["s"],
        "open_claim_count": open_claims,
        "shipment_count": shipment_count,
    }
