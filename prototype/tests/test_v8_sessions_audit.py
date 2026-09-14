"""v8: audit_log 연결, 대시보드 LOT 정합성 KPI, 디바이스별 세션 조회/개별 로그아웃 검증."""


def _fresh_login(client, email="sales@standard-erp.local", user_agent=None):
    headers = {"User-Agent": user_agent} if user_agent else {}
    r = client.post("/api/auth/login", json={"email": email, "password": "demo1234"}, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


# ---------- audit_log ----------

def test_serial_status_change_writes_audit_log(client, tokens, fg_lot_with_serials):
    serial_no = fg_lot_with_serials["serials"][3]
    r = client.post(
        f"/api/serials/{serial_no}/status", json={"status": "SCRAPPED"}, headers=tokens["production"],
    )
    assert r.status_code == 200

    log = client.get("/api/audit-log", headers=tokens["admin"])
    assert log.status_code == 200
    entries = [e for e in log.json() if e["entity"] == "serial_number" and "SCRAPPED" in e["action"]]
    assert entries, "시리얼 상태변경 감사 로그가 남아야 함"


def test_audit_log_requires_admin(client, tokens):
    r = client.get("/api/audit-log", headers=tokens["sales"])
    assert r.status_code == 403


def test_refresh_reuse_writes_audit_log(client):
    tokens_body = _fresh_login(client)
    old_refresh = tokens_body["refresh_token"]
    rotated = client.post("/api/auth/refresh", json={"refresh_token": old_refresh})
    assert rotated.status_code == 200

    reuse = client.post("/api/auth/refresh", json={"refresh_token": old_refresh})
    assert reuse.status_code == 401

    # audit-log 조회는 관리자 계정으로 로그인해서 확인
    admin = _fresh_login(client, "admin@standard-erp.local")
    admin_headers = {"Authorization": f"Bearer {admin['access_token']}"}
    log = client.get("/api/audit-log", headers=admin_headers)
    entries = [e for e in log.json() if e["action"] == "REFRESH_TOKEN_REUSE_DETECTED"]
    assert entries


# ---------- 대시보드 LOT 정합성 KPI ----------

def test_dashboard_kpi_includes_lot_inconsistent_count(client, tokens):
    r = client.get("/api/dashboard/kpi", headers=tokens["admin"])
    assert r.status_code == 200
    assert "lot_inconsistent_count" in r.json()
    assert isinstance(r.json()["lot_inconsistent_count"], int)


# ---------- 디바이스별 세션 조회/개별 로그아웃 ----------

def test_login_records_user_agent_in_sessions(client):
    tokens_body = _fresh_login(client, user_agent="pytest-agent/1.0")
    headers = {"Authorization": f"Bearer {tokens_body['access_token']}"}
    r = client.get("/api/auth/sessions", headers=headers)
    assert r.status_code == 200
    assert any(s["user_agent"] == "pytest-agent/1.0" for s in r.json())


def test_logout_own_session_by_family_id(client):
    tokens_body = _fresh_login(client, user_agent="device-a")
    headers = {"Authorization": f"Bearer {tokens_body['access_token']}"}
    sessions = client.get("/api/auth/sessions", headers=headers).json()
    family_id = next(s["family_id"] for s in sessions if s["user_agent"] == "device-a")

    r = client.post(f"/api/auth/sessions/{family_id}/logout", headers=headers)
    assert r.status_code == 200

    # 로그아웃된 세션의 refresh_token은 더 이상 재발급에 쓸 수 없어야 함
    refresh_again = client.post("/api/auth/refresh", json={"refresh_token": tokens_body["refresh_token"]})
    assert refresh_again.status_code == 401


def test_cannot_logout_other_users_session(client):
    victim = _fresh_login(client, "sales@standard-erp.local", user_agent="victim-device")
    victim_headers = {"Authorization": f"Bearer {victim['access_token']}"}
    sessions = client.get("/api/auth/sessions", headers=victim_headers).json()
    family_id = next(s["family_id"] for s in sessions if s["user_agent"] == "victim-device")

    attacker = _fresh_login(client, "purchase@standard-erp.local")
    attacker_headers = {"Authorization": f"Bearer {attacker['access_token']}"}

    r = client.post(f"/api/auth/sessions/{family_id}/logout", headers=attacker_headers)
    assert r.status_code == 404

    # 공격 시도가 실패했으므로 피해자의 refresh_token은 여전히 유효해야 함
    still_ok = client.post("/api/auth/refresh", json={"refresh_token": victim["refresh_token"]})
    assert still_ok.status_code == 200
