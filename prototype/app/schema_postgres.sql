-- ===== 01. MDM (기준정보) =====
CREATE TABLE company (
  company_id SERIAL PRIMARY KEY,
  code TEXT UNIQUE,
  name TEXT NOT NULL
);

CREATE TABLE plant (
  plant_id SERIAL PRIMARY KEY,
  code TEXT UNIQUE,
  company_id INTEGER NOT NULL REFERENCES company(company_id),
  name TEXT NOT NULL
);

CREATE TABLE warehouse (
  warehouse_id SERIAL PRIMARY KEY,
  code TEXT UNIQUE,
  plant_id INTEGER NOT NULL REFERENCES plant(plant_id),
  name TEXT NOT NULL,
  warehouse_type TEXT NOT NULL DEFAULT 'FG'
);

CREATE TABLE material (
  material_id SERIAL PRIMARY KEY,
  code TEXT UNIQUE NOT NULL,
  name TEXT NOT NULL,
  material_type TEXT NOT NULL DEFAULT 'FG',
  uom TEXT NOT NULL DEFAULT 'EA',
  plant_id INTEGER REFERENCES plant(plant_id),
  reorder_point NUMERIC NOT NULL DEFAULT 0,
  target_stock NUMERIC NOT NULL DEFAULT 0
);

CREATE TABLE bom (
  bom_id SERIAL PRIMARY KEY,
  parent_material_id INTEGER NOT NULL REFERENCES material(material_id),
  child_material_id INTEGER NOT NULL REFERENCES material(material_id),
  qty NUMERIC NOT NULL DEFAULT 1,
  version TEXT NOT NULL DEFAULT 'v1'
);

CREATE TABLE customer (
  customer_id SERIAL PRIMARY KEY,
  code TEXT UNIQUE,
  name TEXT NOT NULL,
  credit_limit NUMERIC DEFAULT 0,
  currency TEXT DEFAULT 'KRW',
  payment_term TEXT DEFAULT 'NET30'
);

CREATE TABLE vendor (
  vendor_id SERIAL PRIMARY KEY,
  code TEXT UNIQUE,
  name TEXT NOT NULL,
  payment_term TEXT DEFAULT 'NET30',
  lead_time_days INTEGER DEFAULT 7
);

CREATE TABLE gl_account (
  account_id SERIAL PRIMARY KEY,
  code TEXT UNIQUE NOT NULL,
  name TEXT NOT NULL,
  account_type TEXT NOT NULL
);

CREATE TABLE app_user (
  user_id SERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  email TEXT UNIQUE NOT NULL,
  password_hash TEXT
);

CREATE TABLE role (
  role_id SERIAL PRIMARY KEY,
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
  created_at TEXT NOT NULL DEFAULT (now()::text),
  expires_at TEXT NOT NULL
);

-- ===== 02. Sales (영업) =====
CREATE TABLE sales_order (
  so_id SERIAL PRIMARY KEY,
  external_no TEXT UNIQUE,
  customer_id INTEGER NOT NULL REFERENCES customer(customer_id),
  order_date DATE NOT NULL DEFAULT CURRENT_DATE,
  currency TEXT NOT NULL DEFAULT 'KRW',
  status TEXT NOT NULL DEFAULT 'OPEN'
);

CREATE TABLE sales_order_line (
  so_line_id SERIAL PRIMARY KEY,
  so_id INTEGER NOT NULL REFERENCES sales_order(so_id),
  material_id INTEGER NOT NULL REFERENCES material(material_id),
  qty NUMERIC NOT NULL,
  price NUMERIC NOT NULL DEFAULT 0
);

CREATE TABLE delivery (
  delivery_id SERIAL PRIMARY KEY,
  so_id INTEGER NOT NULL REFERENCES sales_order(so_id),
  warehouse_id INTEGER NOT NULL REFERENCES warehouse(warehouse_id),
  ship_date DATE NOT NULL DEFAULT CURRENT_DATE
);

CREATE TABLE sales_invoice (
  invoice_id SERIAL PRIMARY KEY,
  so_id INTEGER NOT NULL REFERENCES sales_order(so_id),
  customer_id INTEGER NOT NULL REFERENCES customer(customer_id),
  amount NUMERIC NOT NULL DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'OPEN',
  invoice_date DATE NOT NULL DEFAULT CURRENT_DATE
);

-- ===== 03. Procurement (구매) =====
CREATE TABLE purchase_requisition (
  pr_id SERIAL PRIMARY KEY,
  requester_id INTEGER REFERENCES app_user(user_id),
  status TEXT NOT NULL DEFAULT 'OPEN',
  created_date DATE NOT NULL DEFAULT CURRENT_DATE
);

CREATE TABLE pr_line (
  pr_line_id SERIAL PRIMARY KEY,
  pr_id INTEGER NOT NULL REFERENCES purchase_requisition(pr_id),
  material_id INTEGER NOT NULL REFERENCES material(material_id),
  qty NUMERIC NOT NULL
);

CREATE TABLE purchase_order (
  po_id SERIAL PRIMARY KEY,
  external_no TEXT UNIQUE,
  vendor_id INTEGER NOT NULL REFERENCES vendor(vendor_id),
  pr_id INTEGER REFERENCES purchase_requisition(pr_id),
  status TEXT NOT NULL DEFAULT 'OPEN',
  order_date DATE NOT NULL DEFAULT CURRENT_DATE,
  currency TEXT NOT NULL DEFAULT 'KRW'
);

CREATE TABLE po_line (
  po_line_id SERIAL PRIMARY KEY,
  po_id INTEGER NOT NULL REFERENCES purchase_order(po_id),
  material_id INTEGER NOT NULL REFERENCES material(material_id),
  qty NUMERIC NOT NULL,
  price NUMERIC NOT NULL DEFAULT 0
);

CREATE TABLE goods_receipt (
  gr_id SERIAL PRIMARY KEY,
  po_line_id INTEGER NOT NULL REFERENCES po_line(po_line_id),
  warehouse_id INTEGER NOT NULL REFERENCES warehouse(warehouse_id),
  qty NUMERIC NOT NULL,
  received_date DATE NOT NULL DEFAULT CURRENT_DATE
);

CREATE TABLE ap_invoice (
  ap_id SERIAL PRIMARY KEY,
  vendor_id INTEGER NOT NULL REFERENCES vendor(vendor_id),
  po_id INTEGER REFERENCES purchase_order(po_id),
  amount NUMERIC NOT NULL DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'OPEN',
  invoice_date DATE NOT NULL DEFAULT CURRENT_DATE
);

-- ===== 04. Production (생산, 단순화) =====
CREATE TABLE production_order (
  prod_order_id SERIAL PRIMARY KEY,
  external_no TEXT UNIQUE,
  material_id INTEGER NOT NULL REFERENCES material(material_id),
  plant_id INTEGER NOT NULL REFERENCES plant(plant_id),
  qty NUMERIC NOT NULL,
  status TEXT NOT NULL DEFAULT 'PLANNED',
  order_date DATE NOT NULL DEFAULT CURRENT_DATE
);

CREATE TABLE work_order (
  work_order_id SERIAL PRIMARY KEY,
  prod_order_id INTEGER NOT NULL REFERENCES production_order(prod_order_id),
  routing_step TEXT NOT NULL DEFAULT 'ASSEMBLY',
  status TEXT NOT NULL DEFAULT 'OPEN'
);

CREATE TABLE production_result (
  result_id SERIAL PRIMARY KEY,
  work_order_id INTEGER NOT NULL REFERENCES work_order(work_order_id),
  qty_good NUMERIC NOT NULL DEFAULT 0,
  qty_defect NUMERIC NOT NULL DEFAULT 0,
  result_date DATE NOT NULL DEFAULT CURRENT_DATE,
  oee NUMERIC,
  availability NUMERIC,
  performance NUMERIC,
  quality_rate NUMERIC
);

-- ===== 05. Inventory (재고) =====
CREATE TABLE inventory (
  inventory_id SERIAL PRIMARY KEY,
  material_id INTEGER NOT NULL REFERENCES material(material_id),
  warehouse_id INTEGER NOT NULL REFERENCES warehouse(warehouse_id),
  qty NUMERIC NOT NULL DEFAULT 0,
  UNIQUE(material_id, warehouse_id)
);

CREATE TABLE inventory_transaction (
  txn_id SERIAL PRIMARY KEY,
  material_id INTEGER NOT NULL REFERENCES material(material_id),
  warehouse_id INTEGER NOT NULL REFERENCES warehouse(warehouse_id),
  txn_type TEXT NOT NULL,
  qty NUMERIC NOT NULL,
  ref_doc_type TEXT,
  ref_doc_id INTEGER,
  txn_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ===== 06. FI (회계 기본) =====
CREATE TABLE accounting_document (
  doc_id SERIAL PRIMARY KEY,
  doc_type TEXT NOT NULL,
  posting_date DATE NOT NULL DEFAULT CURRENT_DATE,
  status TEXT NOT NULL DEFAULT 'POSTED',
  description TEXT
);

CREATE TABLE accounting_line (
  line_id SERIAL PRIMARY KEY,
  doc_id INTEGER NOT NULL REFERENCES accounting_document(doc_id),
  account_id INTEGER NOT NULL REFERENCES gl_account(account_id),
  debit NUMERIC NOT NULL DEFAULT 0,
  credit NUMERIC NOT NULL DEFAULT 0
);

-- ===== 07. Common (승인/감사) =====
CREATE TABLE approval_workflow (
  workflow_id SERIAL PRIMARY KEY,
  doc_type TEXT NOT NULL,
  doc_id INTEGER NOT NULL,
  status TEXT NOT NULL DEFAULT 'PENDING',
  current_step TEXT DEFAULT 'MANAGER',
  created_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE audit_log (
  log_id SERIAL PRIMARY KEY,
  user_id INTEGER REFERENCES app_user(user_id),
  action TEXT NOT NULL,
  entity TEXT NOT NULL,
  entity_id INTEGER,
  ts TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ===== 08. Integration (MES/WMS 연계, v2) =====
CREATE TABLE integration_event_log (
  event_id SERIAL PRIMARY KEY,
  source_system TEXT NOT NULL,
  event_type TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'PROCESSED',
  received_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ===== 08b. WMS/QMS LOT·Serial 추적 (v3) =====
-- 기존 inventory(집계) 테이블은 그대로 두고, LOT은 병행 기록되는 별도 레이어다.
-- 과거 임포트 재고는 LOT이 없으므로 소급 생성하지 않는다(task-plan-lot-serial.md 참고).
CREATE TABLE lot (
  lot_id SERIAL PRIMARY KEY,
  lot_no TEXT UNIQUE NOT NULL,
  material_id INTEGER NOT NULL REFERENCES material(material_id),
  warehouse_id INTEGER NOT NULL REFERENCES warehouse(warehouse_id),
  qty NUMERIC NOT NULL DEFAULT 0,
  source_type TEXT NOT NULL,
  source_ref_id INTEGER,
  status TEXT NOT NULL DEFAULT 'ACTIVE',
  created_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE lot_consumption (
  consumption_id SERIAL PRIMARY KEY,
  lot_id INTEGER NOT NULL REFERENCES lot(lot_id),
  qty NUMERIC NOT NULL,
  ref_doc_type TEXT,
  ref_doc_id INTEGER,
  consumed_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE serial_number (
  serial_id SERIAL PRIMARY KEY,
  serial_no TEXT UNIQUE NOT NULL,
  material_id INTEGER NOT NULL REFERENCES material(material_id),
  lot_id INTEGER REFERENCES lot(lot_id),
  status TEXT NOT NULL DEFAULT 'IN_STOCK',
  created_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ===== 08c. MES/WMS 웹훅 인증 (v3) =====
CREATE TABLE integration_api_key (
  key_id SERIAL PRIMARY KEY,
  api_key TEXT UNIQUE NOT NULL,
  source_system TEXT NOT NULL,
  label TEXT,
  active BOOLEAN NOT NULL DEFAULT TRUE,
  created_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ===== 09. Reference Data (prototype_dataset 임포트, 조회 전용 — 비즈니스 로직 없음) =====
CREATE TABLE demand_forecast (
  forecast_id SERIAL PRIMARY KEY,
  forecast_month TEXT NOT NULL,
  material_id INTEGER NOT NULL REFERENCES material(material_id),
  company_id INTEGER REFERENCES company(company_id),
  forecast_qty NUMERIC,
  actual_sales_qty NUMERIC,
  mape NUMERIC,
  forecast_version TEXT
);

CREATE TABLE quality_inspection (
  inspection_id SERIAL PRIMARY KEY,
  inspection_date TEXT NOT NULL,
  plant_id INTEGER REFERENCES plant(plant_id),
  material_id INTEGER NOT NULL REFERENCES material(material_id),
  inspection_type TEXT,
  sample_qty NUMERIC,
  defect_qty NUMERIC,
  defect_ppm NUMERIC,
  fp_yield NUMERIC,
  result TEXT,
  capa_required TEXT,
  lot_id INTEGER REFERENCES lot(lot_id)
);

CREATE TABLE shipment (
  shipment_id SERIAL PRIMARY KEY,
  external_no TEXT UNIQUE,
  so_id INTEGER REFERENCES sales_order(so_id),
  shipment_date TEXT NOT NULL,
  customer_id INTEGER REFERENCES customer(customer_id),
  material_id INTEGER REFERENCES material(material_id),
  shipped_qty NUMERIC,
  carrier TEXT,
  otd_flag TEXT,
  status TEXT
);

CREATE TABLE finance_summary_monthly (
  period TEXT PRIMARY KEY,
  revenue NUMERIC,
  cogs NUMERIC,
  gross_profit NUMERIC,
  opex NUMERIC,
  operating_profit NUMERIC,
  ebitda NUMERIC,
  cash_flow NUMERIC,
  currency TEXT
);

CREATE TABLE kpi_monthly (
  period TEXT PRIMARY KEY,
  revenue NUMERIC,
  operating_profit NUMERIC,
  oee_avg NUMERIC,
  otd_rate NUMERIC,
  ppm_avg NUMERIC,
  inventory_turnover NUMERIC,
  forecast_accuracy NUMERIC,
  supply_risk_count INTEGER,
  ai_recommendation_adoption_rate NUMERIC
);

-- ai_recommendations.csv 과거 이력(참고용) — v2의 실시간 규칙기반 AI Buyer/Scheduler
-- 추천(app/ai_agent.py)과는 별개이므로 이름을 명확히 구분한다.
CREATE TABLE ai_recommendation_log (
  recommendation_id TEXT PRIMARY KEY,
  agent TEXT,
  created_at TEXT,
  title TEXT,
  summary TEXT,
  confidence NUMERIC,
  impact TEXT,
  status TEXT,
  target_module TEXT
);
