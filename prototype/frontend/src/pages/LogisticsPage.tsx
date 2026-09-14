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
import { cn } from '@/lib/utils'
import type {
  Warehouse, WarehouseLocationRow, ContainerRow, TransportRow, LogisticsCostRow,
  ExportStatusRow, InsurancePolicyRow, LogisticsClaimRow, LogisticsDashboard,
} from '@/lib/types'

// 04. Logistics Management (v12) — task-plan-v9-full-menu-rollout.md §3 v12
const TABS = [
  { key: 'dashboard', label: '물류 현황' },
  { key: 'locations', label: '창고 Location' },
  { key: 'containers', label: '컨테이너' },
  { key: 'transports', label: '운송관리' },
  { key: 'costs', label: '물류비 정산' },
  { key: 'export', label: '수출 현황' },
  { key: 'insurance', label: '보험·클레임' },
] as const
type TabKey = (typeof TABS)[number]['key']

const LOCATION_TYPES = ['BIN', 'RACK', 'ZONE']
const CONTAINER_TYPES = ['20FT', '40FT', '40HC', 'LCL']
const CONTAINER_STATUSES = ['EMPTY', 'STUFFING', 'SEALED', 'SHIPPED', 'RETURNED']
const TRANSPORT_STATUSES = ['PLANNED', 'IN_TRANSIT', 'DELIVERED']
const COST_TYPES = [
  { value: 'FREIGHT', label: '운송비' },
  { value: 'INSURANCE', label: '보험료' },
  { value: 'CUSTOMS', label: '통관비' },
  { value: 'HANDLING', label: '하역비' },
  { value: 'OTHER', label: '기타' },
]
const CLAIM_TYPES = [
  { value: 'DAMAGE', label: '파손' },
  { value: 'LOSS', label: '분실' },
  { value: 'DELAY', label: '지연' },
  { value: 'OTHER', label: '기타' },
]
const CLAIM_STATUSES = ['OPEN', 'RESOLVED', 'REJECTED']
const currency = (n: number) => `₩${Math.round(n ?? 0).toLocaleString()}`

export default function LogisticsPage() {
  const { hasRole } = useAuth()
  const canWrite = hasRole('영업담당', '관리자')
  const isAdmin = hasRole('관리자')
  const qc = useQueryClient()
  const [tab, setTab] = useState<TabKey>('dashboard')
  const [error, setError] = useState('')
  const [msg, setMsg] = useState('')

  function flash(text: string) {
    setError('')
    setMsg(text)
  }
  function fail(err: unknown, fallback: string) {
    setMsg('')
    setError(err instanceof ApiError ? err.message : fallback)
  }

  // 공용: 출하 목록(드롭다운 소스) — 수출 현황 API 재사용(신규 API 없이)
  const shipments = useQuery({
    queryKey: ['logistics-export-status'],
    queryFn: () => apiGet<ExportStatusRow[]>('/api/logistics/export-status'),
  })

  // ---------- 물류 현황 ----------
  const dashboard = useQuery({
    queryKey: ['logistics-dashboard'],
    queryFn: () => apiGet<LogisticsDashboard>('/api/logistics/dashboard'),
    enabled: tab === 'dashboard',
  })

  // ---------- 창고 Location ----------
  const warehouses = useQuery({ queryKey: ['warehouses'], queryFn: () => apiGet<Warehouse[]>('/api/warehouses') })
  const locations = useQuery({
    queryKey: ['logistics-locations'],
    queryFn: () => apiGet<WarehouseLocationRow[]>('/api/logistics/locations'),
    enabled: tab === 'locations',
  })
  const [locWarehouseId, setLocWarehouseId] = useState('')
  const [locCode, setLocCode] = useState('')
  const [locName, setLocName] = useState('')
  const [locType, setLocType] = useState('BIN')
  const createLocation = useMutation({
    mutationFn: (body: { warehouse_id: number; code: string; name?: string; location_type: string }) =>
      apiPost('/api/logistics/locations', body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['logistics-locations'] })
      setLocCode('')
      setLocName('')
      flash('Location이 등록되었습니다.')
    },
    onError: (err) => fail(err, '등록 실패'),
  })
  async function submitLocation(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    if (!locWarehouseId || !locCode.trim()) return fail(null, '창고와 Location 코드를 입력하세요')
    await createLocation.mutateAsync({
      warehouse_id: Number(locWarehouseId), code: locCode.trim(),
      name: locName.trim() || undefined, location_type: locType,
    })
  }

  // ---------- 컨테이너 ----------
  const containers = useQuery({
    queryKey: ['logistics-containers'],
    queryFn: () => apiGet<ContainerRow[]>('/api/logistics/containers'),
    enabled: tab === 'containers',
  })
  const [ctNo, setCtNo] = useState('')
  const [ctType, setCtType] = useState('40FT')
  const [ctShipmentId, setCtShipmentId] = useState('')
  const createContainer = useMutation({
    mutationFn: (body: { container_no: string; container_type: string; shipment_id?: number }) =>
      apiPost('/api/logistics/containers', body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['logistics-containers'] })
      setCtNo('')
      flash('컨테이너가 등록되었습니다.')
    },
    onError: (err) => fail(err, '등록 실패'),
  })
  const updateContainerStatus = useMutation({
    mutationFn: ({ id, status }: { id: number; status: string }) =>
      apiPost(`/api/logistics/containers/${id}/status`, { status }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['logistics-containers'] }),
    onError: (err) => fail(err, '상태 변경 실패'),
  })
  async function submitContainer(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    if (!ctNo.trim()) return fail(null, '컨테이너 번호를 입력하세요')
    await createContainer.mutateAsync({
      container_no: ctNo.trim(), container_type: ctType,
      shipment_id: ctShipmentId ? Number(ctShipmentId) : undefined,
    })
  }

  // ---------- 운송관리 ----------
  const transports = useQuery({
    queryKey: ['logistics-transports'],
    queryFn: () => apiGet<TransportRow[]>('/api/logistics/transports'),
    enabled: tab === 'transports',
  })
  const [trShipmentId, setTrShipmentId] = useState('')
  const [trCarrier, setTrCarrier] = useState('')
  const [trVehicleNo, setTrVehicleNo] = useState('')
  const [trDriver, setTrDriver] = useState('')
  const [trCost, setTrCost] = useState('')
  const createTransport = useMutation({
    mutationFn: (body: { shipment_id: number; carrier?: string; vehicle_no?: string; driver?: string; freight_cost?: number }) =>
      apiPost('/api/logistics/transports', body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['logistics-transports'] })
      setTrCarrier('')
      setTrVehicleNo('')
      setTrDriver('')
      setTrCost('')
      flash('운송(배차) 기록이 등록되었습니다.')
    },
    onError: (err) => fail(err, '등록 실패'),
  })
  const updateTransportStatus = useMutation({
    mutationFn: ({ id, status }: { id: number; status: string }) =>
      apiPost(`/api/logistics/transports/${id}/status`, { status }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['logistics-transports'] }),
    onError: (err) => fail(err, '상태 변경 실패'),
  })
  async function submitTransport(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    if (!trShipmentId) return fail(null, '출하를 선택하세요')
    await createTransport.mutateAsync({
      shipment_id: Number(trShipmentId),
      carrier: trCarrier.trim() || undefined,
      vehicle_no: trVehicleNo.trim() || undefined,
      driver: trDriver.trim() || undefined,
      freight_cost: trCost ? Number(trCost) : undefined,
    })
  }

  // ---------- 물류비 정산 ----------
  const costs = useQuery({
    queryKey: ['logistics-costs'],
    queryFn: () => apiGet<LogisticsCostRow[]>('/api/logistics/costs'),
    enabled: tab === 'costs',
  })
  const [costType, setCostType] = useState('FREIGHT')
  const [costAmount, setCostAmount] = useState('')
  const [costShipmentId, setCostShipmentId] = useState('')
  const [costNotes, setCostNotes] = useState('')
  const createCost = useMutation({
    mutationFn: (body: { cost_type: string; amount: number; shipment_id?: number; notes?: string }) =>
      apiPost('/api/logistics/costs', body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['logistics-costs'] })
      setCostAmount('')
      setCostNotes('')
      flash('물류비가 등록되었습니다.')
    },
    onError: (err) => fail(err, '등록 실패'),
  })
  const settleCost = useMutation({
    mutationFn: (id: number) => apiPost(`/api/logistics/costs/${id}/settle`, {}),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['logistics-costs'] })
      flash('정산 완료 — 회계 전표가 생성되었습니다.')
    },
    onError: (err) => fail(err, '정산 실패'),
  })
  async function submitCost(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const amount = Number(costAmount)
    if (!amount || amount <= 0) return fail(null, '금액을 입력하세요')
    await createCost.mutateAsync({
      cost_type: costType, amount,
      shipment_id: costShipmentId ? Number(costShipmentId) : undefined,
      notes: costNotes.trim() || undefined,
    })
  }

  // ---------- 보험·클레임 ----------
  const insurance = useQuery({
    queryKey: ['logistics-insurance'],
    queryFn: () => apiGet<InsurancePolicyRow[]>('/api/logistics/insurance'),
    enabled: tab === 'insurance',
  })
  const claims = useQuery({
    queryKey: ['logistics-claims'],
    queryFn: () => apiGet<LogisticsClaimRow[]>('/api/logistics/claims'),
    enabled: tab === 'insurance',
  })
  const [polNo, setPolNo] = useState('')
  const [polInsurer, setPolInsurer] = useState('')
  const [polCoverage, setPolCoverage] = useState('')
  const [polFrom, setPolFrom] = useState('')
  const [polTo, setPolTo] = useState('')
  const createInsurance = useMutation({
    mutationFn: (body: { policy_no: string; insurer: string; coverage?: string; valid_from?: string; valid_to?: string }) =>
      apiPost('/api/logistics/insurance', body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['logistics-insurance'] })
      setPolNo('')
      setPolInsurer('')
      setPolCoverage('')
      flash('보험이 등록되었습니다.')
    },
    onError: (err) => fail(err, '등록 실패'),
  })
  async function submitInsurance(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    if (!polNo.trim() || !polInsurer.trim()) return fail(null, '증권번호와 보험사를 입력하세요')
    await createInsurance.mutateAsync({
      policy_no: polNo.trim(), insurer: polInsurer.trim(),
      coverage: polCoverage.trim() || undefined,
      valid_from: polFrom || undefined, valid_to: polTo || undefined,
    })
  }
  const [clType, setClType] = useState('DAMAGE')
  const [clShipmentId, setClShipmentId] = useState('')
  const [clAmount, setClAmount] = useState('')
  const [clNotes, setClNotes] = useState('')
  const createClaim = useMutation({
    mutationFn: (body: { claim_type: string; shipment_id?: number; amount?: number; notes?: string }) =>
      apiPost('/api/logistics/claims', body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['logistics-claims'] })
      setClAmount('')
      setClNotes('')
      flash('클레임이 등록되었습니다.')
    },
    onError: (err) => fail(err, '등록 실패'),
  })
  const updateClaimStatus = useMutation({
    mutationFn: ({ id, status }: { id: number; status: string }) =>
      apiPost(`/api/logistics/claims/${id}/status`, { status }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['logistics-claims'] }),
    onError: (err) => fail(err, '상태 변경 실패'),
  })
  async function submitClaim(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    await createClaim.mutateAsync({
      claim_type: clType,
      shipment_id: clShipmentId ? Number(clShipmentId) : undefined,
      amount: clAmount ? Number(clAmount) : undefined,
      notes: clNotes.trim() || undefined,
    })
  }

  const shipmentOptions = (shipments.data ?? []).map((s) => (
    <option key={s.shipment_id} value={s.shipment_id}>
      {s.external_no ?? `#${s.shipment_id}`} — {s.customer_name ?? '-'}
    </option>
  ))

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold text-text-primary">물류</h1>
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

      {tab === 'dashboard' && (
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          <KpiCard label="출하 건수" value={String(dashboard.data?.shipment_count ?? '-')} />
          <KpiCard label="운송 중" value={String(dashboard.data?.transport_in_transit ?? '-')} />
          <KpiCard label="활성 컨테이너" value={String(dashboard.data?.container_active ?? '-')} />
          <KpiCard label="창고 Location" value={String(dashboard.data?.location_count ?? '-')} />
          <KpiCard
            label="미정산 물류비"
            value={dashboard.data ? currency(dashboard.data.unsettled_cost_amount) : '-'}
            hint={dashboard.data ? `${dashboard.data.unsettled_cost_count}건` : undefined}
            tone={dashboard.data && dashboard.data.unsettled_cost_count > 0 ? 'warning' : 'default'}
          />
          <KpiCard
            label="미결 클레임"
            value={String(dashboard.data?.open_claim_count ?? '-')}
            tone={dashboard.data && dashboard.data.open_claim_count > 0 ? 'danger' : 'default'}
          />
        </div>
      )}

      {tab === 'locations' && (
        <>
          {canWrite && (
            <Card>
              <CardHeader><CardTitle>Location 등록 (관리자)</CardTitle></CardHeader>
              <form onSubmit={submitLocation} className="space-y-2 px-4 pb-4">
                <Select value={locWarehouseId} onChange={(e) => setLocWarehouseId(e.target.value)}>
                  <option value="">창고 선택</option>
                  {(warehouses.data ?? []).map((w) => (
                    <option key={w.warehouse_id} value={w.warehouse_id}>{w.name}</option>
                  ))}
                </Select>
                <div className="grid grid-cols-3 gap-2">
                  <Input placeholder="Location 코드 (예: A-01-01)" value={locCode} onChange={(e) => setLocCode(e.target.value)} />
                  <Input placeholder="이름(선택)" value={locName} onChange={(e) => setLocName(e.target.value)} />
                  <Select value={locType} onChange={(e) => setLocType(e.target.value)}>
                    {LOCATION_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
                  </Select>
                </div>
                <Button type="submit" className="w-full" disabled={createLocation.isPending}>Location 등록</Button>
              </form>
            </Card>
          )}
          <Card>
            <CardHeader><CardTitle>Location 목록</CardTitle></CardHeader>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>창고</TableHead><TableHead>코드</TableHead><TableHead>이름</TableHead><TableHead>유형</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {(locations.data ?? []).map((l) => (
                  <TableRow key={l.location_id}>
                    <TableCell>{l.warehouse_name}</TableCell>
                    <TableCell>{l.code}</TableCell>
                    <TableCell>{l.name ?? '-'}</TableCell>
                    <TableCell>{l.location_type}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Card>
        </>
      )}

      {tab === 'containers' && (
        <>
          {canWrite && (
            <Card>
              <CardHeader><CardTitle>컨테이너 등록</CardTitle></CardHeader>
              <form onSubmit={submitContainer} className="space-y-2 px-4 pb-4">
                <div className="grid grid-cols-3 gap-2">
                  <Input placeholder="컨테이너 번호 (예: TCLU1234567)" value={ctNo} onChange={(e) => setCtNo(e.target.value)} />
                  <Select value={ctType} onChange={(e) => setCtType(e.target.value)}>
                    {CONTAINER_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
                  </Select>
                  <Select value={ctShipmentId} onChange={(e) => setCtShipmentId(e.target.value)}>
                    <option value="">출하 연결(선택)</option>
                    {shipmentOptions}
                  </Select>
                </div>
                <Button type="submit" className="w-full" disabled={createContainer.isPending}>컨테이너 등록</Button>
              </form>
            </Card>
          )}
          <Card>
            <CardHeader><CardTitle>컨테이너 목록</CardTitle></CardHeader>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>번호</TableHead><TableHead>유형</TableHead><TableHead>출하</TableHead><TableHead>상태</TableHead>
                  {canWrite && <TableHead>액션</TableHead>}
                </TableRow>
              </TableHeader>
              <TableBody>
                {(containers.data ?? []).map((c) => (
                  <TableRow key={c.container_id}>
                    <TableCell>{c.container_no}</TableCell>
                    <TableCell>{c.container_type}</TableCell>
                    <TableCell>{c.shipment_no ?? '-'}</TableCell>
                    <TableCell><StatusBadge status={c.status} /></TableCell>
                    {canWrite && (
                      <TableCell>
                        <Select
                          value={c.status}
                          onChange={(e) => updateContainerStatus.mutate({ id: c.container_id, status: e.target.value })}
                        >
                          {CONTAINER_STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
                        </Select>
                      </TableCell>
                    )}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Card>
        </>
      )}

      {tab === 'transports' && (
        <>
          {canWrite && (
            <Card>
              <CardHeader><CardTitle>운송(배차) 등록</CardTitle></CardHeader>
              <form onSubmit={submitTransport} className="space-y-2 px-4 pb-4">
                <Select value={trShipmentId} onChange={(e) => setTrShipmentId(e.target.value)}>
                  <option value="">출하 선택</option>
                  {shipmentOptions}
                </Select>
                <div className="grid grid-cols-4 gap-2">
                  <Input placeholder="운송사" value={trCarrier} onChange={(e) => setTrCarrier(e.target.value)} />
                  <Input placeholder="차량번호" value={trVehicleNo} onChange={(e) => setTrVehicleNo(e.target.value)} />
                  <Input placeholder="기사(선택)" value={trDriver} onChange={(e) => setTrDriver(e.target.value)} />
                  <Input type="number" placeholder="운송비(선택)" value={trCost} onChange={(e) => setTrCost(e.target.value)} />
                </div>
                <Button type="submit" className="w-full" disabled={createTransport.isPending}>배차 등록</Button>
              </form>
            </Card>
          )}
          <Card>
            <CardHeader><CardTitle>운송 목록</CardTitle></CardHeader>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>출하</TableHead><TableHead>운송사</TableHead><TableHead>차량</TableHead><TableHead>기사</TableHead>
                  <TableHead>일자</TableHead><TableHead className="text-right">운송비</TableHead><TableHead>상태</TableHead>
                  {canWrite && <TableHead>액션</TableHead>}
                </TableRow>
              </TableHeader>
              <TableBody>
                {(transports.data ?? []).map((t) => (
                  <TableRow key={t.transport_id}>
                    <TableCell>{t.shipment_no ?? t.shipment_id}</TableCell>
                    <TableCell>{t.carrier ?? '-'}</TableCell>
                    <TableCell>{t.vehicle_no ?? '-'}</TableCell>
                    <TableCell>{t.driver ?? '-'}</TableCell>
                    <TableCell>{t.transport_date}</TableCell>
                    <TableCell className="text-right">{t.freight_cost != null ? currency(t.freight_cost) : '-'}</TableCell>
                    <TableCell><StatusBadge status={t.status} /></TableCell>
                    {canWrite && (
                      <TableCell>
                        <Select
                          value={t.status}
                          onChange={(e) => updateTransportStatus.mutate({ id: t.transport_id, status: e.target.value })}
                        >
                          {TRANSPORT_STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
                        </Select>
                      </TableCell>
                    )}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Card>
        </>
      )}

      {tab === 'costs' && (
        <>
          {canWrite && (
            <Card>
              <CardHeader><CardTitle>물류비 등록</CardTitle></CardHeader>
              <form onSubmit={submitCost} className="space-y-2 px-4 pb-4">
                <div className="grid grid-cols-3 gap-2">
                  <Select value={costType} onChange={(e) => setCostType(e.target.value)}>
                    {COST_TYPES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
                  </Select>
                  <Input type="number" placeholder="금액" value={costAmount} onChange={(e) => setCostAmount(e.target.value)} />
                  <Select value={costShipmentId} onChange={(e) => setCostShipmentId(e.target.value)}>
                    <option value="">출하 연결(선택)</option>
                    {shipmentOptions}
                  </Select>
                </div>
                <Input placeholder="비고(선택)" value={costNotes} onChange={(e) => setCostNotes(e.target.value)} />
                <Button type="submit" className="w-full" disabled={createCost.isPending}>물류비 등록</Button>
              </form>
            </Card>
          )}
          <Card>
            <CardHeader><CardTitle>물류비 목록 {isAdmin ? '(정산 시 회계 전표 생성)' : ''}</CardTitle></CardHeader>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>유형</TableHead><TableHead className="text-right">금액</TableHead><TableHead>출하</TableHead>
                  <TableHead>일자</TableHead><TableHead>정산</TableHead><TableHead>전표</TableHead>
                  {isAdmin && <TableHead>액션</TableHead>}
                </TableRow>
              </TableHeader>
              <TableBody>
                {(costs.data ?? []).map((c) => (
                  <TableRow key={c.cost_id}>
                    <TableCell>{COST_TYPES.find((t) => t.value === c.cost_type)?.label ?? c.cost_type}</TableCell>
                    <TableCell className="text-right">{currency(c.amount)}</TableCell>
                    <TableCell>{c.shipment_no ?? '-'}</TableCell>
                    <TableCell>{c.cost_date}</TableCell>
                    <TableCell><StatusBadge status={c.settled ? 'SETTLED' : 'UNSETTLED'} /></TableCell>
                    <TableCell>{c.acct_doc_id ?? '-'}</TableCell>
                    {isAdmin && (
                      <TableCell>
                        {!c.settled && (
                          <Button
                            size="sm"
                            onClick={() => settleCost.mutate(c.cost_id)}
                            disabled={settleCost.isPending}
                          >
                            정산
                          </Button>
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

      {tab === 'export' && (
        <Card>
          <CardHeader><CardTitle>수출 현황 (출하 × 운송/컨테이너 연결 — 수입/통관은 구매 &gt; 통관관리 참고)</CardTitle></CardHeader>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>출하번호</TableHead><TableHead>일자</TableHead><TableHead>고객</TableHead><TableHead>품목</TableHead>
                <TableHead className="text-right">수량</TableHead><TableHead>운송사</TableHead>
                <TableHead className="text-right">운송</TableHead><TableHead className="text-right">컨테이너</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(shipments.data ?? []).map((s) => (
                <TableRow key={s.shipment_id}>
                  <TableCell>{s.external_no ?? s.shipment_id}</TableCell>
                  <TableCell>{s.shipment_date}</TableCell>
                  <TableCell>{s.customer_name ?? '-'}</TableCell>
                  <TableCell>{s.material_name ?? '-'}</TableCell>
                  <TableCell className="text-right">{s.shipped_qty ?? '-'}</TableCell>
                  <TableCell>{s.carrier ?? '-'}</TableCell>
                  <TableCell className="text-right">{s.transport_count}</TableCell>
                  <TableCell className="text-right">{s.container_count}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Card>
      )}

      {tab === 'insurance' && (
        <>
          {canWrite && (
            <div className="grid gap-4 lg:grid-cols-2">
              <Card>
                <CardHeader><CardTitle>보험 등록</CardTitle></CardHeader>
                <form onSubmit={submitInsurance} className="space-y-2 px-4 pb-4">
                  <div className="grid grid-cols-2 gap-2">
                    <Input placeholder="증권번호" value={polNo} onChange={(e) => setPolNo(e.target.value)} />
                    <Input placeholder="보험사" value={polInsurer} onChange={(e) => setPolInsurer(e.target.value)} />
                  </div>
                  <Input placeholder="담보 범위(선택)" value={polCoverage} onChange={(e) => setPolCoverage(e.target.value)} />
                  <div className="grid grid-cols-2 gap-2">
                    <Input type="date" value={polFrom} onChange={(e) => setPolFrom(e.target.value)} />
                    <Input type="date" placeholder="종료일(선택)" value={polTo} onChange={(e) => setPolTo(e.target.value)} />
                  </div>
                  <Button type="submit" className="w-full" disabled={createInsurance.isPending}>보험 등록</Button>
                </form>
              </Card>
              <Card>
                <CardHeader><CardTitle>클레임 등록</CardTitle></CardHeader>
                <form onSubmit={submitClaim} className="space-y-2 px-4 pb-4">
                  <div className="grid grid-cols-2 gap-2">
                    <Select value={clType} onChange={(e) => setClType(e.target.value)}>
                      {CLAIM_TYPES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
                    </Select>
                    <Select value={clShipmentId} onChange={(e) => setClShipmentId(e.target.value)}>
                      <option value="">출하 연결(선택)</option>
                      {shipmentOptions}
                    </Select>
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    <Input type="number" placeholder="청구액(선택)" value={clAmount} onChange={(e) => setClAmount(e.target.value)} />
                    <Input placeholder="비고(선택)" value={clNotes} onChange={(e) => setClNotes(e.target.value)} />
                  </div>
                  <Button type="submit" className="w-full" disabled={createClaim.isPending}>클레임 등록</Button>
                </form>
              </Card>
            </div>
          )}
          <Card>
            <CardHeader><CardTitle>보험 목록</CardTitle></CardHeader>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>증권번호</TableHead><TableHead>보험사</TableHead><TableHead>담보</TableHead>
                  <TableHead>시작</TableHead><TableHead>종료</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {(insurance.data ?? []).map((p) => (
                  <TableRow key={p.policy_id}>
                    <TableCell>{p.policy_no}</TableCell>
                    <TableCell>{p.insurer}</TableCell>
                    <TableCell>{p.coverage ?? '-'}</TableCell>
                    <TableCell>{p.valid_from ?? '-'}</TableCell>
                    <TableCell>{p.valid_to ?? '-'}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Card>
          <Card>
            <CardHeader><CardTitle>클레임 목록</CardTitle></CardHeader>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>유형</TableHead><TableHead>출하</TableHead><TableHead className="text-right">청구액</TableHead>
                  <TableHead>일자</TableHead><TableHead>상태</TableHead><TableHead>비고</TableHead>
                  {canWrite && <TableHead>액션</TableHead>}
                </TableRow>
              </TableHeader>
              <TableBody>
                {(claims.data ?? []).map((c) => (
                  <TableRow key={c.claim_id}>
                    <TableCell>{CLAIM_TYPES.find((t) => t.value === c.claim_type)?.label ?? c.claim_type}</TableCell>
                    <TableCell>{c.shipment_no ?? '-'}</TableCell>
                    <TableCell className="text-right">{c.amount != null ? currency(c.amount) : '-'}</TableCell>
                    <TableCell>{c.claim_date}</TableCell>
                    <TableCell><StatusBadge status={c.status} /></TableCell>
                    <TableCell>{c.notes ?? '-'}</TableCell>
                    {canWrite && (
                      <TableCell>
                        <Select
                          value={c.status}
                          onChange={(e) => updateClaimStatus.mutate({ id: c.claim_id, status: e.target.value })}
                        >
                          {CLAIM_STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
                        </Select>
                      </TableCell>
                    )}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Card>
        </>
      )}
    </div>
  )
}
