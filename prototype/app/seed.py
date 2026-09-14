"""초기 데이터 적재.
prototype_dataset/ 폴더(CSV 17종)가 있으면 그 데이터를 임포트하고, 없으면 최소 데모 시드를
사용한다(신선한 클론 등 데이터셋 없이도 앱이 항상 뜰 수 있도록 하는 방어적 fallback).
init_db()로 스키마가 새로 생성된 직후에만 main.py에서 호출됨.
"""
import csv
from pathlib import Path

from .database import get_conn, run, insert_returning, one, rows_to_list
from .auth import hash_password

APP_DIR = Path(__file__).resolve().parent
DATASET_DIR = APP_DIR.parent / "prototype_dataset"


def _num(value, default=0.0):
    if value in (None, ""):
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _read_csv(name):
    path = DATASET_DIR / name
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _require_map(m, key, csv_name, id_field):
    if key not in m:
        raise ValueError(f"{csv_name}: '{key}' 에 해당하는 {id_field} 매핑을 찾을 수 없음 (참조 무결성 오류)")
    return m[key]


def _seed_common_mdm(conn):
    """데이터셋에 없는 항목(계정과목/역할/사용자)은 데모 시드와 동일하게 채운다."""
    gl_accounts = [
        ("1000", "현금", "ASSET"), ("1100", "매출채권", "ASSET"), ("1200", "재고자산", "ASSET"),
        ("2000", "매입채무", "LIAB"), ("4000", "매출", "REV"), ("5000", "매출원가", "EXP"),
    ]
    for code, name, atype in gl_accounts:
        run(conn, "INSERT INTO gl_account (code, name, account_type) VALUES (?,?,?)", (code, name, atype))
    roles = ["관리자", "영업담당", "구매담당", "생산담당"]
    for r in roles:
        run(conn, "INSERT INTO role (name) VALUES (?)", (r,))

    # 데모 계정 4종(역할당 1명). 비밀번호는 전부 데모용 고정값 — README 참고, 실운영 사용 금지.
    demo_users = [
        ("관리자", "admin@standard-erp.local", "관리자"),
        ("김영업", "sales@standard-erp.local", "영업담당"),
        ("박구매", "purchase@standard-erp.local", "구매담당"),
        ("이생산", "production@standard-erp.local", "생산담당"),
    ]
    DEMO_PASSWORD = "demo1234"
    for name, email, role_name in demo_users:
        role_id = roles.index(role_name) + 1
        user_id = insert_returning(
            conn, "INSERT INTO app_user (name, email, password_hash) VALUES (?,?,?)",
            (name, email, hash_password(DEMO_PASSWORD)), "user_id",
        )
        run(conn, "INSERT INTO user_role (user_id, role_id) VALUES (?, ?)", (user_id, role_id))

    # MES/WMS 웹훅 데모 API Key. 고정값이라 실제 운영 전환 시 반드시 교체할 것 — README 참고.
    demo_api_keys = [
        ("mes-demo-key-please-rotate", "MES", "MES 연동 데모 키"),
        ("wms-demo-key-please-rotate", "WMS", "WMS 연동 데모 키"),
    ]
    for api_key, source_system, label in demo_api_keys:
        run(conn, "INSERT INTO integration_api_key (api_key, source_system, label) VALUES (?,?,?)",
            (api_key, source_system, label))


def _import_dataset(conn):
    _seed_common_mdm(conn)

    company_map, plant_map, warehouse_map = {}, {}, {}
    customer_map, vendor_map, material_map = {}, {}, {}

    for row in _read_csv("companies.csv"):
        cid = insert_returning(conn, "INSERT INTO company (code, name) VALUES (?,?)",
                                (row["company_code"], row["company_name"]), "company_id")
        company_map[row["company_code"]] = cid

    for row in _read_csv("plants.csv"):
        pid = insert_returning(
            conn, "INSERT INTO plant (code, company_id, name) VALUES (?,?,?)",
            (row["plant_code"], _require_map(company_map, row["company_code"], "plants.csv", "company_id"),
             row["plant_name"]), "plant_id",
        )
        plant_map[row["plant_code"]] = pid

    for row in _read_csv("warehouses.csv"):
        wid = insert_returning(
            conn, "INSERT INTO warehouse (code, plant_id, name, warehouse_type) VALUES (?,?,?,?)",
            (row["warehouse_code"], _require_map(plant_map, row["plant_code"], "warehouses.csv", "plant_id"),
             row["warehouse_name"], row["warehouse_type"]), "warehouse_id",
        )
        warehouse_map[row["warehouse_code"]] = wid

    for row in _read_csv("customers.csv"):
        cid = insert_returning(
            conn, "INSERT INTO customer (code, name, credit_limit, currency, payment_term) VALUES (?,?,?,?,?)",
            (row["customer_code"], row["customer_name"], _num(row["credit_limit"]),
             row["currency"], row["payment_terms"]), "customer_id",
        )
        customer_map[row["customer_code"]] = cid

    for row in _read_csv("vendors.csv"):
        vid = insert_returning(
            conn, "INSERT INTO vendor (code, name, payment_term, lead_time_days) VALUES (?,?,?,?)",
            (row["vendor_code"], row["vendor_name"], row["payment_terms"], int(_num(row["lead_time_days"]))),
            "vendor_id",
        )
        vendor_map[row["vendor_code"]] = vid

    for row in _read_csv("materials.csv"):
        mid = insert_returning(
            conn, "INSERT INTO material (code, name, material_type, uom) VALUES (?,?,?,?)",
            (row["material_code"], row["material_name"], row["material_type"], row["base_uom"]), "material_id",
        )
        material_map[row["material_code"]] = mid

    for row in _read_csv("bom_items.csv"):
        run(
            conn, "INSERT INTO bom (parent_material_id, child_material_id, qty, version) VALUES (?,?,?,?)",
            (_require_map(material_map, row["parent_material"], "bom_items.csv", "material_id"),
             _require_map(material_map, row["component_material"], "bom_items.csv", "material_id"),
             _num(row["quantity"], 1), row["bom_code"]),
        )

    # 재고 스냅샷: 과거 거래를 재생하지 않고 현재 잔고의 소스오브트루스로 직접 적재.
    # 동시에 원자재 재발주점/목표재고를 안전재고/현재고 합계로부터 산출해 AI Buyer가 의미있게 동작하게 함.
    reorder_acc, target_acc = {}, {}
    for row in _read_csv("inventory_snapshot.csv"):
        material_id = _require_map(material_map, row["material_code"], "inventory_snapshot.csv", "material_id")
        warehouse_id = _require_map(warehouse_map, row["warehouse_code"], "inventory_snapshot.csv", "warehouse_id")
        qty = _num(row["on_hand_qty"])
        run(conn, "INSERT INTO inventory (material_id, warehouse_id, qty) VALUES (?,?,?)",
            (material_id, warehouse_id, qty))
        reorder_acc[material_id] = reorder_acc.get(material_id, 0) + _num(row["safety_stock_qty"])
        target_acc[material_id] = target_acc.get(material_id, 0) + qty
    for material_id, reorder_point in reorder_acc.items():
        run(conn, "UPDATE material SET reorder_point=?, target_stock=? WHERE material_id=?",
            (reorder_point, target_acc[material_id], material_id))

    so_map = {}
    for row in _read_csv("sales_orders.csv"):
        so_id = insert_returning(
            conn,
            "INSERT INTO sales_order (external_no, customer_id, order_date, currency, status) VALUES (?,?,?,?,?)",
            (row["sales_order_no"], _require_map(customer_map, row["customer_code"], "sales_orders.csv", "customer_id"),
             row["order_date"], row["currency"], row["status"]), "so_id",
        )
        run(conn, "INSERT INTO sales_order_line (so_id, material_id, qty, price) VALUES (?,?,?,?)",
            (so_id, _require_map(material_map, row["material_code"], "sales_orders.csv", "material_id"),
             _num(row["quantity"]), _num(row["unit_price"])))
        so_map[row["sales_order_no"]] = so_id

    for row in _read_csv("purchase_orders.csv"):
        po_id = insert_returning(
            conn,
            "INSERT INTO purchase_order (external_no, vendor_id, status, order_date, currency) VALUES (?,?,?,?,?)",
            (row["purchase_order_no"], _require_map(vendor_map, row["vendor_code"], "purchase_orders.csv", "vendor_id"),
             row["status"], row["order_date"], row["currency"]), "po_id",
        )
        run(conn, "INSERT INTO po_line (po_id, material_id, qty, price) VALUES (?,?,?,?)",
            (po_id, _require_map(material_map, row["material_code"], "purchase_orders.csv", "material_id"),
             _num(row["quantity"]), _num(row["unit_price"])))

    prod_order_map, prod_order_status = {}, {}
    for row in _read_csv("production_orders.csv"):
        prod_order_id = insert_returning(
            conn,
            "INSERT INTO production_order (external_no, material_id, plant_id, qty, status, order_date) "
            "VALUES (?,?,?,?,?,?)",
            (row["production_order_no"],
             _require_map(material_map, row["material_code"], "production_orders.csv", "material_id"),
             _require_map(plant_map, row["plant_code"], "production_orders.csv", "plant_id"),
             _num(row["planned_qty"]), row["status"], row["start_date"]), "prod_order_id",
        )
        prod_order_map[row["production_order_no"]] = prod_order_id
        prod_order_status[row["production_order_no"]] = row["status"]

    for row in _read_csv("production_results.csv"):
        po_no = row["production_order_no"]
        prod_order_id = _require_map(prod_order_map, po_no, "production_results.csv", "prod_order_id")
        wo_status = "DONE" if prod_order_status.get(po_no) == "COMPLETED" else "OPEN"
        work_order_id = insert_returning(
            conn, "INSERT INTO work_order (prod_order_id, routing_step, status) VALUES (?,?,?)",
            (prod_order_id, "IMPORTED", wo_status), "work_order_id",
        )
        run(
            conn,
            "INSERT INTO production_result "
            "(work_order_id, qty_good, qty_defect, result_date, oee, availability, performance, quality_rate) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (work_order_id, _num(row["good_qty"]), _num(row["defect_qty"]), row["result_date"],
             _num(row["oee"]), _num(row["availability"]), _num(row["performance"]), _num(row["quality_rate"])),
        )

    for row in _read_csv("quality_inspections.csv"):
        run(
            conn,
            "INSERT INTO quality_inspection (inspection_date, plant_id, material_id, inspection_type, "
            "sample_qty, defect_qty, defect_ppm, fp_yield, result, capa_required) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (row["inspection_date"], _require_map(plant_map, row["plant_code"], "quality_inspections.csv", "plant_id"),
             _require_map(material_map, row["material_code"], "quality_inspections.csv", "material_id"),
             row["inspection_type"], _num(row["sample_qty"]), _num(row["defect_qty"]), _num(row["defect_ppm"]),
             _num(row["fp_yield"]), row["result"], row["capa_required"]),
        )

    for row in _read_csv("shipments.csv"):
        run(
            conn,
            "INSERT INTO shipment (external_no, so_id, shipment_date, customer_id, material_id, shipped_qty, "
            "carrier, otd_flag, status) VALUES (?,?,?,?,?,?,?,?,?)",
            (row["shipment_no"], so_map.get(row["sales_order_no"]), row["shipment_date"],
             _require_map(customer_map, row["customer_code"], "shipments.csv", "customer_id"),
             _require_map(material_map, row["material_code"], "shipments.csv", "material_id"),
             _num(row["shipped_qty"]), row["carrier"], row["otd_flag"], row["status"]),
        )

    for row in _read_csv("demand_forecast.csv"):
        run(
            conn,
            "INSERT INTO demand_forecast (forecast_month, material_id, company_id, forecast_qty, "
            "actual_sales_qty, mape, forecast_version) VALUES (?,?,?,?,?,?,?)",
            (row["forecast_month"], _require_map(material_map, row["material_code"], "demand_forecast.csv", "material_id"),
             company_map.get(row["company_code"]), _num(row["forecast_qty"]), _num(row["actual_sales_qty"]),
             _num(row["mape"]), row["forecast_version"]),
        )

    for row in _read_csv("finance_summary.csv"):
        run(
            conn,
            "INSERT INTO finance_summary_monthly (period, revenue, cogs, gross_profit, opex, operating_profit, "
            "ebitda, cash_flow, currency) VALUES (?,?,?,?,?,?,?,?,?)",
            (row["period"], _num(row["revenue"]), _num(row["cogs"]), _num(row["gross_profit"]), _num(row["opex"]),
             _num(row["operating_profit"]), _num(row["ebitda"]), _num(row["cash_flow"]), row["currency"]),
        )

    for row in _read_csv("kpi_monthly.csv"):
        run(
            conn,
            "INSERT INTO kpi_monthly (period, revenue, operating_profit, oee_avg, otd_rate, ppm_avg, "
            "inventory_turnover, forecast_accuracy, supply_risk_count, ai_recommendation_adoption_rate) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (row["period"], _num(row["revenue"]), _num(row["operating_profit"]), _num(row["oee_avg"]),
             _num(row["otd_rate"]), _num(row["ppm_avg"]), _num(row["inventory_turnover"]),
             _num(row["forecast_accuracy"]), int(_num(row["supply_risk_count"])),
             _num(row["ai_recommendation_adoption_rate"])),
        )

    for row in _read_csv("ai_recommendations.csv"):
        run(
            conn,
            "INSERT INTO ai_recommendation_log (recommendation_id, agent, created_at, title, summary, "
            "confidence, impact, status, target_module) VALUES (?,?,?,?,?,?,?,?,?)",
            (row["recommendation_id"], row["agent"], row["created_at"], row["title"], row["summary"],
             _num(row["confidence"]), row["impact"], row["status"], row["target_module"]),
        )


def _seed_demo(conn):
    """prototype_dataset/이 없을 때의 최소 데모 시드 (v1 원본과 동일)."""
    _seed_common_mdm(conn)

    company_id = insert_returning(conn, "INSERT INTO company (name) VALUES ('Standard Corp')", (), "company_id")
    plant_id = insert_returning(
        conn, "INSERT INTO plant (company_id, name) VALUES (?, '본사공장')", (company_id,), "plant_id"
    )
    wh_raw = insert_returning(
        conn, "INSERT INTO warehouse (plant_id, name, warehouse_type) VALUES (?, '원자재창고', 'RM')",
        (plant_id,), "warehouse_id",
    )
    wh_fg = insert_returning(
        conn, "INSERT INTO warehouse (plant_id, name, warehouse_type) VALUES (?, '완제품창고', 'FG')",
        (plant_id,), "warehouse_id",
    )

    materials = [
        ("RM-001", "원자재A", "RM", "KG", 30, 150),
        ("RM-002", "원자재B", "RM", "KG", 20, 120),
        ("FG-001", "완제품A", "FG", "EA", 0, 0),
    ]
    mat_ids = {}
    for code, name, mtype, uom, reorder_point, target_stock in materials:
        mat_ids[code] = insert_returning(
            conn,
            "INSERT INTO material (code, name, material_type, uom, plant_id, reorder_point, target_stock) "
            "VALUES (?,?,?,?,?,?,?)",
            (code, name, mtype, uom, plant_id, reorder_point, target_stock),
            "material_id",
        )

    run(conn, "INSERT INTO bom (parent_material_id, child_material_id, qty) VALUES (?,?,2)",
        (mat_ids["FG-001"], mat_ids["RM-001"]))
    run(conn, "INSERT INTO bom (parent_material_id, child_material_id, qty) VALUES (?,?,1)",
        (mat_ids["FG-001"], mat_ids["RM-002"]))

    run(conn, "INSERT INTO inventory (material_id, warehouse_id, qty) VALUES (?,?,100)", (mat_ids["RM-001"], wh_raw))
    run(conn, "INSERT INTO inventory (material_id, warehouse_id, qty) VALUES (?,?,100)", (mat_ids["RM-002"], wh_raw))
    run(conn, "INSERT INTO inventory (material_id, warehouse_id, qty) VALUES (?,?,0)", (mat_ids["FG-001"], wh_fg))

    for c in ["고객사A", "고객사B"]:
        run(conn, "INSERT INTO customer (name) VALUES (?)", (c,))
    for v in ["공급사A", "공급사B"]:
        run(conn, "INSERT INTO vendor (name) VALUES (?)", (v,))


def run_seed():
    conn = get_conn()
    if one(run(conn, "SELECT COUNT(*) c FROM company"))["c"] > 0:
        conn.close()
        return

    if DATASET_DIR.exists() and (DATASET_DIR / "companies.csv").exists():
        _import_dataset(conn)
    else:
        _seed_demo(conn)

    conn.commit()
    conn.close()
