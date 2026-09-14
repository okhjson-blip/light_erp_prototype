import { useState, type FormEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiGet, apiPost, ApiError } from '@/lib/api'
import { useAuth } from '@/lib/auth-context'
import { Card, CardHeader, CardTitle } from '@/components/ui/card'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table'
import { Select } from '@/components/ui/select'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { KpiCard } from '@/components/KpiCard'
import { LineItemsEditor } from '@/components/LineItemsEditor'
import { WarehousePicker } from '@/components/WarehousePicker'
import { StatusBadge } from '@/components/StatusBadge'
import { cn } from '@/lib/utils'
import type {
  Material, Customer, Warehouse, Plant, SalesOrder, LineItem,
  PricePolicy, Quotation, SalesContract, SalesReturn, ServiceOrder,
  ArReceivable, SalesPerformanceRow, SalesProfitabilityRow, SalesKpi,
} from '@/lib/types'

const TABS = [
  { key: 'orders', label: '수주관리' },
  { key: 'quotations', label: '견적관리' },
  { key: 'price', label: '가격정책' },
  { key: 'contracts', label: '판매계약' },
  { key: 'returns', label: '반품관리' },
  { key: 'service', label: '서비스오더' },
  { key: 'analytics', label: '영업 분석' },
] as const
type TabKey = (typeof TABS)[number]['key']

const currency = (n: number) => `₩${Math.round(n ?? 0).toLocaleString()}`

export default function SalesPage() {
  const { hasRole } = useAuth()
  const canWrite = hasRole('영업담당', '관리자')
  const qc = useQueryClient()
  const [tab, setTab] = useState<TabKey>('orders')
  const [error, setError] = useState('')
  const [msg, setMsg] = useState('')

  const materials = useQuery({ queryKey: ['materials'], queryFn: () => apiGet<Material[]>('/api/materials') })
  const customers = useQuery({ queryKey: ['customers'], queryFn: () => apiGet<Customer[]>('/api/customers') })
  const warehouses = useQuery({ queryKey: ['warehouses'], queryFn: () => apiGet<Warehouse[]>('/api/warehouses') })
  const plants = useQuery({ queryKey: ['plants'], queryFn: () => apiGet<Plant[]>('/api/plants') })

  function flash(text: string) {
    setError('')
    setMsg(text)
  }
  function fail(err: unknown, fallback: string) {
    setMsg('')
    setError(err instanceof ApiError ? err.message : fallback)
  }

  // ---------- 수주관리 (기존) ----------
  const [customerId, setCustomerId] = useState<number | null>(null)
  const [lines, setLines] = useState<LineItem[]>([{ material_id: 0, qty: 1, price: 0 }])
  const salesOrders = useQuery({ queryKey: ['sales-orders'], queryFn: () => apiGet<SalesOrder[]>('/api/sales-orders'), enabled: tab === 'orders' })
  const createSO = useMutation({
    mutationFn: (body: { customer_id: number; lines: LineItem[] }) => apiPost('/api/sales-orders', body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['sales-orders'] })
      setLines([{ material_id: materials.data?.[0]?.material_id ?? 0, qty: 1, price: 0 }])
      flash('수주가 등록되었습니다.')
    },
    onError: (err) => fail(err, '등록 실패'),
  })
  const deliver = useMutation({
    mutationFn: ({ soId, warehouseId }: { soId: number; warehouseId: number }) =>
      apiPost(`/api/sales-orders/${soId}/deliveries`, { warehouse_id: warehouseId }),
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({ queryKey: ['sales-orders'] })
      flash(`SO#${vars.soId} 출하 처리 완료 (재고 차감)`)
    },
  })
  const invoice = useMutation({
    mutationFn: (soId: number) => apiPost<{ amount: number }>(`/api/sales-orders/${soId}/invoices`),
    onSuccess: (data, soId) => {
      qc.invalidateQueries({ queryKey: ['sales-orders'] })
      flash(`SO#${soId} 매출계상 완료 (금액: ${data.amount.toLocaleString()})`)
    },
  })
  async function submitSO(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    if (!customerId) return fail(null, '고객을 선택하세요')
    await createSO.mutateAsync({ customer_id: customerId, lines })
  }

  // ---------- 견적관리 ----------
  const [qCustomerId, setQCustomerId] = useState<number | null>(null)
  const [qLines, setQLines] = useState<LineItem[]>([{ material_id: 0, qty: 1, price: 0 }])
  const quotations = useQuery({ queryKey: ['quotations'], queryFn: () => apiGet<Quotation[]>('/api/quotations'), enabled: tab === 'quotations' })
  const createQuotation = useMutation({
    mutationFn: (body: { customer_id: number; lines: LineItem[] }) => apiPost('/api/quotations', body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['quotations'] })
      setQLines([{ material_id: materials.data?.[0]?.material_id ?? 0, qty: 1, price: 0 }])
      flash('견적이 등록되었습니다(승인함에서 승인 후 수주로 전환할 수 있습니다).')
    },
    onError: (err) => fail(err, '등록 실패'),
  })
  const convertQuotation = useMutation({
    mutationFn: (quotationId: number) => apiPost<{ so_id: number }>(`/api/quotations/${quotationId}/convert-to-order`),
    onSuccess: (data, quotationId) => {
      qc.invalidateQueries({ queryKey: ['quotations'] })
      flash(`견적#${quotationId} → 수주#${data.so_id} 전환 완료`)
    },
    onError: (err) => fail(err, '전환 실패(승인 여부를 확인하세요)'),
  })
  async function submitQuotation(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    if (!qCustomerId) return fail(null, '고객을 선택하세요')
    await createQuotation.mutateAsync({ customer_id: qCustomerId, lines: qLines })
  }

  // ---------- 가격정책 ----------
  const [ppMaterialId, setPpMaterialId] = useState<number | null>(null)
  const [ppCustomerId, setPpCustomerId] = useState<number | null>(null)
  const [ppPrice, setPpPrice] = useState('')
  const pricePolicies = useQuery({ queryKey: ['price-policies'], queryFn: () => apiGet<PricePolicy[]>('/api/price-policies'), enabled: tab === 'price' })
  const createPricePolicy = useMutation({
    mutationFn: (body: { material_id: number; customer_id: number | null; unit_price: number }) => apiPost('/api/price-policies', body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['price-policies'] })
      setPpPrice('')
      flash('가격정책이 등록되었습니다.')
    },
    onError: (err) => fail(err, '등록 실패'),
  })
  async function submitPricePolicy(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    if (!ppMaterialId || !ppPrice) return fail(null, '품목과 단가를 입력하세요')
    await createPricePolicy.mutateAsync({ material_id: ppMaterialId, customer_id: ppCustomerId, unit_price: Number(ppPrice) })
  }

  // ---------- 판매계약 ----------
  const [contractCustomerId, setContractCustomerId] = useState<number | null>(null)
  const [contractStart, setContractStart] = useState('')
  const [contractEnd, setContractEnd] = useState('')
  const [contractTerms, setContractTerms] = useState('')
  const contracts = useQuery({ queryKey: ['sales-contracts'], queryFn: () => apiGet<SalesContract[]>('/api/sales-contracts'), enabled: tab === 'contracts' })
  const createContract = useMutation({
    mutationFn: (body: { customer_id: number; start_date: string; end_date?: string; terms?: string }) => apiPost('/api/sales-contracts', body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['sales-contracts'] })
      setContractStart('')
      setContractEnd('')
      setContractTerms('')
      flash('판매계약이 등록되었습니다.')
    },
    onError: (err) => fail(err, '등록 실패'),
  })
  async function submitContract(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    if (!contractCustomerId || !contractStart) return fail(null, '고객과 시작일을 입력하세요')
    await createContract.mutateAsync({
      customer_id: contractCustomerId, start_date: contractStart,
      end_date: contractEnd || undefined, terms: contractTerms || undefined,
    })
  }

  // ---------- 반품관리 ----------
  const [returnSoId, setReturnSoId] = useState('')
  const [returnReason, setReturnReason] = useState('')
  const [returnMaterialId, setReturnMaterialId] = useState<number | null>(null)
  const [returnQty, setReturnQty] = useState('1')
  const [returnWarehouseId, setReturnWarehouseId] = useState<number | null>(null)
  const salesReturns = useQuery({ queryKey: ['sales-returns'], queryFn: () => apiGet<SalesReturn[]>('/api/sales-returns'), enabled: tab === 'returns' })
  const createReturn = useMutation({
    mutationFn: (body: { so_id: number; reason?: string; lines: { material_id: number; qty: number; warehouse_id: number }[] }) =>
      apiPost('/api/sales-returns', body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['sales-returns'] })
      setReturnSoId('')
      setReturnReason('')
      flash('반품이 접수되었습니다(승인함에서 승인 시 재고가 복원됩니다).')
    },
    onError: (err) => fail(err, '접수 실패'),
  })
  async function submitReturn(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    if (!returnSoId || !returnMaterialId || !returnWarehouseId) return fail(null, '수주번호/품목/창고를 입력하세요')
    await createReturn.mutateAsync({
      so_id: Number(returnSoId), reason: returnReason || undefined,
      lines: [{ material_id: returnMaterialId, qty: Number(returnQty), warehouse_id: returnWarehouseId }],
    })
  }

  // ---------- 서비스오더 ----------
  const [svcCustomerId, setSvcCustomerId] = useState<number | null>(null)
  const [svcMaterialId, setSvcMaterialId] = useState<number | null>(null)
  const [svcSymptom, setSvcSymptom] = useState('')
  const serviceOrders = useQuery({ queryKey: ['service-orders'], queryFn: () => apiGet<ServiceOrder[]>('/api/service-orders'), enabled: tab === 'service' })
  const createServiceOrder = useMutation({
    mutationFn: (body: { customer_id: number; material_id: number | null; symptom?: string }) => apiPost('/api/service-orders', body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['service-orders'] })
      setSvcSymptom('')
      flash('서비스오더가 접수되었습니다.')
    },
    onError: (err) => fail(err, '접수 실패'),
  })
  const updateServiceStatus = useMutation({
    mutationFn: ({ id, status }: { id: number; status: string }) => apiPost(`/api/service-orders/${id}/status`, { status }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['service-orders'] }),
  })
  async function submitServiceOrder(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    if (!svcCustomerId) return fail(null, '고객을 선택하세요')
    await createServiceOrder.mutateAsync({ customer_id: svcCustomerId, material_id: svcMaterialId, symptom: svcSymptom || undefined })
  }

  // ---------- 영업 분석 (채권/실적/손익/KPI) ----------
  const [perfGroupBy, setPerfGroupBy] = useState<'customer' | 'material' | 'month'>('customer')
  const kpi = useQuery({ queryKey: ['sales-kpi'], queryFn: () => apiGet<SalesKpi>('/api/sales/kpi'), enabled: tab === 'analytics' })
  const receivables = useQuery({ queryKey: ['ar-receivables'], queryFn: () => apiGet<ArReceivable[]>('/api/ar/receivables'), enabled: tab === 'analytics' })
  const performance = useQuery({
    queryKey: ['sales-performance', perfGroupBy],
    queryFn: () => apiGet<SalesPerformanceRow[]>(`/api/sales/performance?group_by=${perfGroupBy}`),
    enabled: tab === 'analytics',
  })
  const profitability = useQuery({
    queryKey: ['sales-profitability', perfGroupBy === 'material' ? 'material' : 'customer'],
    queryFn: () => apiGet<SalesProfitabilityRow[]>(`/api/sales/profitability?group_by=${perfGroupBy === 'material' ? 'material' : 'customer'}`),
    enabled: tab === 'analytics',
  })

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold text-text-primary">영업</h1>
      {error && <p className="text-xs text-danger">{error}</p>}
      {msg && <p className="text-xs text-success">{msg}</p>}

      <div className="flex flex-wrap gap-1 border-b border-border-default pb-2">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={cn(
              'rounded-control px-3 py-1.5 text-xs font-medium text-text-secondary hover:bg-brand-soft',
              tab === t.key && 'bg-brand-soft text-brand',
            )}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === 'orders' && (
        <div className="space-y-4">
          {canWrite && (
            <Card>
              <CardHeader><CardTitle>수주 등록</CardTitle></CardHeader>
              <form onSubmit={submitSO} className="space-y-3">
                <Select value={customerId ?? ''} onChange={(e) => setCustomerId(Number(e.target.value))}>
                  <option value="">고객 선택</option>
                  {(customers.data ?? []).map((c) => <option key={c.customer_id} value={c.customer_id}>{c.name}</option>)}
                </Select>
                <LineItemsEditor materials={materials.data ?? []} lines={lines} withPrice onChange={setLines} />
                <Button type="submit" disabled={createSO.isPending}>수주 등록</Button>
              </form>
            </Card>
          )}
          <Card>
            <CardHeader><CardTitle>수주 목록</CardTitle></CardHeader>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>SO#</TableHead><TableHead>원본번호</TableHead><TableHead>고객</TableHead>
                  <TableHead>일자</TableHead><TableHead>상태</TableHead>
                  {canWrite && <TableHead>액션</TableHead>}
                </TableRow>
              </TableHeader>
              <TableBody>
                {(salesOrders.data ?? []).map((so) => (
                  <TableRow key={so.so_id}>
                    <TableCell>{so.so_id}</TableCell>
                    <TableCell>{so.external_no}</TableCell>
                    <TableCell>{so.customer_name}</TableCell>
                    <TableCell>{so.order_date}</TableCell>
                    <TableCell><StatusBadge status={so.status} /></TableCell>
                    {canWrite && (
                      <TableCell>
                        <div className="flex items-center gap-1">
                          <WarehousePicker
                            label="출하" warehouseType="FG" warehouses={warehouses.data ?? []} plants={plants.data ?? []}
                            onConfirm={(warehouseId) => deliver.mutate({ soId: so.so_id, warehouseId })}
                          />
                          <Button type="button" size="sm" variant="outline" onClick={() => invoice.mutate(so.so_id)}>청구</Button>
                        </div>
                      </TableCell>
                    )}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Card>
        </div>
      )}

      {tab === 'quotations' && (
        <div className="space-y-4">
          {canWrite && (
            <Card>
              <CardHeader><CardTitle>견적 등록</CardTitle></CardHeader>
              <form onSubmit={submitQuotation} className="space-y-3">
                <Select value={qCustomerId ?? ''} onChange={(e) => setQCustomerId(Number(e.target.value))}>
                  <option value="">고객 선택</option>
                  {(customers.data ?? []).map((c) => <option key={c.customer_id} value={c.customer_id}>{c.name}</option>)}
                </Select>
                <p className="text-xs text-text-secondary">단가를 비워두면 가격정책에 등록된 단가가 자동 적용됩니다.</p>
                <LineItemsEditor materials={materials.data ?? []} lines={qLines} withPrice onChange={setQLines} />
                <Button type="submit" disabled={createQuotation.isPending}>견적 등록</Button>
              </form>
            </Card>
          )}
          <Card>
            <CardHeader><CardTitle>견적 목록</CardTitle></CardHeader>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>견적#</TableHead><TableHead>고객</TableHead><TableHead>일자</TableHead>
                  <TableHead>상태</TableHead><TableHead>전환된 수주</TableHead>
                  {canWrite && <TableHead>액션</TableHead>}
                </TableRow>
              </TableHeader>
              <TableBody>
                {(quotations.data ?? []).map((q) => (
                  <TableRow key={q.quotation_id}>
                    <TableCell>{q.quotation_id}</TableCell>
                    <TableCell>{q.customer_name}</TableCell>
                    <TableCell>{q.quotation_date}</TableCell>
                    <TableCell><StatusBadge status={q.status} /></TableCell>
                    <TableCell>{q.converted_so_id ?? '-'}</TableCell>
                    {canWrite && (
                      <TableCell>
                        {q.status === 'APPROVED' && (
                          <Button type="button" size="sm" variant="outline" onClick={() => convertQuotation.mutate(q.quotation_id)}>
                            수주 전환
                          </Button>
                        )}
                        {q.status === 'DRAFT' && <span className="text-xs text-text-secondary">승인함에서 승인 대기</span>}
                      </TableCell>
                    )}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Card>
        </div>
      )}

      {tab === 'price' && (
        <div className="space-y-4">
          {canWrite && (
            <Card>
              <CardHeader><CardTitle>가격정책 등록</CardTitle></CardHeader>
              <form onSubmit={submitPricePolicy} className="grid grid-cols-3 gap-3">
                <Select value={ppMaterialId ?? ''} onChange={(e) => setPpMaterialId(Number(e.target.value))}>
                  <option value="">품목 선택</option>
                  {(materials.data ?? []).map((m) => <option key={m.material_id} value={m.material_id}>{m.name}</option>)}
                </Select>
                <Select value={ppCustomerId ?? ''} onChange={(e) => setPpCustomerId(e.target.value ? Number(e.target.value) : null)}>
                  <option value="">전체 고객 공통</option>
                  {(customers.data ?? []).map((c) => <option key={c.customer_id} value={c.customer_id}>{c.name}</option>)}
                </Select>
                <Input type="number" placeholder="단가" value={ppPrice} onChange={(e) => setPpPrice(e.target.value)} />
                <Button type="submit" disabled={createPricePolicy.isPending} className="col-span-3">가격정책 등록</Button>
              </form>
            </Card>
          )}
          <Card>
            <CardHeader><CardTitle>가격정책 목록</CardTitle></CardHeader>
            <Table>
              <TableHeader>
                <TableRow><TableHead>품목</TableHead><TableHead>고객</TableHead><TableHead className="text-right">단가</TableHead><TableHead>시작일</TableHead></TableRow>
              </TableHeader>
              <TableBody>
                {(pricePolicies.data ?? []).map((p) => (
                  <TableRow key={p.price_policy_id}>
                    <TableCell>{p.material_name}</TableCell>
                    <TableCell>{p.customer_name ?? '전체 고객'}</TableCell>
                    <TableCell className="text-right">{currency(p.unit_price)}</TableCell>
                    <TableCell>{p.valid_from}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Card>
        </div>
      )}

      {tab === 'contracts' && (
        <div className="space-y-4">
          {canWrite && (
            <Card>
              <CardHeader><CardTitle>판매계약 등록</CardTitle></CardHeader>
              <form onSubmit={submitContract} className="grid grid-cols-2 gap-3">
                <Select value={contractCustomerId ?? ''} onChange={(e) => setContractCustomerId(Number(e.target.value))}>
                  <option value="">고객 선택</option>
                  {(customers.data ?? []).map((c) => <option key={c.customer_id} value={c.customer_id}>{c.name}</option>)}
                </Select>
                <div />
                <Input type="date" value={contractStart} onChange={(e) => setContractStart(e.target.value)} />
                <Input type="date" value={contractEnd} onChange={(e) => setContractEnd(e.target.value)} placeholder="종료일(선택)" />
                <Input className="col-span-2" placeholder="조건(선택)" value={contractTerms} onChange={(e) => setContractTerms(e.target.value)} />
                <Button type="submit" disabled={createContract.isPending} className="col-span-2">계약 등록</Button>
              </form>
            </Card>
          )}
          <Card>
            <CardHeader><CardTitle>판매계약 목록</CardTitle></CardHeader>
            <Table>
              <TableHeader>
                <TableRow><TableHead>고객</TableHead><TableHead>시작일</TableHead><TableHead>종료일</TableHead><TableHead>조건</TableHead><TableHead>상태</TableHead></TableRow>
              </TableHeader>
              <TableBody>
                {(contracts.data ?? []).map((c) => (
                  <TableRow key={c.contract_id}>
                    <TableCell>{c.customer_name}</TableCell>
                    <TableCell>{c.start_date}</TableCell>
                    <TableCell>{c.end_date ?? '-'}</TableCell>
                    <TableCell>{c.terms ?? '-'}</TableCell>
                    <TableCell><StatusBadge status={c.status} /></TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Card>
        </div>
      )}

      {tab === 'returns' && (
        <div className="space-y-4">
          {canWrite && (
            <Card>
              <CardHeader><CardTitle>반품 접수</CardTitle></CardHeader>
              <form onSubmit={submitReturn} className="grid grid-cols-2 gap-3">
                <Input placeholder="원본 수주(SO) 번호" value={returnSoId} onChange={(e) => setReturnSoId(e.target.value)} />
                <Input placeholder="반품 사유(선택)" value={returnReason} onChange={(e) => setReturnReason(e.target.value)} />
                <Select value={returnMaterialId ?? ''} onChange={(e) => setReturnMaterialId(Number(e.target.value))}>
                  <option value="">품목 선택</option>
                  {(materials.data ?? []).map((m) => <option key={m.material_id} value={m.material_id}>{m.name}</option>)}
                </Select>
                <Input type="number" placeholder="수량" value={returnQty} onChange={(e) => setReturnQty(e.target.value)} />
                <Select value={returnWarehouseId ?? ''} onChange={(e) => setReturnWarehouseId(Number(e.target.value))} className="col-span-2">
                  <option value="">복원할 창고 선택</option>
                  {(warehouses.data ?? []).map((w) => <option key={w.warehouse_id} value={w.warehouse_id}>{w.name}</option>)}
                </Select>
                <Button type="submit" disabled={createReturn.isPending} className="col-span-2">반품 접수 (승인함에서 승인 필요)</Button>
              </form>
            </Card>
          )}
          <Card>
            <CardHeader><CardTitle>반품 목록</CardTitle></CardHeader>
            <Table>
              <TableHeader>
                <TableRow><TableHead>반품#</TableHead><TableHead>원본 SO#</TableHead><TableHead>고객</TableHead><TableHead>사유</TableHead><TableHead>상태</TableHead></TableRow>
              </TableHeader>
              <TableBody>
                {(salesReturns.data ?? []).map((r) => (
                  <TableRow key={r.return_id}>
                    <TableCell>{r.return_id}</TableCell>
                    <TableCell>{r.so_id}</TableCell>
                    <TableCell>{r.customer_name}</TableCell>
                    <TableCell>{r.reason ?? '-'}</TableCell>
                    <TableCell><StatusBadge status={r.status} /></TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Card>
        </div>
      )}

      {tab === 'service' && (
        <div className="space-y-4">
          {canWrite && (
            <Card>
              <CardHeader><CardTitle>서비스오더 접수</CardTitle></CardHeader>
              <form onSubmit={submitServiceOrder} className="grid grid-cols-2 gap-3">
                <Select value={svcCustomerId ?? ''} onChange={(e) => setSvcCustomerId(Number(e.target.value))}>
                  <option value="">고객 선택</option>
                  {(customers.data ?? []).map((c) => <option key={c.customer_id} value={c.customer_id}>{c.name}</option>)}
                </Select>
                <Select value={svcMaterialId ?? ''} onChange={(e) => setSvcMaterialId(e.target.value ? Number(e.target.value) : null)}>
                  <option value="">대상 제품(선택)</option>
                  {(materials.data ?? []).map((m) => <option key={m.material_id} value={m.material_id}>{m.name}</option>)}
                </Select>
                <Input className="col-span-2" placeholder="증상/요청내용" value={svcSymptom} onChange={(e) => setSvcSymptom(e.target.value)} />
                <Button type="submit" disabled={createServiceOrder.isPending} className="col-span-2">접수</Button>
              </form>
            </Card>
          )}
          <Card>
            <CardHeader><CardTitle>서비스오더 목록</CardTitle></CardHeader>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>오더#</TableHead><TableHead>고객</TableHead><TableHead>제품</TableHead>
                  <TableHead>증상</TableHead><TableHead>상태</TableHead>{canWrite && <TableHead>액션</TableHead>}
                </TableRow>
              </TableHeader>
              <TableBody>
                {(serviceOrders.data ?? []).map((s) => (
                  <TableRow key={s.service_order_id}>
                    <TableCell>{s.service_order_id}</TableCell>
                    <TableCell>{s.customer_name}</TableCell>
                    <TableCell>{s.material_name ?? '-'}</TableCell>
                    <TableCell>{s.symptom ?? '-'}</TableCell>
                    <TableCell><StatusBadge status={s.status} /></TableCell>
                    {canWrite && (
                      <TableCell>
                        <Select
                          value={s.status}
                          onChange={(e) => updateServiceStatus.mutate({ id: s.service_order_id, status: e.target.value })}
                        >
                          {['RECEIVED', 'IN_PROGRESS', 'COMPLETED', 'CANCELLED'].map((st) => <option key={st} value={st}>{st}</option>)}
                        </Select>
                      </TableCell>
                    )}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Card>
        </div>
      )}

      {tab === 'analytics' && (
        <div className="space-y-4">
          {kpi.data && (
            <div className="grid grid-cols-4 gap-4">
              <KpiCard label="이번달 매출" value={currency(kpi.data.revenue_this_month)} />
              <KpiCard label="수주잔고" value={currency(kpi.data.open_backlog)} />
              <KpiCard label="이번달 수주 건수" value={kpi.data.orders_this_month} />
              <KpiCard label="이번달 수주 고객수" value={kpi.data.customers_this_month} />
            </div>
          )}

          <Card>
            <CardHeader><CardTitle>매출채권(AR) 조회</CardTitle></CardHeader>
            <Table>
              <TableHeader>
                <TableRow><TableHead>고객</TableHead><TableHead className="text-right">금액</TableHead><TableHead>청구일</TableHead><TableHead>만기(추정)</TableHead><TableHead>연체</TableHead></TableRow>
              </TableHeader>
              <TableBody>
                {(receivables.data ?? []).map((r) => (
                  <TableRow key={r.invoice_id}>
                    <TableCell>{r.customer_name}</TableCell>
                    <TableCell className="text-right">{currency(r.amount)}</TableCell>
                    <TableCell>{r.invoice_date}</TableCell>
                    <TableCell>{r.due_date}</TableCell>
                    <TableCell>{r.overdue ? <span className="text-danger">연체</span> : '-'}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>영업실적 / 손익분석</CardTitle>
              <Select value={perfGroupBy} onChange={(e) => setPerfGroupBy(e.target.value as typeof perfGroupBy)} className="w-40">
                <option value="customer">고객별</option>
                <option value="material">제품별</option>
                <option value="month">월별</option>
              </Select>
            </CardHeader>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{perfGroupBy === 'month' ? '월' : perfGroupBy === 'material' ? '제품' : '고객'}</TableHead>
                  <TableHead className="text-right">매출</TableHead>
                  {perfGroupBy !== 'month' && <TableHead className="text-right">원가(근사)</TableHead>}
                  {perfGroupBy !== 'month' && <TableHead className="text-right">손익(근사)</TableHead>}
                </TableRow>
              </TableHeader>
              <TableBody>
                {(performance.data ?? []).map((row, i) => {
                  const profitRow = profitability.data?.find((p) => p.group_label === row.group_label)
                  return (
                    <TableRow key={i}>
                      <TableCell>{row.group_label}</TableCell>
                      <TableCell className="text-right">{currency(row.total_amount)}</TableCell>
                      {perfGroupBy !== 'month' && <TableCell className="text-right">{profitRow ? currency(profitRow.cost) : '-'}</TableCell>}
                      {perfGroupBy !== 'month' && (
                        <TableCell className="text-right">{profitRow ? currency(profitRow.profit) : '-'}</TableCell>
                      )}
                    </TableRow>
                  )
                })}
              </TableBody>
            </Table>
            <p className="mt-2 text-xs text-text-secondary">
              손익(근사)은 매출 - (수량×품목 표준원가)로 계산한 단순 근사치입니다. 정교한 배부/COPA는 09.Controlling 모듈에서 다룹니다.
            </p>
          </Card>
        </div>
      )}
    </div>
  )
}
