"""실행 중인 ERP 서버에 가짜 MES/WMS 이벤트를 전송하는 시뮬레이터.
실제 MES/WMS 시스템이 준비되면 이 스크립트 대신 그 시스템이 동일한 엔드포인트로
Webhook을 호출하면 된다 (엔드포인트/페이로드 계약은 app/integrations.py 참고).

사용법:
    uvicorn app.main:app --reload  (다른 터미널에서 서버 기동)
    python3 simulate_mes_wms.py
"""
import sys
import urllib.request
import json

BASE_URL = "http://127.0.0.1:8000"

# MES/WMS 웹훅 데모 API Key (app/seed.py에서 시드됨). 실제 운영 전환 시 반드시 교체할 것 — README 참고.
MES_API_KEY = "mes-demo-key-please-rotate"
WMS_API_KEY = "wms-demo-key-please-rotate"


def call(method, path, payload=None, headers=None):
    url = BASE_URL + path
    data = json.dumps(payload).encode() if payload is not None else None
    req_headers = {"Content-Type": "application/json"}
    req_headers.update(headers or {})
    req = urllib.request.Request(url, data=data, method=method, headers=req_headers)
    try:
        with urllib.request.urlopen(req) as res:
            return res.status, json.loads(res.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def main():
    print("=== 0) 생산담당 데모 계정 로그인 (RBAC — 생산오더/작업지시 생성에 필요) ===")
    status, session = call("POST", "/api/auth/login",
                            {"email": "production@standard-erp.local", "password": "demo1234"})
    if status != 200:
        print("로그인 실패:", status, session, "-- 서버가 최신 스키마로 기동되었는지 확인하세요.")
        return
    auth_headers = {"Authorization": f"Bearer {session['access_token']}"}

    print("\n=== 1) 생산오더/작업지시 준비 (WMS/MES 이벤트 대상) ===")
    # v3부터 GET 엔드포인트도 로그인이 필요하다 — 조회에도 auth_headers를 실어 보낸다.
    materials = call("GET", "/api/materials", headers=auth_headers)[1]
    plants = call("GET", "/api/plants", headers=auth_headers)[1]
    warehouses = call("GET", "/api/warehouses", headers=auth_headers)[1]
    fg = next(m for m in materials if m["material_type"] == "FG")
    wh_fg = next(w for w in warehouses if w["warehouse_type"] == "FG")

    status, prod = call("POST", "/api/production-orders",
                         {"material_id": fg["material_id"], "plant_id": plants[0]["plant_id"], "qty": 3},
                         headers=auth_headers)
    print("생산오더 생성:", status, prod)
    status, wo = call("POST", f"/api/production-orders/{prod['prod_order_id']}/work-orders", {},
                       headers=auth_headers)
    print("작업지시 생성:", status, wo)

    print("\n=== 2) MES → ERP: 생산실적 Webhook 전송 (X-API-Key 인증) ===")
    status, res = call("POST", "/api/integrations/mes/production-result", {
        "work_order_id": wo["work_order_id"], "qty_good": 3, "qty_defect": 0,
        "warehouse_id": wh_fg["warehouse_id"],
    }, headers={"X-API-Key": MES_API_KEY})
    print("MES 이벤트 결과:", status, res)

    print("\n=== 3) WMS → ERP: 입고 Webhook 전송 (원자재 긴급 입고 가정, X-API-Key 인증) ===")
    rm = next(m for m in materials if m["material_type"] == "RM")
    wh_raw = next(w for w in warehouses if w["warehouse_type"] == "RM")
    status, res = call("POST", "/api/integrations/wms/inventory-movement", {
        "material_code": rm["code"], "warehouse_name": wh_raw["name"],
        "movement_type": "IN", "qty": 50, "ref": "WMS-EMERGENCY-INBOUND-001",
    }, headers={"X-API-Key": WMS_API_KEY})
    print("WMS 이벤트 결과:", status, res)

    print("\n=== 4) 연동 이벤트 로그 확인 ===")
    status, events = call("GET", "/api/integrations/events", headers=auth_headers)
    for e in events[:5]:
        print(f"  [{e['event_id']}] {e['source_system']}/{e['event_type']} -> {e['status']}")

    print("\n완료. ERP 화면의 '연동 로그' 탭에서도 동일 이벤트를 확인할 수 있습니다.")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        BASE_URL = sys.argv[1]
    main()
