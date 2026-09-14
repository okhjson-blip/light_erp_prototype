def test_login_success(client):
    r = client.post("/api/auth/login", json={"email": "admin@standard-erp.local", "password": "demo1234"})
    assert r.status_code == 200
    body = r.json()
    assert "access_token" in body
    assert "refresh_token" in body


def test_login_wrong_password(client):
    r = client.post("/api/auth/login", json={"email": "admin@standard-erp.local", "password": "wrong"})
    assert r.status_code == 401


def test_get_without_token_401(client):
    r = client.get("/api/materials")
    assert r.status_code == 401


def test_get_with_token_any_role_ok(client, tokens):
    r = client.get("/api/materials", headers=tokens["sales"])
    assert r.status_code == 200


def test_post_without_token_401(client):
    r = client.post("/api/purchase-requisitions", json={"lines": []})
    assert r.status_code == 401


def test_post_wrong_role_403(client, tokens):
    """구매 신청은 구매담당 권한이 필요 — 영업담당 토큰으로는 403."""
    r = client.post(
        "/api/purchase-requisitions",
        json={"lines": [{"material_id": 6, "qty": 1}]},
        headers=tokens["sales"],
    )
    assert r.status_code == 403


def test_static_root_no_auth_required(client):
    r = client.get("/")
    assert r.status_code == 200


# ---------- v5: 회계/CFO Copilot 조회 관리자 전용 제한 ----------

def test_accounting_documents_forbidden_for_non_admin(client, tokens):
    r = client.get("/api/accounting/documents", headers=tokens["sales"])
    assert r.status_code == 403


def test_accounting_documents_ok_for_admin(client, tokens):
    r = client.get("/api/accounting/documents", headers=tokens["admin"])
    assert r.status_code == 200


def test_gl_accounts_forbidden_for_non_admin(client, tokens):
    r = client.get("/api/gl-accounts", headers=tokens["purchase"])
    assert r.status_code == 403


def test_gl_accounts_ok_for_admin(client, tokens):
    r = client.get("/api/gl-accounts", headers=tokens["admin"])
    assert r.status_code == 200


def test_cfo_copilot_forbidden_for_non_admin(client, tokens):
    r = client.get("/api/ai/cfo-copilot/insights", headers=tokens["production"])
    assert r.status_code == 403
