import json
import urllib.request

req = urllib.request.Request(
    "http://127.0.0.1:8000/api/auth/login",
    data=json.dumps({"password": "ax2026h2"}).encode(),
    headers={"Content-Type": "application/json"},
    method="POST",
)
with urllib.request.urlopen(req, timeout=30) as r:
    data = json.loads(r.read().decode())
print("status", r.status)
print("user", data.get("user"))
print("has_tokens", "access_token" in data and "refresh_token" in data)

# wrong password
try:
    bad = urllib.request.Request(
        "http://127.0.0.1:8000/api/auth/login",
        data=json.dumps({"password": "wrong"}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    urllib.request.urlopen(bad, timeout=30)
    print("bad_password_unexpected_ok")
except urllib.error.HTTPError as e:
    print("bad_password_status", e.code)

root = urllib.request.urlopen("http://127.0.0.1:8000/", timeout=20).read().decode()
print("html_has_light", "index-" in root or "root" in root)
print("OK")
