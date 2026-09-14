import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { apiGet } from '@/lib/api'
import { Card, CardHeader, CardTitle } from '@/components/ui/card'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table'
import { KpiCard } from '@/components/KpiCard'
import { cn } from '@/lib/utils'
import type {
  DemandForecastAccuracy, SopGapRow, SupplyPlanRow, MpsRow, InventoryPlanRow, SupplyRiskRow, ScmControlTower,
} from '@/lib/types'

// 02. Supply Chain Management (v10) — 전부 조회 전용(신규 마스터/트랜잭션 등록 없음).
// 공급망 시뮬레이션(What-if)은 사용자 확인 후 이번 로드맵 전체에서 제외(task-plan-v9-full-menu-rollout.md §5).
const TABS = [
  { key: 'tower', label: 'Control Tower' },
  { key: 'forecast', label: '수요예측 정확도' },
  { key: 'sop', label: 'S&OP' },
  { key: 'supply', label: '공급계획' },
  { key: 'mps', label: '생산계획(MPS)' },
  { key: 'invplan', label: '재고계획' },
  { key: 'risk', label: '공급위험관리' },
] as const
type TabKey = (typeof TABS)[number]['key']

export default function ScmPage() {
  const [tab, setTab] = useState<TabKey>('tower')

  const tower = useQuery({ queryKey: ['scm-tower'], queryFn: () => apiGet<ScmControlTower>('/api/scm/control-tower'), enabled: tab === 'tower' })
  const forecast = useQuery({ queryKey: ['scm-forecast'], queryFn: () => apiGet<DemandForecastAccuracy[]>('/api/scm/demand-forecast/accuracy'), enabled: tab === 'forecast' })
  const sop = useQuery({ queryKey: ['scm-sop'], queryFn: () => apiGet<SopGapRow[]>('/api/scm/sop'), enabled: tab === 'sop' })
  const supply = useQuery({ queryKey: ['scm-supply'], queryFn: () => apiGet<SupplyPlanRow[]>('/api/scm/supply-plan'), enabled: tab === 'supply' })
  const mps = useQuery({ queryKey: ['scm-mps'], queryFn: () => apiGet<MpsRow[]>('/api/scm/mps'), enabled: tab === 'mps' })
  const invPlan = useQuery({ queryKey: ['scm-invplan'], queryFn: () => apiGet<InventoryPlanRow[]>('/api/scm/inventory-plan'), enabled: tab === 'invplan' })
  const risk = useQuery({ queryKey: ['scm-risk'], queryFn: () => apiGet<SupplyRiskRow[]>('/api/scm/supply-risk'), enabled: tab === 'risk' })

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold text-text-primary">SCM (공급망관리)</h1>
      <p className="text-xs text-text-secondary">
        수요예측/S&OP/공급계획/재고계획/공급위험관리를 조회 전용으로 제공합니다. 공급망 시뮬레이션은
        이번 범위에서 제외했습니다.
      </p>

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

      {tab === 'tower' && tower.data && (
        <div className="grid grid-cols-4 gap-4">
          <KpiCard label="재주문점 이하 품목" value={tower.data.below_reorder_point_count} tone={tower.data.below_reorder_point_count > 0 ? 'warning' : 'success'} />
          <KpiCard label="재고부족 품목" value={tower.data.low_stock_count} tone={tower.data.low_stock_count > 0 ? 'warning' : 'success'} />
          <KpiCard label="고위험 공급사" value={tower.data.high_risk_vendor_count} tone={tower.data.high_risk_vendor_count > 0 ? 'danger' : 'success'} />
          <KpiCard label="입고 이력 보유 공급사" value={tower.data.vendor_count} />
        </div>
      )}

      {tab === 'forecast' && (
        <Card>
          <CardHeader><CardTitle>수요예측 정확도 (품목별 평균 MAPE)</CardTitle></CardHeader>
          <Table>
            <TableHeader>
              <TableRow><TableHead>품목</TableHead><TableHead className="text-right">평균 MAPE</TableHead><TableHead className="text-right">예측 합계</TableHead><TableHead className="text-right">실판매 합계</TableHead><TableHead>방향성</TableHead></TableRow>
            </TableHeader>
            <TableBody>
              {(forecast.data ?? []).map((r) => (
                <TableRow key={r.material_id}>
                  <TableCell>{r.name}</TableCell>
                  <TableCell className="text-right">{r.avg_mape?.toFixed(1)}%</TableCell>
                  <TableCell className="text-right">{r.total_forecast_qty.toLocaleString()}</TableCell>
                  <TableCell className="text-right">{r.total_actual_qty.toLocaleString()}</TableCell>
                  <TableCell>{r.direction === 'OVER_FORECAST' ? '과대예측' : '과소예측'}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Card>
      )}

      {tab === 'sop' && (
        <Card>
          <CardHeader><CardTitle>S&OP — 판매계획(수요예측) vs 생산계획 대조</CardTitle></CardHeader>
          <Table>
            <TableHeader>
              <TableRow><TableHead>품목</TableHead><TableHead>월</TableHead><TableHead className="text-right">수요예측</TableHead><TableHead className="text-right">생산계획</TableHead><TableHead className="text-right">Gap</TableHead></TableRow>
            </TableHeader>
            <TableBody>
              {(sop.data ?? []).slice(0, 100).map((r, i) => (
                <TableRow key={i}>
                  <TableCell>{r.material_name}</TableCell>
                  <TableCell>{r.period}</TableCell>
                  <TableCell className="text-right">{r.demand_qty.toLocaleString()}</TableCell>
                  <TableCell className="text-right">{r.planned_qty.toLocaleString()}</TableCell>
                  <TableCell className={cn('text-right', r.gap < 0 ? 'text-danger' : 'text-success')}>{r.gap.toLocaleString()}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Card>
      )}

      {tab === 'supply' && (
        <Card>
          <CardHeader><CardTitle>공급계획 — 공급가능수량(현재고+미입고 PO)</CardTitle></CardHeader>
          <Table>
            <TableHeader>
              <TableRow><TableHead>품목</TableHead><TableHead className="text-right">현재고</TableHead><TableHead className="text-right">미입고 PO</TableHead><TableHead className="text-right">공급가능</TableHead><TableHead className="text-right">재주문점</TableHead><TableHead>상태</TableHead></TableRow>
            </TableHeader>
            <TableBody>
              {(supply.data ?? []).map((r) => (
                <TableRow key={r.material_id} className={r.below_reorder_point ? 'bg-danger/5' : undefined}>
                  <TableCell>{r.name}</TableCell>
                  <TableCell className="text-right">{r.on_hand_qty.toLocaleString()}</TableCell>
                  <TableCell className="text-right">{r.incoming_po_qty.toLocaleString()}</TableCell>
                  <TableCell className="text-right">{r.available_qty.toLocaleString()}</TableCell>
                  <TableCell className="text-right">{r.reorder_point.toLocaleString()}</TableCell>
                  <TableCell>{r.below_reorder_point ? <span className="text-danger">재주문점 이하</span> : '정상'}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Card>
      )}

      {tab === 'mps' && (
        <Card>
          <CardHeader><CardTitle>생산계획(MPS) — 월별 계획수량</CardTitle></CardHeader>
          <Table>
            <TableHeader>
              <TableRow><TableHead>품목</TableHead><TableHead>월</TableHead><TableHead className="text-right">계획수량</TableHead><TableHead className="text-right">오더 건수</TableHead></TableRow>
            </TableHeader>
            <TableBody>
              {(mps.data ?? []).slice(0, 100).map((r, i) => (
                <TableRow key={i}>
                  <TableCell>{r.name}</TableCell>
                  <TableCell>{r.period}</TableCell>
                  <TableCell className="text-right">{r.planned_qty.toLocaleString()}</TableCell>
                  <TableCell className="text-right">{r.order_count}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Card>
      )}

      {tab === 'invplan' && (
        <Card>
          <CardHeader><CardTitle>재고계획 — 안전재고/목표재고 대비 현재고</CardTitle></CardHeader>
          <Table>
            <TableHeader>
              <TableRow><TableHead>품목</TableHead><TableHead className="text-right">현재고</TableHead><TableHead className="text-right">재주문점</TableHead><TableHead className="text-right">목표재고</TableHead><TableHead className="text-right">목표대비 Gap</TableHead><TableHead>리스크</TableHead></TableRow>
            </TableHeader>
            <TableBody>
              {(invPlan.data ?? []).map((r) => (
                <TableRow key={r.material_id} className={r.risk === 'LOW_STOCK' ? 'bg-danger/5' : undefined}>
                  <TableCell>{r.name}</TableCell>
                  <TableCell className="text-right">{r.current_qty.toLocaleString()}</TableCell>
                  <TableCell className="text-right">{r.reorder_point.toLocaleString()}</TableCell>
                  <TableCell className="text-right">{r.target_stock.toLocaleString()}</TableCell>
                  <TableCell className="text-right">{r.gap_to_target.toLocaleString()}</TableCell>
                  <TableCell>{r.risk === 'LOW_STOCK' ? <span className="text-danger">재고부족</span> : '정상'}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Card>
      )}

      {tab === 'risk' && (
        <Card>
          <CardHeader><CardTitle>공급위험관리 — 공급사별 납기지연 리스크</CardTitle></CardHeader>
          {(risk.data ?? []).length === 0 ? (
            <p className="text-xs text-text-secondary">
              입고(GR) 이력이 있는 공급사가 없습니다. 샘플 데이터셋은 재고를 스냅샷으로 직접 적재해
              구매→입고 트랜잭션 이력이 없기 때문입니다 — 실제 구매발주→입고처리를 진행하면 집계됩니다.
            </p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow><TableHead>공급사</TableHead><TableHead className="text-right">입고 건수</TableHead><TableHead className="text-right">지연 건수</TableHead><TableHead className="text-right">지연율</TableHead><TableHead>리스크</TableHead></TableRow>
              </TableHeader>
              <TableBody>
                {(risk.data ?? []).map((r) => (
                  <TableRow key={r.vendor_id}>
                    <TableCell>{r.vendor_name}</TableCell>
                    <TableCell className="text-right">{r.total}</TableCell>
                    <TableCell className="text-right">{r.delayed}</TableCell>
                    <TableCell className="text-right">{(r.delay_rate * 100).toFixed(1)}%</TableCell>
                    <TableCell>{r.risk_level}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </Card>
      )}
    </div>
  )
}
