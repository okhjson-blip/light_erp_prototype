"""v14: 06 Quality Management 확장 — 검사기준/검사구분필터/SPC/부적합/8D/고객클레임/CAPA/품질Dashboard."""

RM_MATERIAL_ID = 6
CUSTOMER_ID = 1


# ---------- 검사기준 ----------

def test_standard_create_and_list(client, tokens):
    r = client.post(
        "/api/quality/standards",
        json={"material_id": RM_MATERIAL_ID, "inspection_type": "INCOMING",
              "item_name": "불량 PPM", "spec_lsl": 0, "spec_usl": 60000, "unit": "ppm"},
        headers=tokens["production"],
    )
    assert r.status_code == 200
    rows = client.get("/api/quality/standards", headers=tokens["sales"]).json()
    row = next(s for s in rows if s["standard_id"] == r.json()["standard_id"])
    assert row["material_name"]
    assert row["spec_usl"] == 60000


def test_standard_invalid_type_400(client, tokens):
    r = client.post(
        "/api/quality/standards",
        json={"material_id": RM_MATERIAL_ID, "inspection_type": "RANDOM", "item_name": "외관"},
        headers=tokens["production"],
    )
    assert r.status_code == 400


def test_standard_write_requires_role(client, tokens):
    r = client.post(
        "/api/quality/standards",
        json={"material_id": RM_MATERIAL_ID, "inspection_type": "FINAL", "item_name": "외관"},
        headers=tokens["sales"],
    )
    assert r.status_code == 403


# ---------- 검사이력 필터 ----------

def test_inspections_filter_by_type(client, tokens):
    all_rows = client.get("/api/quality/inspections", headers=tokens["admin"]).json()
    assert len(all_rows) > 0  # 데이터셋 180건
    types = {r["inspection_type"] for r in all_rows if r["inspection_type"]}
    assert types, "데이터셋에 검사구분이 있어야 함"
    t = next(iter(types))
    filtered = client.get(f"/api/quality/inspections?inspection_type={t}", headers=tokens["admin"]).json()
    assert len(filtered) > 0
    assert all(r["inspection_type"] == t for r in filtered)


# ---------- SPC ----------

def test_spc_stats_and_cpk_with_standard(client, tokens):
    # 데이터셋 검사이력이 실제로 있는 품목을 동적으로 선택(RM에는 검사 데이터가 없음)
    inspections = client.get("/api/quality/inspections", headers=tokens["admin"]).json()
    with_ppm = [i for i in inspections if i["defect_ppm"] is not None]
    assert len(with_ppm) >= 2
    material_id = with_ppm[0]["material_id"]
    # 해당 품목에 LSL/USL 검사기준 등록 → Cp/Cpk 계산 가능
    assert client.post(
        "/api/quality/standards",
        json={"material_id": material_id, "inspection_type": "FINAL",
              "item_name": "불량 PPM", "spec_lsl": 0, "spec_usl": 60000, "unit": "ppm"},
        headers=tokens["production"],
    ).status_code == 200

    body = client.get(f"/api/quality/spc/{material_id}", headers=tokens["production"]).json()
    assert body["sample_count"] >= 2
    assert body["mean"] is not None
    assert body["ucl"] > body["mean"]
    assert body["lcl"] >= 0
    assert body["cp"] is not None
    assert body["cpk"] is not None
    assert len(body["points"]) <= 50


def test_spc_unknown_material_404(client, tokens):
    assert client.get("/api/quality/spc/999999", headers=tokens["admin"]).status_code == 404


# ---------- 부적합 ----------

def test_nonconformance_shape(client, tokens):
    body = client.get("/api/quality/nonconformance", headers=tokens["admin"]).json()
    assert "defective_serials" in body
    assert "fail_inspections" in body


# ---------- 8D ----------

def test_eight_d_create_and_close(client, tokens):
    r = client.post(
        "/api/quality/eight-d",
        json={"title": "PCB 납땜 불량 재발", "material_id": RM_MATERIAL_ID,
              "problem": "리플로우 온도 편차", "root_cause": "프로파일 미최적화",
              "corrective_action": "온도 프로파일 재설정"},
        headers=tokens["production"],
    )
    assert r.status_code == 200
    report_id = r.json()["report_id"]
    assert client.post(
        f"/api/quality/eight-d/{report_id}/status", json={"status": "CLOSED"}, headers=tokens["production"],
    ).status_code == 200
    rows = client.get("/api/quality/eight-d", headers=tokens["admin"]).json()
    row = next(x for x in rows if x["report_id"] == report_id)
    assert row["status"] == "CLOSED"
    assert row["closed_date"] is not None


# ---------- 고객클레임 ----------

def test_claim_create_by_sales_and_resolve(client, tokens):
    r = client.post(
        "/api/quality/claims",
        json={"customer_id": CUSTOMER_ID, "claim_type": "QUALITY", "description": "표면 스크래치", "qty": 3},
        headers=tokens["sales"],  # 고객 접점 — 영업담당도 등록 가능
    )
    assert r.status_code == 200
    claim_id = r.json()["claim_id"]
    # 상태 변경은 생산담당/관리자만
    assert client.post(
        f"/api/quality/claims/{claim_id}/status", json={"status": "RESOLVED"}, headers=tokens["sales"],
    ).status_code == 403
    assert client.post(
        f"/api/quality/claims/{claim_id}/status", json={"status": "RESOLVED"}, headers=tokens["production"],
    ).status_code == 200
    rows = client.get("/api/quality/claims", headers=tokens["admin"]).json()
    row = next(c for c in rows if c["claim_id"] == claim_id)
    assert row["status"] == "RESOLVED"
    assert row["resolved_date"] is not None


def test_claim_unknown_customer_404(client, tokens):
    r = client.post("/api/quality/claims", json={"customer_id": 999999}, headers=tokens["sales"])
    assert r.status_code == 404


# ---------- CAPA ----------

def test_capa_candidates_and_link_flow(client, tokens):
    before = client.get("/api/quality/capa", headers=tokens["admin"]).json()
    assert len(before["candidates"]) > 0  # 데이터셋 capa_required='Y' 검사 존재
    target = before["candidates"][0]

    r = client.post(
        "/api/quality/capa",
        json={"title": "공정 온도 관리 강화", "inspection_id": target["inspection_id"],
              "action_type": "CORRECTIVE", "due_date": "2026-08-31"},
        headers=tokens["production"],
    )
    assert r.status_code == 200
    capa_id = r.json()["capa_id"]

    # 연결된 검사는 후보 목록에서 빠짐
    after = client.get("/api/quality/capa", headers=tokens["admin"]).json()
    assert all(c["inspection_id"] != target["inspection_id"] for c in after["candidates"])

    done = client.post(
        f"/api/quality/capa/{capa_id}/status", json={"status": "DONE"}, headers=tokens["production"],
    )
    assert done.status_code == 200
    row = next(a for a in after["actions"] if a["capa_id"] == capa_id)
    assert row["status"] == "OPEN"  # after는 DONE 처리 전 조회본
    final = client.get("/api/quality/capa", headers=tokens["admin"]).json()
    assert next(a for a in final["actions"] if a["capa_id"] == capa_id)["completed_date"] is not None


def test_capa_invalid_type_400(client, tokens):
    assert client.post(
        "/api/quality/capa", json={"title": "x", "action_type": "MAGIC"}, headers=tokens["production"],
    ).status_code == 400


# ---------- Dashboard / 인증 ----------

def test_quality_dashboard_shape(client, tokens):
    d = client.get("/api/quality/dashboard", headers=tokens["purchase"]).json()
    for key in (
        "inspection_count", "avg_defect_ppm", "fail_count", "defective_serial_count",
        "open_capa_count", "capa_candidate_count", "open_claim_count", "open_8d_count", "standard_count",
    ):
        assert key in d
    assert d["inspection_count"] > 0


def test_quality_ext_requires_login(client):
    assert client.get("/api/quality/dashboard").status_code == 401
