export interface User {
  user_id: number
  name: string
  email: string
  roles: string[]
}

export interface AuthTokens {
  access_token: string
  refresh_token: string
}

export interface LoginResponse extends AuthTokens {
  user: User
}

// ---------- MDM ----------
export interface Material {
  material_id: number
  code: string
  name: string
  material_type: string
  uom: string
  plant_id: number | null
  reorder_point: number
  target_stock: number
}

export interface Customer {
  customer_id: number
  code: string | null
  name: string
  credit_limit: number
  currency: string
  payment_term: string
}

export interface Vendor {
  vendor_id: number
  code: string | null
  name: string
  payment_term: string
  lead_time_days: number
}

export interface Plant {
  plant_id: number
  code: string | null
  company_id: number
  name: string
}

export interface Warehouse {
  warehouse_id: number
  code: string | null
  plant_id: number
  name: string
  warehouse_type: string
}

// ---------- Sales / Procurement ----------
export interface LineItem {
  material_id: number
  qty: number
  price?: number
}

export interface SalesOrder {
  so_id: number
  external_no: string | null
  customer_id: number
  customer_name: string
  order_date: string
  currency: string
  status: string
}

export interface PurchaseRequisition {
  pr_id: number
  requester_id: number | null
  status: string
  created_date: string
}

export interface PurchaseOrder {
  po_id: number
  external_no: string | null
  vendor_id: number
  vendor_name: string
  pr_id: number | null
  status: string
  order_date: string
  currency: string
  po_type: string
}

// ---------- 01. Sales Management 확장 (v9) ----------
export interface PricePolicy {
  price_policy_id: number
  material_id: number
  material_name: string
  customer_id: number | null
  customer_name: string | null
  unit_price: number
  valid_from: string
  valid_to: string | null
}

export interface QuotationLine {
  quotation_line_id: number
  material_id: number
  material_name: string
  qty: number
  unit_price: number
}

export interface Quotation {
  quotation_id: number
  external_no: string | null
  customer_id: number
  customer_name: string
  status: string
  quotation_date: string
  converted_so_id: number | null
  lines?: QuotationLine[]
}

export interface SalesContract {
  contract_id: number
  external_no: string | null
  customer_id: number
  customer_name: string
  start_date: string
  end_date: string | null
  terms: string | null
  status: string
}

export interface SalesReturn {
  return_id: number
  external_no: string | null
  so_id: number
  customer_id: number
  customer_name: string
  reason: string | null
  status: string
  created_date: string
}

export interface ServiceOrder {
  service_order_id: number
  external_no: string | null
  customer_id: number
  customer_name: string
  material_id: number | null
  material_name: string | null
  symptom: string | null
  status: string
  created_date: string
}

export interface ArReceivable {
  invoice_id: number
  so_id: number
  customer_id: number
  customer_name: string
  amount: number
  status: string
  invoice_date: string
  due_date: string
  overdue: boolean
}

export interface SalesPerformanceRow {
  group_label: string
  order_count?: number
  total_qty?: number
  total_amount: number
}

export interface SalesProfitabilityRow {
  group_label: string
  revenue: number
  cost: number
  profit: number
}

export interface SalesKpi {
  revenue_this_month: number
  open_backlog: number
  orders_this_month: number
  customers_this_month: number
}

// ---------- 02. Supply Chain Management (v10, 조회전용) ----------
export interface DemandForecastAccuracy {
  material_id: number
  code: string
  name: string
  avg_mape: number
  total_forecast_qty: number
  total_actual_qty: number
  forecast_count: number
  direction: 'OVER_FORECAST' | 'UNDER_FORECAST'
}

export interface SopGapRow {
  material_id: number
  material_code: string
  material_name: string
  period: string
  demand_qty: number
  planned_qty: number
  gap: number
}

export interface SupplyPlanRow {
  material_id: number
  code: string
  name: string
  on_hand_qty: number
  incoming_po_qty: number
  available_qty: number
  reorder_point: number
  target_stock: number
  below_reorder_point: boolean
}

export interface MpsRow {
  material_id: number
  code: string
  name: string
  period: string
  planned_qty: number
  order_count: number
}

export interface InventoryPlanRow {
  material_id: number
  code: string
  name: string
  current_qty: number
  reorder_point: number
  target_stock: number
  gap_to_target: number
  risk: 'LOW_STOCK' | 'OK'
}

export interface SupplyRiskRow {
  vendor_id: number
  vendor_name: string
  total: number
  delayed: number
  delay_rate: number
  risk_level: 'HIGH' | 'MEDIUM' | 'LOW'
}

export interface ScmControlTower {
  below_reorder_point_count: number
  low_stock_count: number
  high_risk_vendor_count: number
  vendor_count: number
}

// ---------- Production ----------
export interface ProductionOrder {
  prod_order_id: number
  external_no: string | null
  material_id: number
  material_name: string
  plant_id: number
  qty: number
  status: string
  order_date: string
  // v13: 외주생산
  is_outsourced?: number
  vendor_id?: number | null
  vendor_name?: string | null
}

export interface ProductionResult {
  result_id: number
  lot: { lot_id: number; lot_no: string } | null
  serials: string[]
}

// ---------- Inventory / LOT / Serial ----------
export interface InventoryRow {
  inventory_id: number
  material_id: number
  code: string
  material_name: string
  warehouse_id: number
  warehouse_name: string
  qty: number
}

export interface InventoryTxn {
  txn_id: number
  material_id: number
  material_name: string
  warehouse_id: number
  txn_type: string
  qty: number
  ref_doc_type: string | null
  ref_doc_id: number | null
  txn_date: string
}

export interface Lot {
  lot_id: number
  lot_no: string
  material_id: number
  material_code: string
  material_name: string
  warehouse_id: number
  warehouse_name: string
  qty: number
  source_type: string
  source_ref_id: number | null
  status: string
  created_date: string
}

export interface LotTrace {
  lot: Lot
  consumptions: { consumption_id: number; qty: number; ref_doc_type: string | null; ref_doc_id: number | null; consumed_date: string }[]
  serials: SerialNumber[]
}

export interface SerialNumber {
  serial_id: number
  serial_no: string
  material_id: number
  material_code: string
  material_name: string
  lot_id: number | null
  lot_no: string | null
  status: string
  created_date: string
}

export interface SerialTrace {
  serial: SerialNumber
  lot: Lot | null
}

export interface LotReconciliation {
  material_id: number
  warehouse_id: number
  material_code: string
  material_name: string
  warehouse_name: string
  active_lot_qty: number
  inventory_qty: number
  untracked_qty: number
  consistent: boolean
}

// ---------- Finance / Approvals / Integrations ----------
export interface AccountingDocument {
  doc_id: number
  doc_type: string
  posting_date: string
  status: string
  description: string | null
}

export interface ApprovalWorkflow {
  workflow_id: number
  doc_type: string
  doc_id: number
  status: string
  current_step: string | null
  created_date: string
}

export interface IntegrationEvent {
  event_id: number
  source_system: string
  event_type: string
  payload_json: string
  status: string
  received_at: string
}

// ---------- AI Agent ----------
export interface BuyerRecommendation {
  material_id: number
  code: string
  name: string
  current_qty: number
  reorder_point: number
  target_stock: number
  suggested_qty: number
  recommended_vendor_id: number | null
  recommended_vendor_name: string | null
  rationale: string
  ai_narrative: string
}

export interface SchedulerRecommendation {
  priority_rank: number
  prod_order_id: number
  material_name: string
  qty: number
  status: string
  feasible: boolean
  rationale: string
  ai_narrative: string
}

export interface DemandPlannerRecommendation {
  material_id: number
  code: string
  name: string
  avg_mape: number
  avg_gap_qty: number
  direction: string
  current_reorder_point: number
  current_target_stock: number
  suggested_reorder_point: number
  suggested_target_stock: number
  rationale: string
  ai_narrative: string
}

export interface QualityRecommendation {
  code: string
  name: string
  avg_defect_ppm: number
  recent_fail_count: number
  recent_capa_count: number
  risk_level: string
  rationale: string
  ai_narrative: string
}

export interface CfoInsight {
  title: string
  detail: string
  severity: string
  ai_narrative: string
}

// ---------- 참고 데이터 (prototype_dataset 임포트, 조회전용) ----------
export interface KpiMonthly {
  period: string
  revenue: number
  operating_profit: number
  oee_avg: number
  otd_rate: number
  ppm_avg: number
  inventory_turnover: number
  forecast_accuracy: number
  supply_risk_count: number
}

export interface FinanceSummaryRef {
  period: string
  revenue: number
  cogs: number
  gross_profit: number
  operating_profit: number
  ebitda: number
  cash_flow: number
  currency: string
}

export interface DemandForecastRef {
  forecast_month: string
  material_code: string
  forecast_qty: number
  actual_sales_qty: number
  mape: number
  forecast_version: string
}

export interface ShipmentRef {
  external_no: string
  shipment_date: string
  customer_name: string
  material_code: string
  shipped_qty: number
  carrier: string
  otd_flag: string
  status: string
}

export interface QualityInspectionRef {
  inspection_date: string
  material_code: string
  inspection_type: string
  sample_qty: number
  defect_qty: number
  defect_ppm: number
  result: string
  capa_required: string
}

export interface AiRecommendationLogRef {
  created_at: string
  agent: string
  title: string
  confidence: number
  impact: string
  status: string
  target_module: string
}

// ---------- 03. Procurement Management 확장 (v11) ----------
export interface VendorEvaluation {
  eval_id: number
  vendor_id: number
  vendor_name: string
  eval_date: string
  delivery_score: number
  quality_score: number
  price_score: number
  total_score: number
  notes: string | null
}

export interface VendorEvaluationSummary {
  vendor_id: number
  vendor_name: string
  avg_delivery: number
  avg_quality: number
  avg_price: number
  eval_count: number
  total_score: number
  grade: string
}

export interface PurchaseContract {
  contract_id: number
  external_no: string | null
  vendor_id: number
  vendor_name: string
  start_date: string
  end_date: string | null
  terms: string | null
  status: string
}

export interface PurchaseByCategoryRow {
  category: string
  material_id?: number
  code?: string
  name?: string
  total_qty: number
  total_amount: number
  po_count?: number
}

export interface ImportCustomsRecord {
  customs_id: number
  po_id: number
  po_external_no: string | null
  vendor_name: string
  declaration_no: string | null
  customs_status: string
  customs_date: string
  notes: string | null
}

export interface PurchasePerformanceRow {
  group_label: string
  order_count?: number
  total_qty?: number
  total_amount: number
}

export interface PurchaseKpi {
  open_pr_count: number
  open_po_count: number
  spend_this_month: number
  vendor_count: number
  avg_vendor_score: number | null
}

// ---------- v12: 04 Logistics Management ----------

export interface WarehouseLocationRow {
  location_id: number
  warehouse_id: number
  warehouse_name: string
  code: string
  name: string | null
  location_type: string
}

export interface ContainerRow {
  container_id: number
  container_no: string
  container_type: string
  shipment_id: number | null
  shipment_no: string | null
  status: string
  notes: string | null
}

export interface TransportRow {
  transport_id: number
  shipment_id: number
  shipment_no: string | null
  carrier: string | null
  vehicle_no: string | null
  driver: string | null
  transport_date: string
  status: string
  freight_cost: number | null
}

export interface LogisticsCostRow {
  cost_id: number
  shipment_id: number | null
  shipment_no: string | null
  cost_type: string
  amount: number
  cost_date: string
  settled: number
  acct_doc_id: number | null
  notes: string | null
}

export interface ExportStatusRow {
  shipment_id: number
  external_no: string | null
  shipment_date: string
  carrier: string | null
  status: string | null
  customer_name: string | null
  material_name: string | null
  shipped_qty: number | null
  transport_count: number
  container_count: number
}

export interface InsurancePolicyRow {
  policy_id: number
  policy_no: string
  insurer: string
  coverage: string | null
  valid_from: string | null
  valid_to: string | null
}

export interface LogisticsClaimRow {
  claim_id: number
  shipment_id: number | null
  shipment_no: string | null
  claim_type: string
  amount: number | null
  status: string
  claim_date: string
  notes: string | null
}

export interface LogisticsDashboard {
  location_count: number
  container_active: number
  transport_in_transit: number
  unsettled_cost_count: number
  unsettled_cost_amount: number
  open_claim_count: number
  shipment_count: number
}

// ---------- v13: 05 Production Management 확장 ----------

export interface MrpRow {
  material_id: number
  code: string | null
  name: string
  requirement: number
  onhand: number
  incoming: number
  shortage: number
}

export interface MrpResponse {
  period: string | null
  rows: MrpRow[]
}

export interface OutsourcingRow {
  prod_order_id: number
  external_no: string | null
  material_name: string
  qty: number
  status: string
  order_date: string
  vendor_name: string | null
}

export interface ReworkRow {
  rework_id: number
  serial_id: number
  serial_no: string
  serial_status: string
  material_name: string
  reason: string | null
  status: string
  created_date: string
  completed_date: string | null
}

export interface ProductionCloseRow {
  close_id: number
  period: string
  total_good: number
  total_defect: number
  close_amount: number
  acct_doc_id: number | null
  closed_date: string
  notes: string | null
}

export interface OeeRow {
  period: string
  plant_name: string
  avg_oee: number | null
  avg_availability: number | null
  avg_performance: number | null
  avg_quality_rate: number | null
  result_count: number
}

export interface OeeResponse {
  measured: OeeRow[]
  reference: { period: string; oee_avg: number }[]
}

export interface ProductionDashboard {
  open_order_count: number
  outsourced_count: number
  month_good: number
  month_defect: number
  month_defect_rate: number
  open_rework_count: number
  last_closed_period: string | null
  avg_oee: number | null
}

// ---------- v14: 06 Quality Management 확장 ----------

export interface InspectionStandardRow {
  standard_id: number
  material_id: number
  material_name: string
  material_code: string | null
  inspection_type: string
  item_name: string
  method: string | null
  spec_target: number | null
  spec_lsl: number | null
  spec_usl: number | null
  unit: string | null
}

export interface QualityInspectionRow {
  inspection_id: number
  inspection_date: string
  material_id: number
  material_name: string
  inspection_type: string | null
  sample_qty: number | null
  defect_qty: number | null
  defect_ppm: number | null
  result: string | null
  capa_required: string | null
  lot_id: number | null
}

export interface SpcResponse {
  material_id: number
  sample_count: number
  points: { inspection_date: string; inspection_type: string | null; defect_ppm: number }[]
  mean: number | null
  std: number | null
  ucl: number | null
  lcl: number | null
  out_of_control_count: number | null
  cp: number | null
  cpk: number | null
  standard: InspectionStandardRow | null
}

export interface NonconformanceResponse {
  defective_serials: {
    serial_id: number
    serial_no: string
    status: string
    material_name: string
    open_rework: number
  }[]
  fail_inspections: {
    inspection_id: number
    inspection_date: string
    inspection_type: string | null
    defect_qty: number | null
    defect_ppm: number | null
    material_name: string
  }[]
}

export interface EightDRow {
  report_id: number
  material_id: number | null
  material_name: string | null
  inspection_id: number | null
  title: string
  problem: string | null
  root_cause: string | null
  corrective_action: string | null
  status: string
  report_date: string
  closed_date: string | null
}

export interface CustomerClaimRow {
  claim_id: number
  customer_id: number
  customer_name: string
  material_id: number | null
  material_name: string | null
  claim_type: string
  description: string | null
  qty: number | null
  status: string
  claim_date: string
  resolved_date: string | null
}

export interface CapaRow {
  capa_id: number
  source: string
  inspection_id: number | null
  title: string
  action_type: string
  status: string
  due_date: string | null
  created_date: string
  completed_date: string | null
  notes: string | null
}

export interface CapaResponse {
  actions: CapaRow[]
  candidates: {
    inspection_id: number
    inspection_date: string
    inspection_type: string | null
    result: string | null
    material_name: string
  }[]
}

export interface QualityDashboard {
  inspection_count: number
  avg_defect_ppm: number
  fail_count: number
  defective_serial_count: number
  open_capa_count: number
  capa_candidate_count: number
  open_claim_count: number
  open_8d_count: number
  standard_count: number
}
