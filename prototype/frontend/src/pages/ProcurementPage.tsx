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
  Material, Vendor, Warehouse, Plant, PurchaseRequisition, PurchaseOrder, LineItem,
  VendorEvaluation, VendorEvaluationSummary, PurchaseContract, PurchaseByCategoryRow,
  ImportCustomsRecord, PurchasePerformanceRow, PurchaseKpi,
} from '@/lib/types'

// 03. Procurement Management (v9: PR/PO 기존 + v11: 공급업체평가/구매계약/카테고리별구매/통관/분석 확장)
const TABS = [
  { key: 'orders', label: '발주관리' },
  { key: 'evaluation', label: '공급업체평가' },
  { key: 'contracts', label: '구매계약' },
  { key: 'category', label: '카테고리별 구매' },
  { key: 'customs', label: '통관관리' },
  { key: 'analytics', label: '구매 분석' },
] as const
type TabKey = (typeof TABS)[number]['key']

const PO_TYPES = [
  { value: 'STANDARD', label: '일반구매' },
  { value: 'OUTSOURCING', label: '외주구매' },
  { value: 'CONSIGNMENT', label: '위탁구매' },
]
const currency = (n: number) => `₩${Math.round(n ?? 0).toLocaleString()}`

export default function ProcurementPage() {
  const { hasRole } = useAuth()
  const canWrite = hasRole('구매담당', '관리자')
  const qc = useQueryClient()
  const [tab, setTab] = useState<TabKey>('orders')
  const [error, setError] = useState('')
  const [msg, setMsg] = useState('')

  const materials = useQuery({ queryKey: ['materials'], queryFn: () => apiGet<Material[]>('/api/materials') })
  const vendors = useQuery({ queryKey: ['vendors'], queryFn: () => apiGet<Vendor[]>('/api/vendors') })
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

  // ---------- 발주관리 (기존 PR/PO, v11: po_type 추가) ----------
  const [vendorId, setVendorId] = useState<number | null>(null)
  const [poType, setPoType] = useState('STANDARD')
  const [prLines, setPrLines] = useState<LineItem[]>([{ material_id: 0, qty: 1 }])
  const [poLines, setPoLines] = useState<LineItem[]>([{ material_id: 0, qty: 1, price: 0 }])
  const prs = useQuery({ queryKey: ['prs'], queryFn: () => apiGet<PurchaseRequisition[]>('/api/purchase-requisitions'), enabled: tab === 'orders' })
  const pos = useQuery({ queryKey: ['pos'], queryFn: () => apiGet<PurchaseOrder[]>('/api/purchase-orders'), enabled: tab === 'orders' })

  const createPR = useMutation({
    mutationFn: (body: { lines: LineItem[] }) => apiPost('/api/purchase-requisitions', body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['prs'] })
      setPrLines([{ material_id: materials.data?.[0]?.material_id ?? 0, qty: 1 }])
      flash('PR이 등록되었습니다.')
    },
    onError: (err) => fail(err, '등록 실패'),
  })
  const createPO = useMutation({
    mutationFn: (body: { vendor_id: number; po_type: string; lines: LineItem[] }) => apiPost('/api/purchase-orders', body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['pos'] })
      setPoLines([{ material_id: materials.data?.[0]?.material_id ?? 0, qty: 1, price: 0 }])
      flash('PO가 등록되었습니다.')
    },
    onError: (err) => fail(err, '등록 실패'),
  })
  const goodsReceipt = useMutation({
    mutationFn: ({ poId, warehouseId }: { poId: number; warehouseId: number }) =>
      apiPost<{ amount: number }>(`/api/purchase-orders/${poId}/goods-receipts`, { warehouse_id: warehouseId }),
    onSuccess: (data, vars) => {
      qc.invalidateQueries({ queryKey: ['pos'] })
      flash(`PO#${vars.poId} 입고 완료 (매입채무: ${data.amount.toLocaleString()})`)
    },
  })
  async function submitPR(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    await createPR.mutateAsync({ lines: prLines })
  }
  async function submitPO(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    if (!vendorId) return fail(null, '공급사를 선택하세요')
    await createPO.mutateAsync({ vendor_id: vendorId, po_type: poType, lines: poLines })
  }

  // ---------- 공급업체평가 ----------
  const [evVendorId, setEvVendorId] = useState<number | null>(null)
  const [evDelivery, setEvDelivery] = useState('80')
  const [evQuality, setEvQuality] = useState('80')
  const [evPrice, setEvPrice] = useState('80')
  const [evNotes, setEvNotes] = useState('')
  const evaluations = useQuery({ queryKey: ['vendor-evaluations'], queryFn: () => apiGet<VendorEvaluation[]>('/api/vendor-evaluations'), enabled: tab === 'evaluation' })
  const evalSummary = useQuery({ queryKey: ['vendor-evaluations-summary'], queryFn: () => apiGet<VendorEvaluationSummary[]>('/api/vendor-evaluations/summary'), enabled: tab === 'evaluation' })
  const createEvaluation = useMutation({
    mutationFn: (body: { vendor_id: number; delivery_score: number; quality_score: number; price_score: number; notes?: string }) =>
      apiPost('/api/vendor-evaluations', body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['vendor-evaluations'] })
      qc.invalidateQueries({ queryKey: ['vendor-evaluations-summary'] })
      setEvNotes('')
      flash('공급업체 평가가 등록되었습니다.')
    },
    onError: (err) => fail(err, '등록 실패'),
  })
  async function submitEvaluation(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    if (!evVendorId) return fail(null, '공급사를 선택하세요')
    await createEvaluation.mutateAsync({
      vendor_id: evVendorId, delivery_score: Number(evDelivery), quality_score: Number(evQuality),
      price_score: Number(evPrice), notes: evNotes || undefined,
    })
  }

  // ---------- 구매계약관리 ----------
  const [contractVendorId, setContractVendorId] = useState<number | null>(null)
  const [contractStart, setContractStart] = useState('')
  const [contractEnd, setContractEnd] = useState('')
  const [contractTerms, setContractTerms] = useState('')
  const contracts = useQuery({ queryKey: ['purchase-contracts'], queryFn: () => apiGet<PurchaseContract[]>('/api/purchase-contracts'), enabled: tab === 'contracts' })
  const createContract = useMutation({
    mutationFn: (body: { vendor_id: number; start_date: string; end_date?: string; terms?: string }) => apiPost('/api/purchase-contracts', body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['purchase-contracts'] })
      setContractStart('')
      setContractEnd('')
      setContractTerms('')
      flash('구매계약이 등록되었습니다.')
    },
    onError: (err) => fail(err, '등록 실패'),
  })
  async function submitContract(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    if (!contractVendorId || !contractStart) return fail(null, '공급사와 시작일을 입력하세요')
    await createContract.mutateAsync({
      vendor_id: contractVendorId, start_date: contractStart,
      end_date: contractEnd || undefined, terms: contractTerms || undefined,
    })
  }

  // ---------- 카테고리별 구매 (원재료/부자재/설비/금형 — material_type 필터 뷰) ----------
  const byCategory = useQuery({
    queryKey: ['purchase-by-category'],
    queryFn: () => apiGet<PurchaseByCategoryRow[]>('/api/purchase/by-category'),
    enabled: tab === 'category',
  })

  // ---------- 통관관리/수입관리 ----------
  const [customsPoId, setCustomsPoId] = useState('')
  const [customsDeclNo, setCustomsDeclNo] = useState('')
  const customsRecords = useQuery({ queryKey: ['import-customs'], queryFn: () => apiGet<ImportCustomsRecord[]>('/api/import-customs'), enabled: tab === 'customs' })
  const createCustoms = useMutation({
    mutationFn: (body: { po_id?: number; po_no?: string; declaration_no?: string }) => apiPost('/api/import-customs', body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['import-customs'] })
      setCustomsPoId('')
      setCustomsDeclNo('')
      flash('통관 기록이 등록되었습니다.')
    },
    onError: (err) => fail(err, '등록 실패'),
  })
  const updateCustomsStatus = useMutation({
    mutationFn: ({ id, status }: { id: number; status: string }) => apiPost(`/api/import-customs/${id}/status`, { customs_status: status }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['import-customs'] }),
  })
  async function submitCustoms(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const raw = customsPoId.trim()
    if (!raw) return fail(null, 'PO 번호를 입력하세요')
    // 숫자 ID(264)와 원본번호(PO-2026-00264) 모두 허용
    const ref = /^\d+$/.test(raw) ? { po_id: Number(raw) } : { po_no: raw }
    await createCustoms.mutateAsync({ ...ref, declaration_no: customsDeclNo || undefined })
  }

  // ---------- 구매 분석 (구매실적/구매 KPI) ----------
  const [perfGroupBy, setPerfGroupBy] = useState<'vendor' | 'material' | 'month'>('vendor')
  const kpi = useQuery({ queryKey: ['purchase-kpi'], queryFn: () => apiGet<PurchaseKpi>('/api/purchase/kpi'), enabled: tab === 'analytics' })
  const performance = useQuery({
    queryKey: ['purchase-performance', perfGroupBy],
    queryFn: () => apiGet<PurchasePerformanceRow[]>(`/api/purchase/performance?group_by=${perfGroupBy}`),
    enabled: tab === 'analytics',
  })

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold text-text-primary">구매</h1>
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
              <CardHeader><CardTitle>구매요청(PR) 등록</CardTitle></CardHeader>
              <form onSubmit={submitPR} className="space-y-3">
                <LineItemsEditor materials={materials.data ?? []} lines={prLines} onChange={setPrLines} />
                <Button type="submit" disabled={createPR.isPending}>PR 등록</Button>
              </form>
            </Card>
          )}
          <Card>
            <CardHeader><CardTitle>PR 목록</CardTitle></CardHeader>
            <Table>
              <TableHeader>
                <TableRow><TableHead>PR#</TableHead><TableHead>상태</TableHead><TableHead>일자</TableHead></TableRow>
              </TableHeader>
              <TableBody>
                {(prs.data ?? []).map((pr) => (
                  <TableRow key={pr.pr_id}>
                    <TableCell>{pr.pr_id}</TableCell>
                    <TableCell><StatusBadge status={pr.status} /></TableCell>
                    <TableCell>{pr.created_date}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Card>

          {canWrite && (
            <Card>
              <CardHeader><CardTitle>발주(PO) 등록</CardTitle></CardHeader>
              <form onSubmit={submitPO} className="space-y-3">
                <div className="grid grid-cols-2 gap-3">
                  <Select value={vendorId ?? ''} onChange={(e) => setVendorId(Number(e.target.value))}>
                    <option value="">공급사 선택</option>
                    {(vendors.data ?? []).map((v) => <option key={v.vendor_id} value={v.vendor_id}>{v.name}</option>)}
                  </Select>
                  <Select value={poType} onChange={(e) => setPoType(e.target.value)}>
                    {PO_TYPES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
                  </Select>
                </div>
                <LineItemsEditor materials={materials.data ?? []} lines={poLines} withPrice onChange={setPoLines} />
                <Button type="submit" disabled={createPO.isPending}>PO 등록</Button>
              </form>
            </Card>
          )}
          <Card>
            <CardHeader><CardTitle>PO 목록</CardTitle></CardHeader>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>PO#</TableHead><TableHead>원본번호</TableHead><TableHead>공급사</TableHead>
                  <TableHead>구분</TableHead><TableHead>상태</TableHead><TableHead>일자</TableHead>
                  {canWrite && <TableHead>액션</TableHead>}
                </TableRow>
              </TableHeader>
              <TableBody>
                {(pos.data ?? []).map((po) => (
                  <TableRow key={po.po_id}>
                    <TableCell>{po.po_id}</TableCell>
                    <TableCell>{po.external_no}</TableCell>
                    <TableCell>{po.vendor_name}</TableCell>
                    <TableCell>{PO_TYPES.find((t) => t.value === po.po_type)?.label ?? po.po_type}</TableCell>
                    <TableCell><StatusBadge status={po.status} /></TableCell>
                    <TableCell>{po.order_date}</TableCell>
                    {canWrite && (
                      <TableCell>
                        {po.status === 'OPEN' && (
                          <WarehousePicker
                            label="입고처리" warehouseType="RM" warehouses={warehouses.data ?? []} plants={plants.data ?? []}
                            onConfirm={(warehouseId) => goodsReceipt.mutate({ poId: po.po_id, warehouseId })}
                          />
                        )}
                      </TableCell>
                    )}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Card>
        </div>
      )}

      {tab === 'evaluation' && (
        <div className="space-y-4">
          {evalSummary.data && evalSummary.data.length > 0 && (
            <Card>
              <CardHeader><CardTitle>공급업체 종합 등급</CardTitle></CardHeader>
              <Table>
                <TableHeader>
                  <TableRow><TableHead>공급사</TableHead><TableHead className="text-right">납기</TableHead><TableHead className="text-right">품질</TableHead><TableHead className="text-right">가격</TableHead><TableHead className="text-right">종합점수</TableHead><TableHead>등급</TableHead></TableRow>
                </TableHeader>
                <TableBody>
                  {evalSummary.data.map((s) => (
                    <TableRow key={s.vendor_id}>
                      <TableCell>{s.vendor_name}</TableCell>
                      <TableCell className="text-right">{s.avg_delivery.toFixed(1)}</TableCell>
                      <TableCell className="text-right">{s.avg_quality.toFixed(1)}</TableCell>
                      <TableCell className="text-right">{s.avg_price.toFixed(1)}</TableCell>
                      <TableCell className="text-right">{s.total_score.toFixed(1)}</TableCell>
                      <TableCell><span className={cn(s.grade === 'A' && 'text-success', s.grade === 'C' && 'text-danger')}>{s.grade}</span></TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </Card>
          )}
          {canWrite && (
            <Card>
              <CardHeader><CardTitle>공급업체 평가 등록</CardTitle></CardHeader>
              <form onSubmit={submitEvaluation} className="grid grid-cols-3 gap-3">
                <Select className="col-span-3" value={evVendorId ?? ''} onChange={(e) => setEvVendorId(Number(e.target.value))}>
                  <option value="">공급사 선택</option>
                  {(vendors.data ?? []).map((v) => <option key={v.vendor_id} value={v.vendor_id}>{v.name}</option>)}
                </Select>
                <Input type="number" min={0} max={100} placeholder="납기 점수" value={evDelivery} onChange={(e) => setEvDelivery(e.target.value)} />
                <Input type="number" min={0} max={100} placeholder="품질 점수" value={evQuality} onChange={(e) => setEvQuality(e.target.value)} />
                <Input type="number" min={0} max={100} placeholder="가격 점수" value={evPrice} onChange={(e) => setEvPrice(e.target.value)} />
                <Input className="col-span-3" placeholder="비고(선택)" value={evNotes} onChange={(e) => setEvNotes(e.target.value)} />
                <Button type="submit" disabled={createEvaluation.isPending} className="col-span-3">평가 등록</Button>
              </form>
            </Card>
          )}
          <Card>
            <CardHeader><CardTitle>평가 이력</CardTitle></CardHeader>
            <Table>
              <TableHeader>
                <TableRow><TableHead>공급사</TableHead><TableHead>평가일</TableHead><TableHead className="text-right">납기</TableHead><TableHead className="text-right">품질</TableHead><TableHead className="text-right">가격</TableHead><TableHead className="text-right">종합</TableHead><TableHead>비고</TableHead></TableRow>
              </TableHeader>
              <TableBody>
                {(evaluations.data ?? []).map((e) => (
                  <TableRow key={e.eval_id}>
                    <TableCell>{e.vendor_name}</TableCell>
                    <TableCell>{e.eval_date}</TableCell>
                    <TableCell className="text-right">{e.delivery_score}</TableCell>
                    <TableCell className="text-right">{e.quality_score}</TableCell>
                    <TableCell className="text-right">{e.price_score}</TableCell>
                    <TableCell className="text-right">{e.total_score}</TableCell>
                    <TableCell>{e.notes ?? '-'}</TableCell>
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
              <CardHeader><CardTitle>구매계약 등록</CardTitle></CardHeader>
              <form onSubmit={submitContract} className="grid grid-cols-2 gap-3">
                <Select value={contractVendorId ?? ''} onChange={(e) => setContractVendorId(Number(e.target.value))}>
                  <option value="">공급사 선택</option>
                  {(vendors.data ?? []).map((v) => <option key={v.vendor_id} value={v.vendor_id}>{v.name}</option>)}
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
            <CardHeader><CardTitle>구매계약 목록</CardTitle></CardHeader>
            <Table>
              <TableHeader>
                <TableRow><TableHead>공급사</TableHead><TableHead>시작일</TableHead><TableHead>종료일</TableHead><TableHead>조건</TableHead><TableHead>상태</TableHead></TableRow>
              </TableHeader>
              <TableBody>
                {(contracts.data ?? []).map((c) => (
                  <TableRow key={c.contract_id}>
                    <TableCell>{c.vendor_name}</TableCell>
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

      {tab === 'category' && (
        <div className="space-y-4">
          <p className="text-xs text-text-secondary">
            품목 유형(material_type) 기준 구매 집계입니다. 현재 데이터셋은 원자재(RM)/완제품(FG) 유형만
            보유하고 있어 부자재/설비/금형 구분은 향후 해당 유형 데이터가 등록되면 자동으로 반영됩니다.
          </p>
          <Card>
            <CardHeader><CardTitle>카테고리별 구매 요약</CardTitle></CardHeader>
            <Table>
              <TableHeader>
                <TableRow><TableHead>카테고리</TableHead><TableHead className="text-right">구매수량</TableHead><TableHead className="text-right">구매금액</TableHead><TableHead className="text-right">발주 건수</TableHead></TableRow>
              </TableHeader>
              <TableBody>
                {(byCategory.data ?? []).map((r, i) => (
                  <TableRow key={i}>
                    <TableCell>{r.category}</TableCell>
                    <TableCell className="text-right">{r.total_qty.toLocaleString()}</TableCell>
                    <TableCell className="text-right">{currency(r.total_amount)}</TableCell>
                    <TableCell className="text-right">{r.po_count ?? '-'}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Card>
        </div>
      )}

      {tab === 'customs' && (
        <div className="space-y-4">
          {canWrite && (
            <Card>
              <CardHeader><CardTitle>통관 기록 등록</CardTitle></CardHeader>
              <form onSubmit={submitCustoms} className="grid grid-cols-2 gap-3">
                <Input placeholder="PO 번호 (예: 264 또는 PO-2026-00264)" value={customsPoId} onChange={(e) => setCustomsPoId(e.target.value)} />
                <Input placeholder="신고번호(선택)" value={customsDeclNo} onChange={(e) => setCustomsDeclNo(e.target.value)} />
                <Button type="submit" disabled={createCustoms.isPending} className="col-span-2">등록</Button>
              </form>
            </Card>
          )}
          <Card>
            <CardHeader><CardTitle>통관 기록 목록</CardTitle></CardHeader>
            <Table>
              <TableHeader>
                <TableRow><TableHead>PO#</TableHead><TableHead>공급사</TableHead><TableHead>신고번호</TableHead><TableHead>상태</TableHead>{canWrite && <TableHead>액션</TableHead>}</TableRow>
              </TableHeader>
              <TableBody>
                {(customsRecords.data ?? []).map((r) => (
                  <TableRow key={r.customs_id}>
                    <TableCell>{r.po_external_no ?? r.po_id}</TableCell>
                    <TableCell>{r.vendor_name}</TableCell>
                    <TableCell>{r.declaration_no ?? '-'}</TableCell>
                    <TableCell><StatusBadge status={r.customs_status} /></TableCell>
                    {canWrite && (
                      <TableCell>
                        <Select value={r.customs_status} onChange={(e) => updateCustomsStatus.mutate({ id: r.customs_id, status: e.target.value })}>
                          {['PENDING', 'DECLARED', 'CLEARED', 'HOLD'].map((st) => <option key={st} value={st}>{st}</option>)}
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
            <div className="grid grid-cols-5 gap-4">
              <KpiCard label="미승인 PR" value={kpi.data.open_pr_count} />
              <KpiCard label="진행중 PO" value={kpi.data.open_po_count} />
              <KpiCard label="이번달 구매액" value={currency(kpi.data.spend_this_month)} />
              <KpiCard label="공급사 수" value={kpi.data.vendor_count} />
              <KpiCard label="평균 공급사 점수" value={kpi.data.avg_vendor_score ?? '-'} />
            </div>
          )}
          <Card>
            <CardHeader>
              <CardTitle>구매실적</CardTitle>
              <Select value={perfGroupBy} onChange={(e) => setPerfGroupBy(e.target.value as typeof perfGroupBy)} className="w-40">
                <option value="vendor">공급사별</option>
                <option value="material">품목별</option>
                <option value="month">월별</option>
              </Select>
            </CardHeader>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{perfGroupBy === 'month' ? '월' : perfGroupBy === 'material' ? '품목' : '공급사'}</TableHead>
                  <TableHead className="text-right">구매금액</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {(performance.data ?? []).map((row, i) => (
                  <TableRow key={i}>
                    <TableCell>{row.group_label}</TableCell>
                    <TableCell className="text-right">{currency(row.total_amount)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Card>
        </div>
      )}
    </div>
  )
}
