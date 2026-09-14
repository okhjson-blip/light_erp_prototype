import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { apiGet } from '@/lib/api'
import { Card } from '@/components/ui/card'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table'
import { cn } from '@/lib/utils'
import type {
  KpiMonthly,
  FinanceSummaryRef,
  DemandForecastRef,
  ShipmentRef,
  QualityInspectionRef,
  AiRecommendationLogRef,
} from '@/lib/types'

// ui-identity.md 권고대로 6개 서브테이블을 세로 나열 대신 탭으로 전환해 화면 스크롤을 줄인다
// (정보항목/데이터는 기존 static과 동일 — 표시 방식만 탭으로 변경).
const TABS = [
  { key: 'kpi', label: '월간 KPI (EIS)' },
  { key: 'fin', label: '재무 요약 (EIS)' },
  { key: 'forecast', label: '수요예측 (SCM)' },
  { key: 'shipment', label: '출하 (WMS)' },
  { key: 'quality', label: '품질검사 (QMS)' },
  { key: 'ai-log', label: 'AI 추천 이력 (AI Copilot)' },
] as const

type TabKey = (typeof TABS)[number]['key']

export default function ReferenceDataPage() {
  const [tab, setTab] = useState<TabKey>('kpi')

  const kpi = useQuery({ queryKey: ['ref-kpi'], queryFn: () => apiGet<KpiMonthly[]>('/api/reference/kpi-monthly'), enabled: tab === 'kpi' })
  const fin = useQuery({ queryKey: ['ref-fin'], queryFn: () => apiGet<FinanceSummaryRef[]>('/api/reference/finance-summary'), enabled: tab === 'fin' })
  const forecast = useQuery({ queryKey: ['ref-forecast'], queryFn: () => apiGet<DemandForecastRef[]>('/api/reference/demand-forecast'), enabled: tab === 'forecast' })
  const shipment = useQuery({ queryKey: ['ref-shipment'], queryFn: () => apiGet<ShipmentRef[]>('/api/reference/shipments'), enabled: tab === 'shipment' })
  const quality = useQuery({ queryKey: ['ref-quality'], queryFn: () => apiGet<QualityInspectionRef[]>('/api/reference/quality-inspections'), enabled: tab === 'quality' })
  const aiLog = useQuery({ queryKey: ['ref-ai-log'], queryFn: () => apiGet<AiRecommendationLogRef[]>('/api/reference/ai-recommendation-log'), enabled: tab === 'ai-log' })

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold text-text-primary">참고 데이터</h1>
      <p className="text-xs text-text-secondary">
        SCM/QMS/WMS/EIS/AI Copilot 모듈이 아직 없어, 임포트한 이력·통계성 데이터를 조회 전용으로 표시합니다.
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

      {tab === 'kpi' && (
        <Card>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>기간</TableHead>
                <TableHead className="text-right">매출</TableHead>
                <TableHead className="text-right">영업이익</TableHead>
                <TableHead className="text-right">평균OEE</TableHead>
                <TableHead className="text-right">납기준수율</TableHead>
                <TableHead className="text-right">평균PPM</TableHead>
                <TableHead className="text-right">재고회전율</TableHead>
                <TableHead className="text-right">예측정확도</TableHead>
                <TableHead className="text-right">공급리스크건수</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(kpi.data ?? []).map((r, i) => (
                <TableRow key={i}>
                  <TableCell>{r.period}</TableCell>
                  <TableCell className="text-right">{r.revenue.toLocaleString()}</TableCell>
                  <TableCell className="text-right">{r.operating_profit.toLocaleString()}</TableCell>
                  <TableCell className="text-right">{r.oee_avg}</TableCell>
                  <TableCell className="text-right">{r.otd_rate}</TableCell>
                  <TableCell className="text-right">{r.ppm_avg}</TableCell>
                  <TableCell className="text-right">{r.inventory_turnover}</TableCell>
                  <TableCell className="text-right">{r.forecast_accuracy}</TableCell>
                  <TableCell className="text-right">{r.supply_risk_count}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Card>
      )}

      {tab === 'fin' && (
        <Card>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>기간</TableHead>
                <TableHead className="text-right">매출</TableHead>
                <TableHead className="text-right">매출원가</TableHead>
                <TableHead className="text-right">매출총이익</TableHead>
                <TableHead className="text-right">영업이익</TableHead>
                <TableHead className="text-right">EBITDA</TableHead>
                <TableHead className="text-right">현금흐름</TableHead>
                <TableHead>통화</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(fin.data ?? []).map((r, i) => (
                <TableRow key={i}>
                  <TableCell>{r.period}</TableCell>
                  <TableCell className="text-right">{r.revenue.toLocaleString()}</TableCell>
                  <TableCell className="text-right">{r.cogs.toLocaleString()}</TableCell>
                  <TableCell className="text-right">{r.gross_profit.toLocaleString()}</TableCell>
                  <TableCell className="text-right">{r.operating_profit.toLocaleString()}</TableCell>
                  <TableCell className="text-right">{r.ebitda.toLocaleString()}</TableCell>
                  <TableCell className="text-right">{r.cash_flow.toLocaleString()}</TableCell>
                  <TableCell>{r.currency}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Card>
      )}

      {tab === 'forecast' && (
        <Card>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>월</TableHead>
                <TableHead>품목</TableHead>
                <TableHead className="text-right">예측수량</TableHead>
                <TableHead className="text-right">실제판매</TableHead>
                <TableHead className="text-right">MAPE(%)</TableHead>
                <TableHead>버전</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(forecast.data ?? []).map((r, i) => (
                <TableRow key={i}>
                  <TableCell>{r.forecast_month}</TableCell>
                  <TableCell>{r.material_code}</TableCell>
                  <TableCell className="text-right">{r.forecast_qty}</TableCell>
                  <TableCell className="text-right">{r.actual_sales_qty}</TableCell>
                  <TableCell className="text-right">{r.mape}</TableCell>
                  <TableCell>{r.forecast_version}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Card>
      )}

      {tab === 'shipment' && (
        <Card>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>출하#</TableHead>
                <TableHead>출하일</TableHead>
                <TableHead>고객</TableHead>
                <TableHead>품목</TableHead>
                <TableHead className="text-right">수량</TableHead>
                <TableHead>운송사</TableHead>
                <TableHead>정시여부</TableHead>
                <TableHead>상태</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(shipment.data ?? []).map((r, i) => (
                <TableRow key={i}>
                  <TableCell>{r.external_no}</TableCell>
                  <TableCell>{r.shipment_date}</TableCell>
                  <TableCell>{r.customer_name}</TableCell>
                  <TableCell>{r.material_code}</TableCell>
                  <TableCell className="text-right">{r.shipped_qty}</TableCell>
                  <TableCell>{r.carrier}</TableCell>
                  <TableCell>{r.otd_flag}</TableCell>
                  <TableCell>{r.status}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Card>
      )}

      {tab === 'quality' && (
        <Card>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>검사일</TableHead>
                <TableHead>품목</TableHead>
                <TableHead>유형</TableHead>
                <TableHead className="text-right">샘플수</TableHead>
                <TableHead className="text-right">불량수</TableHead>
                <TableHead className="text-right">PPM</TableHead>
                <TableHead>결과</TableHead>
                <TableHead>CAPA필요</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(quality.data ?? []).map((r, i) => (
                <TableRow key={i}>
                  <TableCell>{r.inspection_date}</TableCell>
                  <TableCell>{r.material_code}</TableCell>
                  <TableCell>{r.inspection_type}</TableCell>
                  <TableCell className="text-right">{r.sample_qty}</TableCell>
                  <TableCell className="text-right">{r.defect_qty}</TableCell>
                  <TableCell className="text-right">{r.defect_ppm}</TableCell>
                  <TableCell>{r.result}</TableCell>
                  <TableCell>{r.capa_required}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Card>
      )}

      {tab === 'ai-log' && (
        <Card>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>일자</TableHead>
                <TableHead>에이전트</TableHead>
                <TableHead>제목</TableHead>
                <TableHead className="text-right">신뢰도</TableHead>
                <TableHead>영향도</TableHead>
                <TableHead>상태</TableHead>
                <TableHead>대상모듈</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(aiLog.data ?? []).map((r, i) => (
                <TableRow key={i}>
                  <TableCell>{r.created_at}</TableCell>
                  <TableCell>{r.agent}</TableCell>
                  <TableCell>{r.title}</TableCell>
                  <TableCell className="text-right">{r.confidence}</TableCell>
                  <TableCell>{r.impact}</TableCell>
                  <TableCell>{r.status}</TableCell>
                  <TableCell>{r.target_module}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Card>
      )}
    </div>
  )
}
