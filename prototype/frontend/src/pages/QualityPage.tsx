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
  Material, Customer, InspectionStandardRow, QualityInspectionRow, SpcResponse,
  NonconformanceResponse, EightDRow, CustomerClaimRow, CapaResponse, QualityDashboard,
} from '@/lib/types'

// 06. Quality Management (v14) — task-plan-v9-full-menu-rollout.md §3 v14
const TABS = [
  { key: 'dashboard', label: '품질 현황' },
  { key: 'standards', label: '검사기준' },
  { key: 'inspections', label: '검사이력' },
  { key: 'spc', label: 'SPC·공정능력' },
  { key: 'nonconformance', label: '부적합' },
  { key: 'claims', label: '고객클레임' },
  { key: 'improvement', label: '8D·CAPA' },
] as const
type TabKey = (typeof TABS)[number]['key']

const INSPECTION_TYPES = [
  { value: 'INCOMING', label: '수입검사' },
  { value: 'IN_PROCESS', label: '공정검사' },
  { value: 'FINAL', label: '출하검사' },
]
const typeLabel = (v: string | null) => INSPECTION_TYPES.find((t) => t.value === v)?.label ?? (v ?? '-')
const CLAIM_TYPES = [
  { value: 'QUALITY', label: '품질' },
  { value: 'DELIVERY', label: '납기' },
  { value: 'OTHER', label: '기타' },
]
const CLAIM_STATUSES = ['OPEN', 'INVESTIGATING', 'RESOLVED', 'REJECTED']
const EIGHT_D_STATUSES = ['OPEN', 'IN_PROGRESS', 'CLOSED']
const CAPA_STATUSES = ['OPEN', 'IN_PROGRESS', 'DONE']

export default function QualityPage() {
  const { hasRole } = useAuth()
  const canWrite = hasRole('생산담당', '관리자')
  const canClaim = hasRole('영업담당', '생산담당', '관리자')
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

  const materials = useQuery({ queryKey: ['materials'], queryFn: () => apiGet<Material[]>('/api/materials') })
  const customers = useQuery({ queryKey: ['customers'], queryFn: () => apiGet<Customer[]>('/api/customers') })

  // ---------- 품질 현황 ----------
  const dashboard = useQuery({
    queryKey: ['quality-dashboard'],
    queryFn: () => apiGet<QualityDashboard>('/api/quality/dashboard'),
    enabled: tab === 'dashboard',
  })

  // ---------- 검사기준 ----------
  const standards = useQuery({
    queryKey: ['quality-standards'],
    queryFn: () => apiGet<InspectionStandardRow[]>('/api/quality/standards'),
    enabled: tab === 'standards' || tab === 'spc',
  })
  const [stMaterialId, setStMaterialId] = useState('')
  const [stType, setStType] = useState('INCOMING')
  const [stItem, setStItem] = useState('')
  const [stLsl, setStLsl] = useState('')
  const [stUsl, setStUsl] = useState('')
  const [stUnit, setStUnit] = useState('')
  const createStandard = useMutation({
    mutationFn: (body: Record<string, unknown>) => apiPost('/api/quality/standards', body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['quality-standards'] })
      setStItem('')
      flash('검사기준이 등록되었습니다.')
    },
    onError: (err) => fail(err, '등록 실패'),
  })
  async function submitStandard(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    if (!stMaterialId || !stItem.trim()) return fail(null, '품목과 검사항목을 입력하세요')
    await createStandard.mutateAsync({
      material_id: Number(stMaterialId), inspection_type: stType, item_name: stItem.trim(),
      spec_lsl: stLsl ? Number(stLsl) : undefined, spec_usl: stUsl ? Number(stUsl) : undefined,
      unit: stUnit.trim() || undefined,
    })
  }

  // ---------- 검사이력 ----------
  const [filterType, setFilterType] = useState('')
  const inspections = useQuery({
    queryKey: ['quality-inspections', filterType],
    queryFn: () =>
      apiGet<QualityInspectionRow[]>(`/api/quality/inspections${filterType ? `?inspection_type=${filterType}` : ''}`),
    enabled: tab === 'inspections',
  })

  // ---------- SPC ----------
  const [spcMaterialId, setSpcMaterialId] = useState('')
  const spc = useQuery({
    queryKey: ['quality-spc', spcMaterialId],
    queryFn: () => apiGet<SpcResponse>(`/api/quality/spc/${spcMaterialId}`),
    enabled: tab === 'spc' && !!spcMaterialId,
  })

  // ---------- 부적합 ----------
  const nonconformance = useQuery({
    queryKey: ['quality-nonconformance'],
    queryFn: () => apiGet<NonconformanceResponse>('/api/quality/nonconformance'),
    enabled: tab === 'nonconformance',
  })

  // ---------- 고객클레임 ----------
  const claims = useQuery({
    queryKey: ['quality-claims'],
    queryFn: () => apiGet<CustomerClaimRow[]>('/api/quality/claims'),
    enabled: tab === 'claims',
  })
  const [clCustomerId, setClCustomerId] = useState('')
  const [clMaterialId, setClMaterialId] = useState('')
  const [clType, setClType] = useState('QUALITY')
  const [clQty, setClQty] = useState('')
  const [clDesc, setClDesc] = useState('')
  const createClaim = useMutation({
    mutationFn: (body: Record<string, unknown>) => apiPost('/api/quality/claims', body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['quality-claims'] })
      setClDesc('')
      setClQty('')
      flash('고객클레임이 등록되었습니다.')
    },
    onError: (err) => fail(err, '등록 실패'),
  })
  const updateClaimStatus = useMutation({
    mutationFn: ({ id, status }: { id: number; status: string }) =>
      apiPost(`/api/quality/claims/${id}/status`, { status }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['quality-claims'] }),
    onError: (err) => fail(err, '상태 변경 실패'),
  })
  async function submitClaim(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    if (!clCustomerId) return fail(null, '고객을 선택하세요')
    await createClaim.mutateAsync({
      customer_id: Number(clCustomerId),
      material_id: clMaterialId ? Number(clMaterialId) : undefined,
      claim_type: clType,
      qty: clQty ? Number(clQty) : undefined,
      description: clDesc.trim() || undefined,
    })
  }

  // ---------- 8D / CAPA ----------
  const eightD = useQuery({
    queryKey: ['quality-8d'],
    queryFn: () => apiGet<EightDRow[]>('/api/quality/eight-d'),
    enabled: tab === 'improvement',
  })
  const capa = useQuery({
    queryKey: ['quality-capa'],
    queryFn: () => apiGet<CapaResponse>('/api/quality/capa'),
    enabled: tab === 'improvement',
  })
  const [edTitle, setEdTitle] = useState('')
  const [edMaterialId, setEdMaterialId] = useState('')
  const [edProblem, setEdProblem] = useState('')
  const [edRootCause, setEdRootCause] = useState('')
  const [edAction, setEdAction] = useState('')
  const createEightD = useMutation({
    mutationFn: (body: Record<string, unknown>) => apiPost('/api/quality/eight-d', body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['quality-8d'] })
      setEdTitle('')
      setEdProblem('')
      setEdRootCause('')
      setEdAction('')
      flash('8D Report가 등록되었습니다.')
    },
    onError: (err) => fail(err, '등록 실패'),
  })
  const updateEightDStatus = useMutation({
    mutationFn: ({ id, status }: { id: number; status: string }) =>
      apiPost(`/api/quality/eight-d/${id}/status`, { status }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['quality-8d'] }),
    onError: (err) => fail(err, '상태 변경 실패'),
  })
  const [capaTitle, setCapaTitle] = useState('')
  const [capaType, setCapaType] = useState('CORRECTIVE')
  const [capaInspectionId, setCapaInspectionId] = useState('')
  const [capaDue, setCapaDue] = useState('')
  const createCapa = useMutation({
    mutationFn: (body: Record<string, unknown>) => apiPost('/api/quality/capa', body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['quality-capa'] })
      setCapaTitle('')
      setCapaInspectionId('')
      flash('CAPA가 등록되었습니다.')
    },
    onError: (err) => fail(err, '등록 실패'),
  })
  const updateCapaStatus = useMutation({
    mutationFn: ({ id, status }: { id: number; status: string }) =>
      apiPost(`/api/quality/capa/${id}/status`, { status }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['quality-capa'] }),
    onError: (err) => fail(err, '상태 변경 실패'),
  })

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold text-text-primary">품질</h1>
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
          <KpiCard label="검사 건수" value={String(dashboard.data?.inspection_count ?? '-')} />
          <KpiCard label="평균 불량 PPM" value={String(dashboard.data?.avg_defect_ppm ?? '-')} />
          <KpiCard
            label="FAIL 검사"
            value={String(dashboard.data?.fail_count ?? '-')}
            tone={(dashboard.data?.fail_count ?? 0) > 0 ? 'danger' : 'default'}
          />
          <KpiCard
            label="불량 시리얼"
            value={String(dashboard.data?.defective_serial_count ?? '-')}
            tone={(dashboard.data?.defective_serial_count ?? 0) > 0 ? 'warning' : 'default'}
          />
          <KpiCard
            label="미완료 CAPA"
            value={String(dashboard.data?.open_capa_count ?? '-')}
            hint={dashboard.data ? `후보 ${dashboard.data.capa_candidate_count}건` : undefined}
            tone={(dashboard.data?.open_capa_count ?? 0) > 0 ? 'warning' : 'default'}
          />
          <KpiCard
            label="미결 클레임"
            value={String(dashboard.data?.open_claim_count ?? '-')}
            tone={(dashboard.data?.open_claim_count ?? 0) > 0 ? 'danger' : 'default'}
          />
          <KpiCard label="진행 중 8D" value={String(dashboard.data?.open_8d_count ?? '-')} />
          <KpiCard label="검사기준 수" value={String(dashboard.data?.standard_count ?? '-')} />
        </div>
      )}

      {tab === 'standards' && (
        <>
          {canWrite && (
            <Card>
              <CardHeader><CardTitle>검사기준 등록</CardTitle></CardHeader>
              <form onSubmit={submitStandard} className="space-y-2 px-4 pb-4">
                <div className="grid grid-cols-3 gap-2">
                  <Select value={stMaterialId} onChange={(e) => setStMaterialId(e.target.value)}>
                    <option value="">품목 선택</option>
                    {(materials.data ?? []).map((m) => (
                      <option key={m.material_id} value={m.material_id}>{m.name}</option>
                    ))}
                  </Select>
                  <Select value={stType} onChange={(e) => setStType(e.target.value)}>
                    {INSPECTION_TYPES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
                  </Select>
                  <Input placeholder="검사항목 (예: 외관, 치수, 불량 PPM)" value={stItem} onChange={(e) => setStItem(e.target.value)} />
                </div>
                <div className="grid grid-cols-3 gap-2">
                  <Input type="number" placeholder="규격 하한 LSL(선택)" value={stLsl} onChange={(e) => setStLsl(e.target.value)} />
                  <Input type="number" placeholder="규격 상한 USL(선택)" value={stUsl} onChange={(e) => setStUsl(e.target.value)} />
                  <Input placeholder="단위(선택)" value={stUnit} onChange={(e) => setStUnit(e.target.value)} />
                </div>
                <p className="text-xs text-text-secondary">LSL/USL을 등록하면 SPC·공정능력 탭에서 Cp/Cpk가 계산됩니다.</p>
                <Button type="submit" className="w-full" disabled={createStandard.isPending}>검사기준 등록</Button>
              </form>
            </Card>
          )}
          <Card>
            <CardHeader><CardTitle>검사기준 목록</CardTitle></CardHeader>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>품목</TableHead><TableHead>검사구분</TableHead><TableHead>검사항목</TableHead>
                  <TableHead className="text-right">LSL</TableHead><TableHead className="text-right">USL</TableHead>
                  <TableHead>단위</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {(standards.data ?? []).map((s) => (
                  <TableRow key={s.standard_id}>
                    <TableCell>{s.material_name}</TableCell>
                    <TableCell>{typeLabel(s.inspection_type)}</TableCell>
                    <TableCell>{s.item_name}</TableCell>
                    <TableCell className="text-right">{s.spec_lsl ?? '-'}</TableCell>
                    <TableCell className="text-right">{s.spec_usl ?? '-'}</TableCell>
                    <TableCell>{s.unit ?? '-'}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Card>
        </>
      )}

      {tab === 'inspections' && (
        <Card>
          <CardHeader>
            <CardTitle>검사이력 (등록은 생산 &gt; 생산오더 탭의 QMS 폼 이용)</CardTitle>
          </CardHeader>
          <div className="px-4 pb-2">
            <Select value={filterType} onChange={(e) => setFilterType(e.target.value)} className="w-48">
              <option value="">전체 검사구분</option>
              {INSPECTION_TYPES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
            </Select>
          </div>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>일자</TableHead><TableHead>품목</TableHead><TableHead>구분</TableHead>
                <TableHead className="text-right">샘플</TableHead><TableHead className="text-right">불량</TableHead>
                <TableHead className="text-right">PPM</TableHead><TableHead>결과</TableHead><TableHead>CAPA</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(inspections.data ?? []).map((i) => (
                <TableRow key={i.inspection_id}>
                  <TableCell>{i.inspection_date}</TableCell>
                  <TableCell>{i.material_name}</TableCell>
                  <TableCell>{typeLabel(i.inspection_type)}</TableCell>
                  <TableCell className="text-right">{i.sample_qty ?? '-'}</TableCell>
                  <TableCell className="text-right">{i.defect_qty ?? '-'}</TableCell>
                  <TableCell className="text-right">{i.defect_ppm != null ? Math.round(i.defect_ppm).toLocaleString() : '-'}</TableCell>
                  <TableCell><StatusBadge status={i.result ?? '-'} /></TableCell>
                  <TableCell>{i.capa_required === 'Y' ? 'Y' : '-'}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Card>
      )}

      {tab === 'spc' && (
        <>
          <Card>
            <CardHeader><CardTitle>SPC·공정능력 분석 (불량 PPM 기준 — 프로토타입 근사)</CardTitle></CardHeader>
            <div className="px-4 pb-4">
              <Select value={spcMaterialId} onChange={(e) => setSpcMaterialId(e.target.value)} className="w-64">
                <option value="">품목 선택</option>
                {(materials.data ?? []).map((m) => (
                  <option key={m.material_id} value={m.material_id}>{m.name}</option>
                ))}
              </Select>
            </div>
            {spc.data && spc.data.mean != null && (
              <div className="grid grid-cols-2 gap-3 px-4 pb-4 md:grid-cols-4">
                <KpiCard label="표본 수" value={String(spc.data.sample_count)} />
                <KpiCard label="평균 PPM" value={String(spc.data.mean)} />
                <KpiCard label="UCL (+3σ)" value={String(spc.data.ucl)} />
                <KpiCard label="LCL (-3σ)" value={String(spc.data.lcl)} />
                <KpiCard
                  label="관리이탈 점"
                  value={String(spc.data.out_of_control_count ?? '-')}
                  tone={(spc.data.out_of_control_count ?? 0) > 0 ? 'danger' : 'success'}
                />
                <KpiCard
                  label="Cp"
                  value={spc.data.cp != null ? String(spc.data.cp) : '기준 없음'}
                  hint={spc.data.cp == null ? '검사기준에 LSL/USL 등록 필요' : undefined}
                />
                <KpiCard
                  label="Cpk"
                  value={spc.data.cpk != null ? String(spc.data.cpk) : '기준 없음'}
                  tone={spc.data.cpk != null && spc.data.cpk < 1.33 ? 'warning' : 'default'}
                />
              </div>
            )}
            {spc.data && spc.data.mean == null && spcMaterialId && (
              <p className="px-4 pb-4 text-xs text-text-secondary">해당 품목의 검사 데이터가 2건 미만이라 통계를 계산할 수 없습니다.</p>
            )}
          </Card>
          {spc.data && (spc.data.points?.length ?? 0) > 0 && (
            <Card>
              <CardHeader><CardTitle>최근 검사 시계열 (최대 50건)</CardTitle></CardHeader>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>일자</TableHead><TableHead>구분</TableHead><TableHead className="text-right">불량 PPM</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {spc.data.points.map((p, i) => (
                    <TableRow key={i} className={spc.data!.ucl != null && p.defect_ppm > spc.data!.ucl! ? 'bg-danger/5' : undefined}>
                      <TableCell>{p.inspection_date}</TableCell>
                      <TableCell>{typeLabel(p.inspection_type)}</TableCell>
                      <TableCell className="text-right">{Math.round(p.defect_ppm).toLocaleString()}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </Card>
          )}
        </>
      )}

      {tab === 'nonconformance' && (
        <>
          <Card>
            <CardHeader><CardTitle>불량(DEFECTIVE) 시리얼 — 처리(재투입/폐기)는 생산 &gt; 재작업 탭</CardTitle></CardHeader>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>시리얼</TableHead><TableHead>품목</TableHead><TableHead>상태</TableHead><TableHead>재작업</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {(nonconformance.data?.defective_serials ?? []).map((s) => (
                  <TableRow key={s.serial_id}>
                    <TableCell>{s.serial_no}</TableCell>
                    <TableCell>{s.material_name}</TableCell>
                    <TableCell><StatusBadge status={s.status} /></TableCell>
                    <TableCell>{s.open_rework > 0 ? '진행 중' : '-'}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Card>
          <Card>
            <CardHeader><CardTitle>FAIL 검사 이력 (최근 50건)</CardTitle></CardHeader>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>일자</TableHead><TableHead>품목</TableHead><TableHead>구분</TableHead>
                  <TableHead className="text-right">불량수량</TableHead><TableHead className="text-right">PPM</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {(nonconformance.data?.fail_inspections ?? []).map((f) => (
                  <TableRow key={f.inspection_id}>
                    <TableCell>{f.inspection_date}</TableCell>
                    <TableCell>{f.material_name}</TableCell>
                    <TableCell>{typeLabel(f.inspection_type)}</TableCell>
                    <TableCell className="text-right">{f.defect_qty ?? '-'}</TableCell>
                    <TableCell className="text-right">{f.defect_ppm != null ? Math.round(f.defect_ppm).toLocaleString() : '-'}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Card>
        </>
      )}

      {tab === 'claims' && (
        <>
          {canClaim && (
            <Card>
              <CardHeader><CardTitle>고객클레임 등록</CardTitle></CardHeader>
              <form onSubmit={submitClaim} className="space-y-2 px-4 pb-4">
                <div className="grid grid-cols-4 gap-2">
                  <Select value={clCustomerId} onChange={(e) => setClCustomerId(e.target.value)}>
                    <option value="">고객 선택</option>
                    {(customers.data ?? []).map((c) => (
                      <option key={c.customer_id} value={c.customer_id}>{c.name}</option>
                    ))}
                  </Select>
                  <Select value={clMaterialId} onChange={(e) => setClMaterialId(e.target.value)}>
                    <option value="">품목(선택)</option>
                    {(materials.data ?? []).map((m) => (
                      <option key={m.material_id} value={m.material_id}>{m.name}</option>
                    ))}
                  </Select>
                  <Select value={clType} onChange={(e) => setClType(e.target.value)}>
                    {CLAIM_TYPES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
                  </Select>
                  <Input type="number" placeholder="수량(선택)" value={clQty} onChange={(e) => setClQty(e.target.value)} />
                </div>
                <Input placeholder="내용(선택)" value={clDesc} onChange={(e) => setClDesc(e.target.value)} />
                <Button type="submit" className="w-full" disabled={createClaim.isPending}>클레임 등록</Button>
              </form>
            </Card>
          )}
          <Card>
            <CardHeader><CardTitle>고객클레임 목록</CardTitle></CardHeader>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>고객</TableHead><TableHead>품목</TableHead><TableHead>유형</TableHead>
                  <TableHead className="text-right">수량</TableHead><TableHead>내용</TableHead>
                  <TableHead>일자</TableHead><TableHead>상태</TableHead>
                  {canWrite && <TableHead>액션</TableHead>}
                </TableRow>
              </TableHeader>
              <TableBody>
                {(claims.data ?? []).map((c) => (
                  <TableRow key={c.claim_id}>
                    <TableCell>{c.customer_name}</TableCell>
                    <TableCell>{c.material_name ?? '-'}</TableCell>
                    <TableCell>{CLAIM_TYPES.find((t) => t.value === c.claim_type)?.label ?? c.claim_type}</TableCell>
                    <TableCell className="text-right">{c.qty ?? '-'}</TableCell>
                    <TableCell>{c.description ?? '-'}</TableCell>
                    <TableCell>{c.claim_date}</TableCell>
                    <TableCell><StatusBadge status={c.status} /></TableCell>
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

      {tab === 'improvement' && (
        <>
          {canWrite && (
            <div className="grid gap-4 lg:grid-cols-2">
              <Card>
                <CardHeader><CardTitle>8D Report 등록 (간이 — 문제/근본원인/시정조치)</CardTitle></CardHeader>
                <form
                  onSubmit={async (e) => {
                    e.preventDefault()
                    if (!edTitle.trim()) return fail(null, '제목을 입력하세요')
                    await createEightD.mutateAsync({
                      title: edTitle.trim(),
                      material_id: edMaterialId ? Number(edMaterialId) : undefined,
                      problem: edProblem.trim() || undefined,
                      root_cause: edRootCause.trim() || undefined,
                      corrective_action: edAction.trim() || undefined,
                    })
                  }}
                  className="space-y-2 px-4 pb-4"
                >
                  <div className="grid grid-cols-2 gap-2">
                    <Input placeholder="제목" value={edTitle} onChange={(e) => setEdTitle(e.target.value)} />
                    <Select value={edMaterialId} onChange={(e) => setEdMaterialId(e.target.value)}>
                      <option value="">품목(선택)</option>
                      {(materials.data ?? []).map((m) => (
                        <option key={m.material_id} value={m.material_id}>{m.name}</option>
                      ))}
                    </Select>
                  </div>
                  <Input placeholder="D2 문제 정의(선택)" value={edProblem} onChange={(e) => setEdProblem(e.target.value)} />
                  <Input placeholder="D4 근본원인(선택)" value={edRootCause} onChange={(e) => setEdRootCause(e.target.value)} />
                  <Input placeholder="D5 시정조치(선택)" value={edAction} onChange={(e) => setEdAction(e.target.value)} />
                  <Button type="submit" className="w-full" disabled={createEightD.isPending}>8D 등록</Button>
                </form>
              </Card>
              <Card>
                <CardHeader><CardTitle>CAPA 등록</CardTitle></CardHeader>
                <form
                  onSubmit={async (e) => {
                    e.preventDefault()
                    if (!capaTitle.trim()) return fail(null, '제목을 입력하세요')
                    await createCapa.mutateAsync({
                      title: capaTitle.trim(),
                      action_type: capaType,
                      inspection_id: capaInspectionId ? Number(capaInspectionId) : undefined,
                      due_date: capaDue || undefined,
                    })
                  }}
                  className="space-y-2 px-4 pb-4"
                >
                  <Input placeholder="제목" value={capaTitle} onChange={(e) => setCapaTitle(e.target.value)} />
                  <div className="grid grid-cols-3 gap-2">
                    <Select value={capaType} onChange={(e) => setCapaType(e.target.value)}>
                      <option value="CORRECTIVE">시정(Corrective)</option>
                      <option value="PREVENTIVE">예방(Preventive)</option>
                    </Select>
                    <Select value={capaInspectionId} onChange={(e) => setCapaInspectionId(e.target.value)}>
                      <option value="">검사 연결(선택)</option>
                      {(capa.data?.candidates ?? []).map((c) => (
                        <option key={c.inspection_id} value={c.inspection_id}>
                          #{c.inspection_id} {c.material_name} ({c.inspection_date})
                        </option>
                      ))}
                    </Select>
                    <Input type="date" value={capaDue} onChange={(e) => setCapaDue(e.target.value)} />
                  </div>
                  <p className="text-xs text-text-secondary">
                    검사 연결 드롭다운은 CAPA 필요(Y) 표시됐지만 아직 조치가 없는 검사 목록입니다
                    ({capa.data?.candidates.length ?? 0}건 대기).
                  </p>
                  <Button type="submit" className="w-full" disabled={createCapa.isPending}>CAPA 등록</Button>
                </form>
              </Card>
            </div>
          )}
          <Card>
            <CardHeader><CardTitle>8D Report 목록</CardTitle></CardHeader>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>제목</TableHead><TableHead>품목</TableHead><TableHead>근본원인</TableHead>
                  <TableHead>일자</TableHead><TableHead>상태</TableHead>
                  {canWrite && <TableHead>액션</TableHead>}
                </TableRow>
              </TableHeader>
              <TableBody>
                {(eightD.data ?? []).map((r) => (
                  <TableRow key={r.report_id}>
                    <TableCell>{r.title}</TableCell>
                    <TableCell>{r.material_name ?? '-'}</TableCell>
                    <TableCell>{r.root_cause ?? '-'}</TableCell>
                    <TableCell>{r.report_date}</TableCell>
                    <TableCell><StatusBadge status={r.status} /></TableCell>
                    {canWrite && (
                      <TableCell>
                        <Select
                          value={r.status}
                          onChange={(e) => updateEightDStatus.mutate({ id: r.report_id, status: e.target.value })}
                        >
                          {EIGHT_D_STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
                        </Select>
                      </TableCell>
                    )}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Card>
          <Card>
            <CardHeader><CardTitle>CAPA 목록</CardTitle></CardHeader>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>제목</TableHead><TableHead>유형</TableHead><TableHead>출처</TableHead>
                  <TableHead>검사#</TableHead><TableHead>기한</TableHead><TableHead>상태</TableHead>
                  {canWrite && <TableHead>액션</TableHead>}
                </TableRow>
              </TableHeader>
              <TableBody>
                {(capa.data?.actions ?? []).map((c) => (
                  <TableRow key={c.capa_id}>
                    <TableCell>{c.title}</TableCell>
                    <TableCell>{c.action_type === 'CORRECTIVE' ? '시정' : '예방'}</TableCell>
                    <TableCell>{c.source}</TableCell>
                    <TableCell>{c.inspection_id ?? '-'}</TableCell>
                    <TableCell>{c.due_date ?? '-'}</TableCell>
                    <TableCell><StatusBadge status={c.status} /></TableCell>
                    {canWrite && (
                      <TableCell>
                        <Select
                          value={c.status}
                          onChange={(e) => updateCapaStatus.mutate({ id: c.capa_id, status: e.target.value })}
                        >
                          {CAPA_STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
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
