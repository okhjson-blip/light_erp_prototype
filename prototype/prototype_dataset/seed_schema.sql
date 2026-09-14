-- AX ERP Prototype Dataset seed helper
-- CSV files are UTF-8-SIG encoded and include headers.

-- companies: 4 rows
CREATE TABLE IF NOT EXISTS companies (
  company_code TEXT,
  company_name TEXT,
  country TEXT,
  currency TEXT,
  company_type TEXT
);
-- PostgreSQL example:
-- \copy companies(company_code, company_name, country, currency, company_type) FROM './companies.csv' WITH CSV HEADER ENCODING 'UTF8';

-- plants: 5 rows
CREATE TABLE IF NOT EXISTS plants (
  plant_code TEXT,
  company_code TEXT,
  plant_name TEXT,
  plant_type TEXT,
  timezone TEXT
);
-- PostgreSQL example:
-- \copy plants(plant_code, company_code, plant_name, plant_type, timezone) FROM './plants.csv' WITH CSV HEADER ENCODING 'UTF8';

-- warehouses: 8 rows
CREATE TABLE IF NOT EXISTS warehouses (
  warehouse_code TEXT,
  plant_code TEXT,
  warehouse_name TEXT,
  warehouse_type TEXT,
  status TEXT
);
-- PostgreSQL example:
-- \copy warehouses(warehouse_code, plant_code, warehouse_name, warehouse_type, status) FROM './warehouses.csv' WITH CSV HEADER ENCODING 'UTF8';

-- customers: 6 rows
CREATE TABLE IF NOT EXISTS customers (
  customer_code TEXT,
  customer_name TEXT,
  country TEXT,
  customer_group TEXT,
  currency TEXT,
  credit_limit TEXT,
  payment_terms TEXT
);
-- PostgreSQL example:
-- \copy customers(customer_code, customer_name, country, customer_group, currency, credit_limit, payment_terms) FROM './customers.csv' WITH CSV HEADER ENCODING 'UTF8';

-- vendors: 8 rows
CREATE TABLE IF NOT EXISTS vendors (
  vendor_code TEXT,
  vendor_name TEXT,
  country TEXT,
  vendor_group TEXT,
  lead_time_days TEXT,
  quality_grade TEXT,
  payment_terms TEXT
);
-- PostgreSQL example:
-- \copy vendors(vendor_code, vendor_name, country, vendor_group, lead_time_days, quality_grade, payment_terms) FROM './vendors.csv' WITH CSV HEADER ENCODING 'UTF8';

-- materials: 15 rows
CREATE TABLE IF NOT EXISTS materials (
  material_code TEXT,
  material_name TEXT,
  material_type TEXT,
  material_group TEXT,
  base_uom TEXT,
  standard_price TEXT,
  standard_cost TEXT,
  status TEXT
);
-- PostgreSQL example:
-- \copy materials(material_code, material_name, material_type, material_group, base_uom, standard_price, standard_cost, status) FROM './materials.csv' WITH CSV HEADER ENCODING 'UTF8';

-- bom_items: 25 rows
CREATE TABLE IF NOT EXISTS bom_items (
  bom_code TEXT,
  parent_material TEXT,
  component_material TEXT,
  item_no TEXT,
  quantity TEXT,
  uom TEXT,
  effective_from TEXT,
  status TEXT
);
-- PostgreSQL example:
-- \copy bom_items(bom_code, parent_material, component_material, item_no, quantity, uom, effective_from, status) FROM './bom_items.csv' WITH CSV HEADER ENCODING 'UTF8';

-- demand_forecast: 60 rows
CREATE TABLE IF NOT EXISTS demand_forecast (
  forecast_month TEXT,
  material_code TEXT,
  forecast_qty TEXT,
  actual_sales_qty TEXT,
  mape TEXT,
  forecast_version TEXT,
  company_code TEXT
);
-- PostgreSQL example:
-- \copy demand_forecast(forecast_month, material_code, forecast_qty, actual_sales_qty, mape, forecast_version, company_code) FROM './demand_forecast.csv' WITH CSV HEADER ENCODING 'UTF8';

-- sales_orders: 216 rows
CREATE TABLE IF NOT EXISTS sales_orders (
  sales_order_no TEXT,
  order_date TEXT,
  requested_delivery_date TEXT,
  customer_code TEXT,
  material_code TEXT,
  quantity TEXT,
  unit_price TEXT,
  amount TEXT,
  currency TEXT,
  status TEXT,
  company_code TEXT
);
-- PostgreSQL example:
-- \copy sales_orders(sales_order_no, order_date, requested_delivery_date, customer_code, material_code, quantity, unit_price, amount, currency, status, company_code) FROM './sales_orders.csv' WITH CSV HEADER ENCODING 'UTF8';

-- purchase_orders: 264 rows
CREATE TABLE IF NOT EXISTS purchase_orders (
  purchase_order_no TEXT,
  order_date TEXT,
  due_date TEXT,
  vendor_code TEXT,
  material_code TEXT,
  quantity TEXT,
  unit_price TEXT,
  amount TEXT,
  currency TEXT,
  status TEXT,
  company_code TEXT
);
-- PostgreSQL example:
-- \copy purchase_orders(purchase_order_no, order_date, due_date, vendor_code, material_code, quantity, unit_price, amount, currency, status, company_code) FROM './purchase_orders.csv' WITH CSV HEADER ENCODING 'UTF8';

-- inventory_snapshot: 45 rows
CREATE TABLE IF NOT EXISTS inventory_snapshot (
  snapshot_date TEXT,
  plant_code TEXT,
  warehouse_code TEXT,
  material_code TEXT,
  on_hand_qty TEXT,
  allocated_qty TEXT,
  available_qty TEXT,
  safety_stock_qty TEXT,
  dos TEXT,
  inventory_value TEXT,
  status TEXT
);
-- PostgreSQL example:
-- \copy inventory_snapshot(snapshot_date, plant_code, warehouse_code, material_code, on_hand_qty, allocated_qty, available_qty, safety_stock_qty, dos, inventory_value, status) FROM './inventory_snapshot.csv' WITH CSV HEADER ENCODING 'UTF8';

-- production_orders: 180 rows
CREATE TABLE IF NOT EXISTS production_orders (
  production_order_no TEXT,
  plant_code TEXT,
  material_code TEXT,
  planned_qty TEXT,
  completed_qty TEXT,
  start_date TEXT,
  end_date TEXT,
  status TEXT,
  line_code TEXT
);
-- PostgreSQL example:
-- \copy production_orders(production_order_no, plant_code, material_code, planned_qty, completed_qty, start_date, end_date, status, line_code) FROM './production_orders.csv' WITH CSV HEADER ENCODING 'UTF8';

-- production_results: 180 rows
CREATE TABLE IF NOT EXISTS production_results (
  result_date TEXT,
  production_order_no TEXT,
  plant_code TEXT,
  material_code TEXT,
  good_qty TEXT,
  defect_qty TEXT,
  oee TEXT,
  availability TEXT,
  performance TEXT,
  quality_rate TEXT
);
-- PostgreSQL example:
-- \copy production_results(result_date, production_order_no, plant_code, material_code, good_qty, defect_qty, oee, availability, performance, quality_rate) FROM './production_results.csv' WITH CSV HEADER ENCODING 'UTF8';

-- quality_inspections: 180 rows
CREATE TABLE IF NOT EXISTS quality_inspections (
  inspection_date TEXT,
  plant_code TEXT,
  material_code TEXT,
  inspection_type TEXT,
  sample_qty TEXT,
  defect_qty TEXT,
  defect_ppm TEXT,
  fp_yield TEXT,
  result TEXT,
  capa_required TEXT
);
-- PostgreSQL example:
-- \copy quality_inspections(inspection_date, plant_code, material_code, inspection_type, sample_qty, defect_qty, defect_ppm, fp_yield, result, capa_required) FROM './quality_inspections.csv' WITH CSV HEADER ENCODING 'UTF8';

-- shipments: 124 rows
CREATE TABLE IF NOT EXISTS shipments (
  shipment_no TEXT,
  sales_order_no TEXT,
  shipment_date TEXT,
  customer_code TEXT,
  material_code TEXT,
  shipped_qty TEXT,
  carrier TEXT,
  otd_flag TEXT,
  status TEXT
);
-- PostgreSQL example:
-- \copy shipments(shipment_no, sales_order_no, shipment_date, customer_code, material_code, shipped_qty, carrier, otd_flag, status) FROM './shipments.csv' WITH CSV HEADER ENCODING 'UTF8';

-- finance_summary: 12 rows
CREATE TABLE IF NOT EXISTS finance_summary (
  period TEXT,
  revenue TEXT,
  cogs TEXT,
  gross_profit TEXT,
  opex TEXT,
  operating_profit TEXT,
  ebitda TEXT,
  cash_flow TEXT,
  currency TEXT
);
-- PostgreSQL example:
-- \copy finance_summary(period, revenue, cogs, gross_profit, opex, operating_profit, ebitda, cash_flow, currency) FROM './finance_summary.csv' WITH CSV HEADER ENCODING 'UTF8';

-- kpi_monthly: 12 rows
CREATE TABLE IF NOT EXISTS kpi_monthly (
  period TEXT,
  revenue TEXT,
  operating_profit TEXT,
  oee_avg TEXT,
  otd_rate TEXT,
  ppm_avg TEXT,
  inventory_turnover TEXT,
  forecast_accuracy TEXT,
  supply_risk_count TEXT,
  ai_recommendation_adoption_rate TEXT
);
-- PostgreSQL example:
-- \copy kpi_monthly(period, revenue, operating_profit, oee_avg, otd_rate, ppm_avg, inventory_turnover, forecast_accuracy, supply_risk_count, ai_recommendation_adoption_rate) FROM './kpi_monthly.csv' WITH CSV HEADER ENCODING 'UTF8';

-- ai_recommendations: 5 rows
CREATE TABLE IF NOT EXISTS ai_recommendations (
  recommendation_id TEXT,
  agent TEXT,
  created_at TEXT,
  title TEXT,
  summary TEXT,
  confidence TEXT,
  impact TEXT,
  status TEXT,
  target_module TEXT
);
-- PostgreSQL example:
-- \copy ai_recommendations(recommendation_id, agent, created_at, title, summary, confidence, impact, status, target_module) FROM './ai_recommendations.csv' WITH CSV HEADER ENCODING 'UTF8';
