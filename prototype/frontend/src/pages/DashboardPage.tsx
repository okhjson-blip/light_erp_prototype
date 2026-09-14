import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { apiGet } from '@/lib/api'
import {
  DashboardKpiGrid,
  DashboardMenuGrid,
  DashboardSection,
  DashboardShell,
  statusFor,
  trendFor,
  type DashboardKpi,
} from '@/components/ax-dashboard'

interface DashboardKpiResponse {
  open_so: number
  open_po: number
  pending_approvals: number
  material_count: number
  total_ar: number
  total_ap: number
  lot_inconsistent_count: number
}

/** 카드 폭이 좁아 원화 전체 자릿수를 넣으면 잘린다. 억/만 단위로 압축한다. */
const compactCurrency = (n: number) => {
  if (Math.abs(n) >= 100_000_000) return `${(n / 100_000_000).toFixed(1)}억`
  if (Math.abs(n) >= 10_000) return `${Math.round(n / 10_000).toLocaleString()}만`
  return n.toLocaleString()
}

// 메뉴 카드 아이콘. 전사 대시보드 사양대로 인라인 SVG만 사용한다.
const icon = (path: string) => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor"
    strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d={path} />
  </svg>
)

// App.tsx의 실제 라우트만 사용한다.
const MENUS = [
  { id: 'mdm', label: '기준정보', caption: '품목·거래처', tone: 'purple', to: '/mdm', icon: icon('M12 3c4.97 0 9 1.34 9 3v12c0 1.66-4.03 3-9 3s-9-1.34-9-3V6c0-1.66 4.03-3 9-3zM3 6c0 1.66 4.03 3 9 3s9-1.34 9-3') },
  { id: 'sales', label: '영업', caption: '수주·출하·매출', tone: 'blue', to: '/sales', icon: icon('M3 3v18h18M7 15l4-4 3 3 5-6') },
  { id: 'procurement', label: '구매', caption: '발주·입고·매입', tone: 'green', to: '/procurement', icon: icon('M6 2 3 6v14h18V6l-3-4zM3 6h18M16 10a4 4 0 0 1-8 0') },
  { id: 'production', label: '생산', caption: '작업지시·실적', tone: 'amber', to: '/production', icon: icon('M2 20h20V9l-6 4V9l-6 4V4H2z') },
  { id: 'inventory', label: '재고', caption: '재고·LOT·이동', tone: 'cyan', to: '/inventory', icon: icon('M21 8v13H3V8M1 3h22v5H1zM10 12h4') },
  { id: 'quality', label: '품질', caption: '검사·부적합', tone: 'rose', to: '/quality', icon: icon('M9 11l3 3L22 4M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11') },
  { id: 'logistics', label: '물류', caption: '출하·배송', tone: 'gray', to: '/logistics', icon: icon('M1 3h15v13H1zM16 8h4l3 3v5h-7zM5.5 19a2 2 0 1 0 0-4 2 2 0 0 0 0 4zM18.5 19a2 2 0 1 0 0-4 2 2 0 0 0 0 4z') },
  { id: 'scm', label: 'SCM', caption: '수요·공급 관제', tone: 'indigo', to: '/scm', icon: icon('M12 2v6M12 16v6M2 12h6M16 12h6M6 6l4 4M14 14l4 4M18 6l-4 4M10 14l-4 4') },
  { id: 'finance', label: '회계', caption: '전표·AR·AP', tone: 'blue', to: '/finance', icon: icon('M12 1v22M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6') },
  { id: 'approvals', label: '승인함', caption: '결재 대기', tone: 'amber', to: '/approvals', icon: icon('M9 11l3 3L22 4M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11') },
  { id: 'reference', label: '참조 데이터', caption: '코드·기준', tone: 'gray', to: '/reference', icon: icon('M4 19.5A2.5 2.5 0 0 1 6.5 17H20M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z') },
  { id: 'ai-agent', label: 'AI Agent', caption: '추천·설명', tone: 'rose', to: '/ai-agent', icon: icon('M12 2a3 3 0 0 1 3 3v1h1a3 3 0 0 1 3 3v2h1v3h-1v2a3 3 0 0 1-3 3H8a3 3 0 0 1-3-3v-2H4v-3h1V9a3 3 0 0 1 3-3h1V5a3 3 0 0 1 3-3zM9 13h.01M15 13h.01') },
] as const

export default function DashboardPage() {
  const navigate = useNavigate()
  const { data, isLoading } = useQuery({
    queryKey: ['dashboard-kpi'],
    queryFn: () => apiGet<DashboardKpiResponse>('/api/dashboard/kpi'),
  })

  const kpis: DashboardKpi[] = data
    ? [
        {
          id: 'open_so', title: '미결 수주', value: data.open_so, unit: '건',
          status: statusFor(data.open_so, { warning: 20, danger: 50 }),
          ...trendFor(data.open_so, '건'),
          onClick: () => navigate('/sales'),
        },
        {
          id: 'open_po', title: '미결 발주', value: data.open_po, unit: '건',
          status: statusFor(data.open_po, { warning: 20, danger: 50 }),
          ...trendFor(data.open_po, '건'),
          onClick: () => navigate('/procurement'),
        },
        {
          id: 'pending_approvals', title: '승인 대기', value: data.pending_approvals, unit: '건',
          status: statusFor(data.pending_approvals, { warning: 1, danger: 10 }),
          ...trendFor(data.pending_approvals, '건'),
          onClick: () => navigate('/approvals'),
        },
        {
          id: 'material_count', title: '등록 품목수', value: data.material_count, unit: '개',
          status: 'normal', trend: 'flat', trendLabel: `${data.material_count}개`,
          onClick: () => navigate('/mdm'),
        },
        {
          id: 'total_ar', title: '매출채권 (AR)', value: compactCurrency(data.total_ar), unit: '원',
          status: 'normal', trend: 'flat', trendLabel: '기준: 현재',
          onClick: () => navigate('/finance'),
        },
        {
          id: 'total_ap', title: '매입채무 (AP)', value: compactCurrency(data.total_ap), unit: '원',
          status: 'normal', trend: 'flat', trendLabel: '기준: 현재',
          onClick: () => navigate('/finance'),
        },
        {
          id: 'lot_inconsistent', title: 'LOT 정합성 불일치', value: data.lot_inconsistent_count, unit: '건',
          status: statusFor(data.lot_inconsistent_count, { danger: 1 }),
          ...trendFor(data.lot_inconsistent_count, '건'),
          onClick: () => navigate('/inventory'),
        },
      ]
    : []

  return (
    <DashboardShell>
      <DashboardSection title="주요 KPI" hint={isLoading ? '불러오는 중…' : '기준: 현재'}>
        {isLoading || !data
          ? <p className="text-[11px] text-gray-400">불러오는 중…</p>
          : <DashboardKpiGrid items={kpis} />}
      </DashboardSection>

      <DashboardSection title="메뉴">
        <DashboardMenuGrid
          items={MENUS.map(({ to, ...menu }) => ({ ...menu, onClick: () => navigate(to) }))}
        />
      </DashboardSection>
    </DashboardShell>
  )
}
