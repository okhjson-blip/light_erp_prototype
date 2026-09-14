def test_health_ok(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert r.json()["db"] == "ok"


def test_health_no_auth_required(client):
    """헬스체크는 GET 인증 확장(v4) 대상에서 제외 — 인프라 프로브가 로그인 없이 호출 가능해야 함."""
    r = client.get("/health")
    assert r.status_code != 401


def test_index_static_no_auth_required(client):
    r = client.get("/")
    assert r.status_code == 200
