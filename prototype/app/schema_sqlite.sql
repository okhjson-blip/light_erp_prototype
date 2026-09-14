PRAGMA foreign_keys = ON;

-- ===== 01. MDM (기준정보) =====
CREATE TABLE company (
  company_id INTEGER PRIMARY KEY AUTOINCREMENT,
  code TEXT UNIQUE,
  name TEXT NOT NULL
);

CREATE TABLE plant (
  plant_id INTEGER PRIMARY KEY AUTOINCREMENT,
  code TEXT UNIQUE,
  company_id INTEGER NOT NULL REFERENCES company(company_id),
  name TEXT NOT NULL
);

CREATE TABLE warehouse (
  warehouse_id INTEGER PRIMARY KEY AUTOINCREMENT,
  code TEXT UNIQUE,
  plant_id INTEGER NOT NULL REFERENCES plant(plant_id),
  name TEXT NOT NULL,
  warehouse_type TEXT NOT NULL DEFAULT 'FG'
);

CREATE TABLE material (
  material_id INTEGER PRIMARY KEY AUTOINCREMENT,
  code TEXT UNIQUE NOT NULL,
  name TEXT NOT NULL,
  material_type TEXT NOT NULL DEFAULT 'FG',
  uom TEXT NOT NULL DEFAULT 'EA',
  plant_id INTEGER REFERENCES plant(plant_id),
  reorder_point REAL NOT NULL DEFAULT 0,
  target_stock REAL NOT NULL DEFAULT 0
);

CREATE TABLE bom (
  bom_id INTEGER PRIMARY KEY AUTOINCREMENT,
  parent_material_id INTEGER NOT NULL REFERENCES material(material_id),
  child_material_id INTEGER NOT NULL REFERENCES material(material_id),
  qty REAL NOT NULL DEFAULT 1,
  version TEXT NOT NULL DEFAULT 'v1'
);

CREATE TABLE customer (
  customer_id INTEGER PRIMARY KEY AUTOINCREMENT,
  code TEXT UNIQUE,
  name TEXT NOT NULL,
  credit_limit REAL DEFAULT 0,
  currency TEXT DEFAULT 'KRW',
  payment_term TEXT DEFAULT 'NET30'
);

CREATE TABLE vendor (
  vendor_id INTEGER PRIMARY KEY AUTOINCREMENT,
  code TEXT UNIQUE,
  name TEXT NOT NULL,
  payment_term TEXT DEFAULT 'NET30',
  lead_time_days INTEGER DEFAULT 7
);

CREATE TABLE gl_account (
  account_id INTEGER PRIMARY KEY AUTOINCREMENT,
  code TEXT UNIQUE NOT NULL,
  name TEXT NOT NULL,
  account_type TEXT NOT NULL
);

CREATE TABLE app_user (
  user_id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  email TEXT UNIQUE NOT NULL,
  password_hash TEXT
);

CREATE TABLE role (
  role_id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT UNIQUE NOT NULL
);

CREATE TABLE user_role (
  user_id INTEGER NOT NULL REFERENCES app_user(user_id),
  role_id INTEGER NOT NULL REFERENCES role(role_id),
  PRIMARY KEY (user_id, role_id)
);

CREATE TABLE session (
  token TEXT PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES app_user(user_id),
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  expires_at TEXT NOT NULL
);

-- ===== 02. Sales (영업) =====
CREATE TABLE sales_order (
  so_id INTEGER PRIMARY KEY AUTOINCREMENT,
  external_no TEXT UNIQUE,
  customer_id INTEGER NOT NULL REFERENCES customer(customer_id),
  order_date TEXT NOT NULL DEFAULT (date('now')),
  currency TEXT NOT NULL DEFAULT 'KRW',
  status TEXT NOT NULL DEFAULT 'OPEN'
);

CREATE TABLE sales_order_line (
  so_line_id INTEGER PRIMARY KEY AUTOINCREMENT,
  so_id INTEGER NOT NULL REFERENCES sales_order(so_id),
  material_id INTEGER NOT NULL REFERENCES material(material_id),
  qty REAL NOT NULL,
  price REAL NOT NULL DEFAULT 0
);

CREATE TABLE delivery (
  delivery_id INTEGER PRIMARY KEY AUTOINCREMENT,
  so_id INTEGER NOT NULL REFERENCES sales_order(so_id),
  warehouse_id INTEGER NOT NULL REFERENCES warehouse(warehouse_id),
  ship_date TEXT NOT NULL DEFAULT (date('now'))
);

CREATE TABLE sales_invoice (
  invoice_id INTEGER PRIMARY KEY AUTOINCREMENT,
  so_id INTEGER NOT NULL REFERENCES sales_order(so_id),
  customer_id INTEGER NOT NULL REFERENCES customer(customer_id),
  amount REAL NOT NULL DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'OPEN',
  invoice_date TEXT NOT NULL DEFAULT (date('now'))
);

-- ===== 03. Procurement (구매) =====
CREATE TABLE purchase_requisition (
  pr_id INTEGER PRIMARY KEY AUTOINCREMENT,
  requester_id INTEGER REFERENCES app_user(user_id),
  status TEXT NOT NULL DEFAULT 'OPEN',
  created_date TEXT NOT NULL DEFAULT (date('now'))
);

CREATE TABLE pr_line (
  pr_line_id INTEGER PRIMARY KEY AUTOINCREMENT,
  pr_id INTEGER NOT NULL REFERENCES purchase_requisition(pr_id),
  material_id INTEGER NOT NULL REFERENCES material(material_id),
  qty REAL NOT NULL
);

CREATE TABLE purchase_order (
  po_id INTEGER PRIMARY KEY AUTOINCREMENT,
  external_no TEXT UNIQUE,
  vendor_id INTEGER NOT NULL REFERENCES vendor(vendor_id),
  pr_id INTEGER REFERENCES purchase_requisition(pr_id),
  status TEXT NOT NULL DEFAULT 'OPEN',
  order_date TEXT NOT NULL DEFAULT (date('now')),
  currency TEXT NOT NULL DEFAULT 'KRW'
);

CREATE TABLE po_line (
  po_line_id INTEGER PRIMARY KEY AUTOINCREMENT,
  po_id INTEGER NOT NULL REFERENCES purchase_order(po_id),
  material_id INTEGER NOT NULL REFERENCES material(material_id),
  qty REAL NOT NULL,
  price REAL NOT NULL DEFAULT 0
);

CREATE TABLE goods_receipt (
  gr_id INTEGER PRIMARY KEY AUTOINCREMENT,
  po_line_id INTEGER NOT NULL REFERENCES po_line(po_line_id),
  warehouse_id INTEGER NOT NULL REFERENCES warehouse(warehouse_id),
  qty REAL NOT NULL,
  received_date TEXT NOT NULL DEFAULT (date('now'))
);

CREATE TABLE ap_invoice (
  ap_id INTEGER PRIMARY KEY AUTOINCREMENT,
  vendor_id INTEGER NOT NULL REFERENCES vendor(vendor_id),
  po_id INTEGER REFERENCES purchase_order(po_id),
  amount REAL NOT NULL DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'OPEN',
  invoice_date TEXT NOT NULL DEFAULT (date('now'))
);

-- ===== 04. Production (생산, 단순화) =====
CREATE TABLE production_order (
  prod_order_id INTEGER PRIMARY KEY AUTOINCREMENT,
  external_no TEXT UNIQUE,
  material_id INTEGER NOT NULL REFERENCES material(material_id),
  plant_id INTEGER NOT NULL REFERENCES plant(plant_id),
  qty REAL NOT NULL,
  status TEXT NOT NULL DEFAULT 'PLANNED',
  order_date TEXT NOT NULL DEFAULT (date('now'))
);

CREATE TABLE work_order (
  work_order_id INTEGER PRIMARY KEY AUTOINCREMENT,
  prod_order_id INTEGER NOT NULL REFERENCES production_order(prod_order_id),
  routing_step TEXT NOT NULL DEFAULT 'ASSEMBLY',
  status TEXT NOT NULL DEFAULT 'OPEN'
);

CREATE TABLE production_result (
  result_id INTEGER PRIMARY KEY AUTOINCREMENT,
  work_order_id INTEGER NOT NULL REFERENCES work_order(work_order_id),
  qty_good REAL NOT NULL DEFAULT 0,
  qty_defect REAL NOT NULL DEFAULT 0,
  result_date TEXT NOT NULL DEFAULT (date('now')),
  oee REAL,
  availability REAL,
  performance REAL,
  quality_rate REAL
);

-- ===== 05. Inventory (재고) =====
CREATE TABLE inventory (
  inventory_id INTEGER PRIMARY KEY AUTOINCREMENT,
  material_id INTEGER NOT NULL REFERENCES material(material_id),
  warehouse_id INTEGER NOT NULL REFERENCES warehouse(warehouse_id),
  qty REAL NOT NULL DEFAULT 0,
  UNIQUE(material_id, warehouse_id)
);

CREATE TABLE inventory_transaction (
  txn_id INTEGER PRIMARY KEY AUTOINCREMENT,
  material_id INTEGER NOT NULL REFERENCES material(material_id),
  warehouse_id INTEGER NOT NULL REFERENCES warehouse(warehouse_id),
  txn_type TEXT NOT NULL,
  qty REAL NOT NULL,
  ref_doc_type TEXT,
  ref_doc_id INTEGER,
  txn_date TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ===== 06. FI (회계 기본) =====
CREATE TABLE accounting_document (
  doc_id INTEGER PRIMARY KEY AUTOINCREMENT,
  doc_type TEXT NOT NULL,
  posting_date TEXT NOT NULL DEFAULT (date('now')),
  status TEXT NOT NULL DEFAULT 'POSTED',
  description TEXT
);

CREATE TABLE accounting_line (
  line_id INTEGER PRIMARY KEY AUTOINCREMENT,
  doc_id INTEGER NOT NULL REFERENCES accounting_document(doc_id),
  account_id INTEGER NOT NULL REFERENCES gl_account(account_id),
  debit REAL NOT NULL DEFAULT 0,
  credit REAL NOT NULL DEFAULT 0
);

-- ===== 07. Common (승인/감사) =====
CREATE TABLE approval_workflow (
  workflow_id INTEGER PRIMARY KEY AUTOINCREMENT,
  doc_type TEXT NOT NULL,
  doc_id INTEGER NOT NULL,
  status TEXT NOT NULL DEFAULT 'PENDING',
  current_step TEXT DEFAULT 'MANAGER',
  created_date TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE audit_log (
  log_id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER REFERENCES app_user(user_id),
  action TEXT NOT NULL,
  entity TEXT NOT NULL,
  entity_id INTEGER,
  ts TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ===== 08. Integration (MES/WMS 연계, v2) =====
CREATE TABLE integration_event_log (
  event_id INTEGER PRIMARY KEY AUTOINCREMENT,
  source_system TEXT NOT NULL,
  event_type TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'PROCESSED',
  received_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ===== 08b. WMS/QMS LOT·Serial 추적 (v3) =====
-- 기존 inventory(집계) 테이블은 그대로 두고, LOT은 병행 기록되는 별도 레이어다.
-- 과거 임포트 재고는 LOT이 없으므로 소급 생성하지 않는다(task-plan-lot-serial.md 참고).
CREATE TABLE lot (
  lot_id INTEGER PRIMARY KEY AUTOINCREMENT,
  lot_no TEXT UNIQUE NOT NULL,
  material_id INTEGER NOT NULL REFERENCES material(material_id),
  warehouse_id INTEGER NOT NULL REFERENCES warehouse(warehouse_id),
  qty REAL NOT NULL DEFAULT 0,
  source_type TEXT NOT NULL,
  source_ref_id INTEGER,
  status TEXT NOT NULL DEFAULT 'ACTIVE',
  created_date TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE lot_consumption (
  consumption_id INTEGER PRIMARY KEY AUTOINCREMENT,
  lot_id INTEGER NOT NULL REFERENCES lot(lot_id),
  qty REAL NOT NULL,
  ref_doc_type TEXT,
  ref_doc_id INTEGER,
  consumed_date TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE serial_number (
  serial_id INTEGER PRIMARY KEY AUTOINCREMENT,
  serial_no TEXT UNIQUE NOT NULL,
  material_id INTEGER NOT NULL REFERENCES material(material_id),
  lot_id INTEGER REFERENCES lot(lot_id),
  status TEXT NOT NULL DEFAULT 'IN_STOCK',
  created_date TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ===== 08c. MES/WMS 웹훅 인증 (v3) =====
CREATE TABLE integration_api_key (
  key_id INTEGER PRIMARY KEY AUTOINCREMENT,
  api_key TEXT UNIQUE NOT NULL,
  source_system TEXT NOT NULL,
  label TEXT,
  active INTEGER NOT NULL DEFAULT 1,
  created_date TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ===== 09. Reference Data (prototype_dataset 임포트, 조회 전용 — 비즈니스 로직 없음) =====
CREATE TABLE demand_forecast (
  forecast_id INTEGER PRIMARY KEY AUTOINCREMENT,
  forecast_month TEXT NOT NULL,
  material_id INTEGER NOT NULL REFERENCES material(material_id),
  company_id INTEGER REFERENCES company(company_id),
  forecast_qty REAL,
  actual_sales_qty REAL,
  mape REAL,
  forecast_version TEXT
);

CREATE TABLE quality_inspection (
  inspection_id INTEGER PRIMARY KEY AUTOINCREMENT,
  inspection_date TEXT NOT NULL,
  plant_id INTEGER REFERENCES plant(plant_id),
  material_id INTEGER NOT NULL REFERENCES material(material_id),
  inspection_type TEXT,
  sample_qty REAL,
  defect_qty REAL,
  defect_ppm REAL,
  fp_yield REAL,
  result TEXT,
  capa_required TEXT,
  lot_id INTEGER REFERENCES lot(lot_id)
);

CREATE TABLE shipment (
  shipment_id INTEGER PRIMARY KEY AUTOINCREMENT,
  external_no TEXT UNIQUE,
  so_id INTEGER REFERENCES sales_order(so_id),
  shipment_date TEXT NOT NULL,
  customer_id INTEGER REFERENCES customer(customer_id),
  material_id INTEGER REFERENCES material(material_id),
  shipped_qty REAL,
  carrier TEXT,
  otd_flag TEXT,
  status TEXT
);

CREATE TABLE finance_summary_monthly (
  period TEXT PRIMARY KEY,
  revenue REAL,
  cogs REAL,
  gross_profit REAL,
  opex REAL,
  operating_profit REAL,
  ebitda REAL,
  cash_flow REAL,
  currency TEXT
);

CREATE TABLE kpi_monthly (
  period TEXT PRIMARY KEY,
  revenue REAL,
  operating_profit REAL,
  oee_avg REAL,
  otd_rate REAL,
  ppm_avg REAL,
  inventory_turnover REAL,
  forecast_accuracy REAL,
  supply_risk_count INTEGER,
  ai_recommendation_adoption_rate REAL
);

-- ai_recommendations.csv 과거 이력(참고용) — v2의 실시간 규칙기반 AI Buyer/Scheduler
-- 추천(app/ai_agent.py)과는 별개이므로 이름을 명확히 구분한다.
CREATE TABLE ai_recommendation_log (
  recommendation_id TEXT PRIMARY KEY,
  agent TEXT,
  created_at TEXT,
  title TEXT,
  summary TEXT,
  confidence REAL,
  impact TEXT,
  status TEXT,
  target_module TEXT
);
