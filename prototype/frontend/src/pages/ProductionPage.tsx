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
import { StatusBadge } from '@/components/StatusBadge'
import { ProductionResultPicker } from '@/components/ProductionResultPicker'
import { cn } from '@/lib/utils'
import type {
  Material, Plant, Warehouse, Vendor, ProductionOrder, ProductionResult, Lot,
  MrpResponse, OutsourcingRow, ReworkRow, ProductionCloseRow, OeeResponse, ProductionDashboard,
} from '@/lib/types'

// 05. Production Management (기존 오더/실적/QMS + v13: MRP/외주/재작업/생산마감/OEE/Dashboard)
const TABS = [
  { key: 'orders', label: '생산오더' },
  { key: 'mrp', label: 'MRP' },
  { key: 'outsourcing', label: '외주생산' },
  { key: 'rework', label: '재작업' },
  { key: 'close', label: '생산마감' },
  { key: 'oee', label: 'OEE 분석' },
  { key: 'dashboard', label: '생산 현황' },
] as const
type TabKey = (typeof TABS)[number]['key']

const currency = (n: number) => `₩${Math.round(n ?? 0).toLocaleString()}`

export default function ProductionPage() {
  const { hasRole } = useAuth()
  const canWrite = hasRole('생산담당', '관리자')
  const isAdmin = hasRole('관리자')
  const qc = useQueryClient()
  const [tab, setTab] = useState<TabKey>('orders')
  const [error, setError] = useState('')
  const [msg, setMsg] = useState('')

  const materials = useQuery({ queryKey: ['materials'], queryFn: () => apiGet<Material[]>('/api/materials') })
  const plants = useQuery({ queryKey: ['plants'], queryFn: () => apiGet<Plant[]>('/api/plants') })
  const warehouses = useQuery({ queryKey: ['warehouses'], queryFn: () => apiGet<Warehouse[]>('/api/warehouses') })
  const vendors = useQuery({ queryKey: ['vendors'], queryFn: () => apiGet<Vendor[]>('/api/vendors') })
  const prodOrders = useQuery({
    queryKey: ['production-orders'],
    queryFn: () => apiGet<ProductionOrder[]>('/api/production-orders'),
  })
  const fgMaterials = (materials.data ?? []).filter((m) => m.material_type !== 'RM')

  // 오더별로 마지막 생성된 work_order_id를 들고 있어야 실적입력이 가능(기존 static의 LAST_WORK_ORDER와 동일 개념)
  const [lastWorkOrder, setLastWorkOrder] = useState<Record<number, number>>({})

  const [prodMaterialId, setProdMaterialId] = useState<number | null>(null)
  const [prodPlantId, setProdPlantId] = useState<number | null>(null)
  const [prodQty, setProdQty] = useState(10)
  const [prodOutsourced, setProdOutsourced] = useState(false)
  const [prodVendorId, setProdVendorId] = useState('')

  const createProdOrder = useMutation({
    mutationFn: (body: { material_id: number; plant_id: number; qty: number; is_outsourced?: boolean; vendor_id?: number }) =>
      apiPost('/api/production-orders', body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['production-orders'] }),
  })
  const startWork = useMutation({
    mutationFn: (prodOrderId: number) =>
      apiPost<{ work_order_id: number }>(`/api/production-orders/${prodOrderId}/work-orders`, {}),
    onSuccess: (data, prodOrderId) => {
      setLastWorkOrder((prev) => ({ ...prev, [prodOrderId]: data.work_order_id }))
      qc.invalidateQueries({ queryKey: ['production-orders'] })
      setMsg(`작업지시가 생성되었습니다 (WO#${data.work_order_id})`)
    },
  })
  const enterResult = useMutation({
    mutationFn: ({
      workOrderId,
      qtyGood,
      warehouseId,
      generateSerials,
    }: {
      workOrderId: number
      qtyGood: number
      warehouseId: number
      generateSerials: boolean
    }) =>
      apiPost<ProductionResult>(`/api/work-orders/${workOrderId}/results`, {
        qty_good: qtyGood,
        warehouse_id: warehouseId,
        generate_serials: generateSerials,
      }),
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ['production-orders'] })
      const lotMsg = data.lot ? ` (LOT ${data.lot.lot_no}${data.serials?.length ? `, 시리얼 ${data.serials.length}건` : ''})` : ''
      setMsg(`생산실적이 반영되었습니다 (재고 증가)${lotMsg}.`)
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : '실적 입력 실패'),
  })

  async function submitProdOrder(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    setError('')
    setMsg('')
    if (!prodMaterialId || !prodPlantId) {
      setError('완제품과 공장을 선택하세요')
      return
    }
    if (prodOutsourced && !prodVendorId) {
      setError('외주생산은 외주처를 선택해야 합니다')
      return
    }
    try {
      await createProdOrder.mutateAsync({
        material_id: prodMaterialId, plant_id: prodPlantId, qty: prodQty,
        is_outsourced: prodOutsourced || undefined,
        vendor_id: prodVendorId ? Number(prodVendorId) : undefined,
      })
      setMsg('생산오더가 등록되었습니다.')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : '등록 실패')
    }
  }

  function handleResultConfirm(prodOrderId: number, qty: number, warehouseId: number, generateSerials: boolean) {
    const workOrderId = lastWorkOrder[prodOrderId]
    if (!workOrderId) {
      setError('먼저 작업지시를 생성하세요.')
      return
    }
    setError('')
    enterResult.mutate({ workOrderId, qtyGood: qty, warehouseId, generateSerials })
  }

  // ---------- QMS 품질검사 등록 ----------
  const [qiMaterialId, setQiMaterialId] = useState<number | null>(null)
  const [qiLotId, setQiLotId] = useState<string>('')
  const [qiType, setQiType] = useState('FINAL')
  const [qiSample, setQiSample] = useState(10)
  const [qiDefect, setQiDefect] = useState(0)
  const [qiResult, setQiResult] = useState('PASS')
  const [qiCapa, setQiCapa] = useState('N')

  const qiLots = useQuery({
    queryKey: ['lots-active', qiMaterialId],
    queryFn: () => apiGet<Lot[]>(`/api/lots?material_id=${qiMaterialId}&status=ACTIVE`),
    enabled: qiMaterialId != null,
  })

  const createInspection = useMutation({
    mutationFn: (body: Record<string, unknown>) => apiPost('/api/quality/inspections', body),
  })

  async function submitInspection(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    setError('')
    setMsg('')
    if (!qiMaterialId) {
      setError('품목을 선택하세요')
      return
    }
    try {
      await createInspection.mutateAsync({
        material_id: qiMaterialId,
        lot_id: qiLotId ? Number(qiLotId) : null,
        inspection_type: qiType,
        sample_qty: qiSample,
        defect_qty: qiDefect,
        result: qiResult,
        capa_required: qiCapa,
      })
      setMsg('품질검사가 등록되었습니다.')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : '등록 실패')
    }
  }

  // ---------- v13: MRP / 외주 / 재작업 / 마감 / OEE / Dashboard ----------
  const mrp = useQuery({
    queryKey: ['production-mrp'],
    queryFn: () => apiGet<MrpResponse>('/api/production/mrp'),
    enabled: tab === 'mrp',
  })
  const outsourcing = useQuery({
    queryKey: ['production-outsourcing'],
    queryFn: () => apiGet<OutsourcingRow[]>('/api/production/outsourcing'),
    enabled: tab === 'outsourcing',
  })
  const reworks = useQuery({
    queryKey: ['production-reworks'],
    queryFn: () => apiGet<ReworkRow[]>('/api/production/reworks'),
    enabled: tab === 'rework',
  })
  const closes = useQuery({
    queryKey: ['production-closes'],
    queryFn: () => apiGet<ProductionCloseRow[]>('/api/production/closes'),
    enabled: tab === 'close',
  })
  const oee = useQuery({
    queryKey: ['production-oee'],
    queryFn: () => apiGet<OeeResponse>('/api/production/oee'),
    enabled: tab === 'oee',
  })
  const dashboard = useQuery({
    queryKey: ['production-dashboard'],
    queryFn: () => apiGet<ProductionDashboard>('/api/production/dashboard'),
    enabled: tab === 'dashboard',
  })

  const [rwSerialNo, setRwSerialNo] = useState('')
  const [rwReason, setRwReason] = useState('')
  const createRework = useMutation({
    mutationFn: (body: { serial_no: string; reason?: string }) => apiPost('/api/production/reworks', body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['production-reworks'] })
      setRwSerialNo('')
      setRwReason('')
      setError('')
      setMsg('재작업이 등록되었습니다.')
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : '등록 실패'),
  })
  const completeRework = useMutation({
    mutationFn: ({ id, result }: { id: number; result: string }) =>
      apiPost(`/api/production/reworks/${id}/complete`, { result }),
    onSuccess: (_d, v) => {
      qc.invalidateQueries({ queryKey: ['production-reworks'] })
      setMsg(v.result === 'REWORKED' ? '재작업 완료 — 시리얼이 IN_STOCK으로 복귀했습니다.' : '폐기 처리되었습니다.')
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : '처리 실패'),
  })

  const [closePeriod, setClosePeriod] = useState('')
  const closeMutation = useMutation({
    mutationFn: (body: { period: string }) => apiPost('/api/production/close', body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['production-closes'] })
      setError('')
      setMsg('생산마감 완료 — 해당월 실적 입력이 잠기고 회계 전표가 생성되었습니다.')
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : '마감 실패'),
  })

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold text-text-primary">생산</h1>
      {error && <p className="text-xs text-danger">{error}</p>}
      {msg && <p className="text-xs text-success">{msg}</p>}

      <div className="flex flex-wrap gap-1 border-b border-border-default pb-2">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={cn(
              'rounded-md px-3 py-1.5 text-xs font-medium transition-colors',
              tab === t.key ? 'bg-brand-50 text-brand-600' : 'text-text-secondary hover:text-text-primary',
            )}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === 'orders' && (
        <div className="space-y-6">
          {canWrite && (
            <Card>
              <CardHeader>
                <CardTitle>생산오더 등록</CardTitle>
              </CardHeader>
              <form onSubmit={submitProdOrder} className="flex flex-wrap items-end gap-3">
                <div className="w-56">
                  <label className="mb-1 block text-xs text-text-secondary">완제품</label>
                  <Select value={prodMaterialId ?? ''} onChange={(e) => setProdMaterialId(Number(e.target.value))}>
                    <option value="">선택</option>
                    {fgMaterials.map((m) => (
                      <option key={m.material_id} value={m.material_id}>
                        {m.name}
                      </option>
                    ))}
                  </Select>
                </div>
                <div className="w-40">
                  <label className="mb-1 block text-xs text-text-secondary">공장</label>
                  <Select value={prodPlantId ?? ''} onChange={(e) => setProdPlantId(Number(e.target.value))}>
                    <option value="">선택</option>
                    {(plants.data ?? []).map((p) => (
                      <option key={p.plant_id} value={p.plant_id}>
                        {p.name}
                      </option>
                    ))}
                  </Select>
                </div>
                <div className="w-24">
                  <label className="mb-1 block text-xs text-text-secondary">수량</label>
                  <Input type="number" value={prodQty} onChange={(e) => setProdQty(Number(e.target.value))} />
                </div>
                <div className="w-32">
                  <label className="mb-1 block text-xs text-text-secondary">생산구분</label>
                  <Select
                    value={prodOutsourced ? 'OUT' : 'IN'}
                    onChange={(e) => setProdOutsourced(e.target.value === 'OUT')}
                  >
                    <option value="IN">자체생산</option>
                    <option value="OUT">외주생산</option>
                  </Select>
                </div>
                {prodOutsourced && (
                  <div className="w-48">
                    <label className="mb-1 block text-xs text-text-secondary">외주처</label>
                    <Select value={prodVendorId} onChange={(e) => setProdVendorId(e.target.value)}>
                      <option value="">선택</option>
                      {(vendors.data ?? []).map((v) => (
                        <option key={v.vendor_id} value={v.vendor_id}>{v.name}</option>
                      ))}
                    </Select>
                  </div>
                )}
                <Button type="submit" disabled={createProdOrder.isPending}>
                  생산오더 등록
                </Button>
              </form>
            </Card>
          )}

          <Card>
            <CardHeader>
              <CardTitle>생산오더 목록</CardTitle>
            </CardHeader>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>오더#</TableHead>
                  <TableHead>원본번호</TableHead>
                  <TableHead>완제품</TableHead>
                  <TableHead className="text-right">수량</TableHead>
                  <TableHead>구분</TableHead>
                  <TableHead>상태</TableHead>
                  {canWrite && <TableHead>액션</TableHead>}
                </TableRow>
              </TableHeader>
              <TableBody>
                {(prodOrders.data ?? []).map((po) => (
                  <TableRow key={po.prod_order_id}>
                    <TableCell>{po.prod_order_id}</TableCell>
                    <TableCell>{po.external_no}</TableCell>
                    <TableCell>{po.material_name}</TableCell>
                    <TableCell className="text-right">{po.qty}</TableCell>
                    <TableCell>{po.is_outsourced ? `외주(${po.vendor_name ?? '-'})` : '자체'}</TableCell>
                    <TableCell>
                      <StatusBadge status={po.status} />
                    </TableCell>
                    {canWrite && (
                      <TableCell>
                        {po.status === 'PLANNED' && (
                          <Button type="button" size="sm" variant="outline" onClick={() => startWork.mutate(po.prod_order_id)}>
                            작업지시
                          </Button>
                        )}
                        {po.status === 'IN_PROGRESS' && (
                          <ProductionResultPicker
                            warehouses={warehouses.data ?? []}
                            plants={plants.data ?? []}
                            preferredPlantId={po.plant_id}
                            onConfirm={(qty, warehouseId, generateSerials) =>
                              handleResultConfirm(po.prod_order_id, qty, warehouseId, generateSerials)
                            }
                          />
                        )}
                      </TableCell>
                    )}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Card>

          {canWrite && (
            <Card>
              <CardHeader>
                <CardTitle>품질검사 등록 (QMS)</CardTitle>
              </CardHeader>
              <form onSubmit={submitInspection} className="flex flex-wrap items-end gap-3">
                <div className="w-56">
                  <label className="mb-1 block text-xs text-text-secondary">품목</label>
                  <Select
                    value={qiMaterialId ?? ''}
                    onChange={(e) => {
                      setQiMaterialId(Number(e.target.value))
                      setQiLotId('')
                    }}
                  >
                    <option value="">선택</option>
                    {(materials.data ?? []).map((m) => (
                      <option key={m.material_id} value={m.material_id}>
                        {m.name}
                      </option>
                    ))}
                  </Select>
                </div>
                <div className="w-56">
                  <label className="mb-1 block text-xs text-text-secondary">LOT(선택)</label>
                  <Select value={qiLotId} onChange={(e) => setQiLotId(e.target.value)}>
                    <option value="">-</option>
                    {(qiLots.data ?? []).map((l) => (
                      <option key={l.lot_id} value={l.lot_id}>
                        {l.lot_no} (잔여 {l.qty})
                      </option>
                    ))}
                  </Select>
                </div>
                <div className="w-32">
                  <label className="mb-1 block text-xs text-text-secondary">검사유형</label>
                  <Input value={qiType} onChange={(e) => setQiType(e.target.value)} required />
                </div>
                <div className="w-24">
                  <label className="mb-1 block text-xs text-text-secondary">샘플수량</label>
                  <Input type="number" value={qiSample} onChange={(e) => setQiSample(Number(e.target.value))} required />
                </div>
                <div className="w-24">
                  <label className="mb-1 block text-xs text-text-secondary">불량수량</label>
                  <Input type="number" value={qiDefect} onChange={(e) => setQiDefect(Number(e.target.value))} />
                </div>
                <div className="w-28">
                  <label className="mb-1 block text-xs text-text-secondary">결과</label>
                  <Select value={qiResult} onChange={(e) => setQiResult(e.target.value)}>
                    <option value="PASS">PASS</option>
                    <option value="FAIL">FAIL</option>
                  </Select>
                </div>
                <div className="w-24">
                  <label className="mb-1 block text-xs text-text-secondary">CAPA 필요</label>
                  <Select value={qiCapa} onChange={(e) => setQiCapa(e.target.value)}>
                    <option value="N">N</option>
                    <option value="Y">Y</option>
                  </Select>
                </div>
                <Button type="submit" disabled={createInspection.isPending}>
                  검사 등록
                </Button>
              </form>
            </Card>
          )}
        </div>
      )}

      {tab === 'mrp' && (
        <Card>
          <CardHeader>
            <CardTitle>
              MRP — 자재소요계획 {mrp.data?.period ? `(수요예측 기준월: ${mrp.data.period})` : ''}
            </CardTitle>
          </CardHeader>
          <p className="px-4 pb-2 text-xs text-text-secondary">
            수요예측 × BOM 전개 소요량 대비 현재고+미입고 발주 잔량으로 부족분을 산출합니다.
            부족 자재의 발주는 구매 &gt; 발주관리 또는 AI Agent(Buyer 재발주 추천, 재발주점 기준 — 별개 로직)를 활용하세요.
          </p>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>자재</TableHead><TableHead>코드</TableHead>
                <TableHead className="text-right">소요량</TableHead>
                <TableHead className="text-right">현재고</TableHead>
                <TableHead className="text-right">미입고 PO</TableHead>
                <TableHead className="text-right">부족분</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(mrp.data?.rows ?? []).map((r) => (
                <TableRow key={r.material_id} className={r.shortage > 0 ? 'bg-danger/5' : undefined}>
                  <TableCell>{r.name}</TableCell>
                  <TableCell>{r.code ?? '-'}</TableCell>
                  <TableCell className="text-right">{Math.round(r.requirement).toLocaleString()}</TableCell>
                  <TableCell className="text-right">{Math.round(r.onhand).toLocaleString()}</TableCell>
                  <TableCell className="text-right">{Math.round(r.incoming).toLocaleString()}</TableCell>
                  <TableCell className={cn('text-right font-medium', r.shortage > 0 && 'text-danger')}>
                    {Math.round(r.shortage).toLocaleString()}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Card>
      )}

      {tab === 'outsourcing' && (
        <Card>
          <CardHeader><CardTitle>외주생산 현황 (등록은 생산오더 탭에서 생산구분=외주생산 선택)</CardTitle></CardHeader>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>오더#</TableHead><TableHead>원본번호</TableHead><TableHead>완제품</TableHead>
                <TableHead className="text-right">수량</TableHead><TableHead>외주처</TableHead>
                <TableHead>일자</TableHead><TableHead>상태</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(outsourcing.data ?? []).map((o) => (
                <TableRow key={o.prod_order_id}>
                  <TableCell>{o.prod_order_id}</TableCell>
                  <TableCell>{o.external_no ?? '-'}</TableCell>
                  <TableCell>{o.material_name}</TableCell>
                  <TableCell className="text-right">{o.qty}</TableCell>
                  <TableCell>{o.vendor_name ?? '-'}</TableCell>
                  <TableCell>{o.order_date}</TableCell>
                  <TableCell><StatusBadge status={o.status} /></TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Card>
      )}

      {tab === 'rework' && (
        <>
          {canWrite && (
            <Card>
              <CardHeader><CardTitle>재작업 등록 (DEFECTIVE 시리얼만 — 재고 &gt; 시리얼추적에서 상태 확인)</CardTitle></CardHeader>
              <form
                onSubmit={async (e) => {
                  e.preventDefault()
                  if (!rwSerialNo.trim()) return setError('시리얼 번호를 입력하세요')
                  await createRework.mutateAsync({ serial_no: rwSerialNo.trim(), reason: rwReason.trim() || undefined })
                }}
                className="space-y-2 px-4 pb-4"
              >
                <div className="grid grid-cols-2 gap-2">
                  <Input placeholder="시리얼 번호" value={rwSerialNo} onChange={(e) => setRwSerialNo(e.target.value)} />
                  <Input placeholder="사유(선택)" value={rwReason} onChange={(e) => setRwReason(e.target.value)} />
                </div>
                <Button type="submit" className="w-full" disabled={createRework.isPending}>재작업 등록</Button>
              </form>
            </Card>
          )}
          <Card>
            <CardHeader><CardTitle>재작업 목록</CardTitle></CardHeader>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>시리얼</TableHead><TableHead>품목</TableHead><TableHead>사유</TableHead>
                  <TableHead>등록일</TableHead><TableHead>상태</TableHead><TableHead>시리얼 상태</TableHead>
                  {canWrite && <TableHead>액션</TableHead>}
                </TableRow>
              </TableHeader>
              <TableBody>
                {(reworks.data ?? []).map((r) => (
                  <TableRow key={r.rework_id}>
                    <TableCell>{r.serial_no}</TableCell>
                    <TableCell>{r.material_name}</TableCell>
                    <TableCell>{r.reason ?? '-'}</TableCell>
                    <TableCell>{r.created_date}</TableCell>
                    <TableCell><StatusBadge status={r.status} /></TableCell>
                    <TableCell><StatusBadge status={r.serial_status} /></TableCell>
                    {canWrite && (
                      <TableCell>
                        {r.status === 'OPEN' && (
                          <div className="flex gap-1">
                            <Button
                              size="sm" variant="success"
                              onClick={() => completeRework.mutate({ id: r.rework_id, result: 'REWORKED' })}
                            >
                              재투입
                            </Button>
                            <Button
                              size="sm" variant="danger"
                              onClick={() => completeRework.mutate({ id: r.rework_id, result: 'SCRAPPED' })}
                            >
                              폐기
                            </Button>
                          </div>
                        )}
                      </TableCell>
                    )}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Card>
        </>
      )}

      {tab === 'close' && (
        <>
          {isAdmin && (
            <Card>
              <CardHeader><CardTitle>생산마감 실행 (관리자 — 마감 후 해당월 실적입력 잠금 + FI 전표)</CardTitle></CardHeader>
              <form
                onSubmit={async (e) => {
                  e.preventDefault()
                  if (!/^\d{4}-\d{2}$/.test(closePeriod)) return setError('마감월을 YYYY-MM 형식으로 입력하세요')
                  await closeMutation.mutateAsync({ period: closePeriod })
                }}
                className="flex items-end gap-2 px-4 pb-4"
              >
                <div className="w-40">
                  <label className="mb-1 block text-xs text-text-secondary">마감월 (YYYY-MM)</label>
                  <Input placeholder="2026-06" value={closePeriod} onChange={(e) => setClosePeriod(e.target.value)} />
                </div>
                <Button type="submit" disabled={closeMutation.isPending}>마감 실행</Button>
              </form>
            </Card>
          )}
          <Card>
            <CardHeader><CardTitle>마감 이력</CardTitle></CardHeader>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>마감월</TableHead>
                  <TableHead className="text-right">양품</TableHead>
                  <TableHead className="text-right">불량</TableHead>
                  <TableHead className="text-right">마감금액(표준원가)</TableHead>
                  <TableHead>전표</TableHead><TableHead>마감일</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {(closes.data ?? []).map((c) => (
                  <TableRow key={c.close_id}>
                    <TableCell>{c.period}</TableCell>
                    <TableCell className="text-right">{Math.round(c.total_good).toLocaleString()}</TableCell>
                    <TableCell className="text-right">{Math.round(c.total_defect).toLocaleString()}</TableCell>
                    <TableCell className="text-right">{currency(c.close_amount)}</TableCell>
                    <TableCell>{c.acct_doc_id ?? '-'}</TableCell>
                    <TableCell>{c.closed_date}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Card>
        </>
      )}

      {tab === 'oee' && (
        <>
          <Card>
            <CardHeader><CardTitle>OEE 실측 집계 (월 × 공장, 생산실적 기반)</CardTitle></CardHeader>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>월</TableHead><TableHead>공장</TableHead>
                  <TableHead className="text-right">OEE</TableHead>
                  <TableHead className="text-right">가동률</TableHead>
                  <TableHead className="text-right">성능</TableHead>
                  <TableHead className="text-right">품질률</TableHead>
                  <TableHead className="text-right">실적 건수</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {(oee.data?.measured ?? []).map((r, i) => (
                  <TableRow key={i}>
                    <TableCell>{r.period}</TableCell>
                    <TableCell>{r.plant_name}</TableCell>
                    <TableCell className={cn('text-right font-medium', (r.avg_oee ?? 0) < 70 && 'text-danger')}>
                      {r.avg_oee ?? '-'}
                    </TableCell>
                    <TableCell className="text-right">{r.avg_availability ?? '-'}</TableCell>
                    <TableCell className="text-right">{r.avg_performance ?? '-'}</TableCell>
                    <TableCell className="text-right">{r.avg_quality_rate ?? '-'}</TableCell>
                    <TableCell className="text-right">{r.result_count}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Card>
          <Card>
            <CardHeader><CardTitle>KPI 월별 OEE 평균 (참고 데이터)</CardTitle></CardHeader>
            <Table>
              <TableHeader>
                <TableRow><TableHead>월</TableHead><TableHead className="text-right">OEE 평균</TableHead></TableRow>
              </TableHeader>
              <TableBody>
                {(oee.data?.reference ?? []).map((r) => (
                  <TableRow key={r.period}>
                    <TableCell>{r.period}</TableCell>
                    <TableCell className="text-right">{r.oee_avg}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Card>
        </>
      )}

      {tab === 'dashboard' && (
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          <KpiCard label="미완료 생산오더" value={String(dashboard.data?.open_order_count ?? '-')} />
          <KpiCard label="외주생산 오더" value={String(dashboard.data?.outsourced_count ?? '-')} />
          <KpiCard label="당월 양품" value={String(Math.round(dashboard.data?.month_good ?? 0).toLocaleString())} />
          <KpiCard
            label="당월 불량률"
            value={`${dashboard.data?.month_defect_rate ?? 0}%`}
            tone={(dashboard.data?.month_defect_rate ?? 0) > 3 ? 'danger' : 'default'}
          />
          <KpiCard
            label="진행 중 재작업"
            value={String(dashboard.data?.open_rework_count ?? '-')}
            tone={(dashboard.data?.open_rework_count ?? 0) > 0 ? 'warning' : 'default'}
          />
          <KpiCard label="최근 마감월" value={dashboard.data?.last_closed_period ?? '없음'} />
          <KpiCard label="평균 OEE (전체)" value={String(dashboard.data?.avg_oee ?? '-')} />
        </div>
      )}
    </div>
  )
}
