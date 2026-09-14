import json
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8000"


def get(path: str):
    with urllib.request.urlopen(BASE + path, timeout=30) as r:
        return r.status, json.loads(r.read().decode())


def post(path: str, body: dict):
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        BASE + path,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.status, json.loads(r.read().decode())


status, health = get("/health")
print("health", status, health)

status, login = post(
    "/api/auth/login",
    {"email": "admin@standard-erp.local", "password": "demo1234"},
)
print("login_status", status)
print("login_user", {k: login.get(k) for k in ("name", "email", "roles") if k in login or True})
# token fields vary; print keys only
print("login_keys", sorted(login.keys()))
assert "access_token" in login or "accessToken" in login, login
print("LOGIN_OK")
