import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Sparkles } from 'lucide-react'
import { apiGet, apiPost, ApiError } from '@/lib/api'
import { useAuth } from '@/lib/auth-context'
import { Card, CardHeader, CardTitle } from '@/components/ui/card'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { AiNarrative } from '@/components/AiNarrative'
import type {
  BuyerRecommendation,
  SchedulerRecommendation,
  DemandPlannerRecommendation,
  QualityRecommendation,
  CfoInsight,
} from '@/lib/types'

function AgentCardHeader({ title }: { title: string }) {
  return (
    <CardHeader>
      <CardTitle>
        <span className="flex items-center gap-1.5">
          <Sparkles size={14} className="text-brand" />
          {title}
        </span>
      </CardTitle>
    </CardHeader>
  )
}

export default function AiAgentPage() {
  const { hasRole } = useAuth()
  const canApply = hasRole('관리자')
  const qc = useQueryClient()
  const [msg, setMsg] = useState('')
  const [error, setError] = useState('')

  const buyer = useQuery({
    queryKey: ['ai-buyer'],
    queryFn: () => apiGet<BuyerRecommendation[]>('/api/ai/buyer/recommendations'),
  })
  const scheduler = useQuery({
    queryKey: ['ai-scheduler'],
    queryFn: () => apiGet<SchedulerRecommendation[]>('/api/ai/scheduler/recommendations'),
  })
  const demandPlanner = useQuery({
    queryKey: ['ai-demand-planner'],
    queryFn: () => apiGet<DemandPlannerRecommendation[]>('/api/ai/demand-planner/recommendations'),
  })
  const quality = useQuery({
    queryKey: ['ai-quality'],
    queryFn: () => apiGet<QualityRecommendation[]>('/api/ai/quality/recommendations'),
  })
  const cfo = useQuery({
    queryKey: ['ai-cfo'],
    queryFn: () => apiGet<CfoInsight[]>('/api/ai/cfo-copilot/insights'),
    enabled: canApply, // v5: CFO Copilot도 재무 민감정보라 조회도 관리자 전용
  })

  const applyBuyer = useMutation({
    mutationFn: (body: { material_id: number; qty: number }) =>
      apiPost<{ pr_id: number }>('/api/ai/buyer/apply', body),
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ['ai-buyer'] })
      setMsg(`추천이 PR#${data.pr_id}로 생성되었습니다 (승인함에서 승인 필요).`)
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : '적용 실패'),
  })
  const applyDemandPlanner = useMutation({
    mutationFn: (body: { material_id: number; reorder_point: number; target_stock: number }) =>
      apiPost('/api/ai/demand-planner/apply', body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['ai-demand-planner'] })
      setMsg('재발주점/목표재고가 갱신되었습니다.')
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : '적용 실패'),
  })

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold text-text-primary">AI Agent 추천 (Human-in-the-loop)</h1>
      <p className="text-xs text-text-secondary">규칙기반 추천만 제공하며, 실제 실행은 사람이 버튼을 눌러야 합니다.</p>
      {error && <p className="text-xs text-danger">{error}</p>}
      {msg && <p className="text-xs text-success">{msg}</p>}

      <Card>
        <AgentCardHeader title="AI Buyer — 재발주 추천" />
        {(buyer.data ?? []).length === 0 ? (
          <p className="text-xs text-text-secondary">재발주 필요 품목 없음</p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>코드</TableHead>
                <TableHead>품목</TableHead>
                <TableHead className="text-right">현재고</TableHead>
                <TableHead className="text-right">재발주점</TableHead>
                <TableHead className="text-right">추천발주량</TableHead>
                <TableHead>추천공급사</TableHead>
                <TableHead>근거 / AI 설명</TableHead>
                {canApply && <TableHead>액션</TableHead>}
              </TableRow>
            </TableHeader>
            <TableBody>
              {(buyer.data ?? []).map((r) => (
                <TableRow key={r.material_id}>
                  <TableCell>{r.code}</TableCell>
                  <TableCell>{r.name}</TableCell>
                  <TableCell className="text-right">{r.current_qty}</TableCell>
                  <TableCell className="text-right">{r.reorder_point}</TableCell>
                  <TableCell className="text-right">{r.suggested_qty}</TableCell>
                  <TableCell>{r.recommended_vendor_name}</TableCell>
                  <TableCell className="space-y-1">
                    <p>{r.rationale}</p>
                    <AiNarrative text={r.ai_narrative} />
                  </TableCell>
                  {canApply && (
                    <TableCell>
                      <Button
                        type="button"
                        size="sm"
                        onClick={() => applyBuyer.mutate({ material_id: r.material_id, qty: r.suggested_qty })}
                      >
                        PR 생성 적용
                      </Button>
                    </TableCell>
                  )}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </Card>

      <Card>
        <AgentCardHeader title="AI Production Scheduler — 생산 우선순위 추천" />
        {(scheduler.data ?? []).length === 0 ? (
          <p className="text-xs text-text-secondary">진행 중인 생산오더 없음</p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>우선순위</TableHead>
                <TableHead>오더#</TableHead>
                <TableHead>완제품</TableHead>
                <TableHead className="text-right">수량</TableHead>
                <TableHead>상태</TableHead>
                <TableHead>착수가능</TableHead>
                <TableHead>근거 / AI 설명</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(scheduler.data ?? []).map((r) => (
                <TableRow key={r.prod_order_id}>
                  <TableCell>{r.priority_rank}</TableCell>
                  <TableCell>{r.prod_order_id}</TableCell>
                  <TableCell>{r.material_name}</TableCell>
                  <TableCell className="text-right">{r.qty}</TableCell>
                  <TableCell>{r.status}</TableCell>
                  <TableCell>
                    <Badge variant={r.feasible ? 'success' : 'warning'}>{r.feasible ? '가능' : '불가'}</Badge>
                  </TableCell>
                  <TableCell className="space-y-1">
                    <p>{r.rationale}</p>
                    <AiNarrative text={r.ai_narrative} />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </Card>

      <Card>
        <AgentCardHeader title="AI Demand Planner — 수요예측 오차 기반 재발주점/목표재고 조정 추천" />
        {(demandPlanner.data ?? []).length === 0 ? (
          <p className="text-xs text-text-secondary">예측 정확도 저하 품목 없음</p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>코드</TableHead>
                <TableHead>품목</TableHead>
                <TableHead className="text-right">평균MAPE(%)</TableHead>
                <TableHead>방향</TableHead>
                <TableHead className="text-right">현재발주점</TableHead>
                <TableHead className="text-right">현재목표재고</TableHead>
                <TableHead className="text-right">추천재발주점</TableHead>
                <TableHead className="text-right">추천목표재고</TableHead>
                <TableHead>근거 / AI 설명</TableHead>
                {canApply && <TableHead>액션</TableHead>}
              </TableRow>
            </TableHeader>
            <TableBody>
              {(demandPlanner.data ?? []).map((r) => (
                <TableRow key={r.material_id}>
                  <TableCell>{r.code}</TableCell>
                  <TableCell>{r.name}</TableCell>
                  <TableCell className="text-right">{r.avg_mape}</TableCell>
                  <TableCell>{r.direction}</TableCell>
                  <TableCell className="text-right">{r.current_reorder_point}</TableCell>
                  <TableCell className="text-right">{r.current_target_stock}</TableCell>
                  <TableCell className="text-right">{r.suggested_reorder_point}</TableCell>
                  <TableCell className="text-right">{r.suggested_target_stock}</TableCell>
                  <TableCell className="space-y-1">
                    <p>{r.rationale}</p>
                    <AiNarrative text={r.ai_narrative} />
                  </TableCell>
                  {canApply && (
                    <TableCell>
                      <Button
                        type="button"
                        size="sm"
                        onClick={() =>
                          applyDemandPlanner.mutate({
                            material_id: r.material_id,
                            reorder_point: r.suggested_reorder_point,
                            target_stock: r.suggested_target_stock,
                          })
                        }
                      >
                        계획값 적용
                      </Button>
                    </TableCell>
                  )}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </Card>

      <Card>
        <AgentCardHeader title="AI Quality Engineer — 품질 리스크 추천 (조회전용)" />
        {(quality.data ?? []).length === 0 ? (
          <p className="text-xs text-text-secondary">품질 리스크 품목 없음</p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>코드</TableHead>
                <TableHead>품목</TableHead>
                <TableHead className="text-right">평균PPM</TableHead>
                <TableHead className="text-right">최근불량건수</TableHead>
                <TableHead className="text-right">CAPA필요건수</TableHead>
                <TableHead>위험도</TableHead>
                <TableHead>근거 / AI 설명</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(quality.data ?? []).map((r, i) => (
                <TableRow key={i}>
                  <TableCell>{r.code}</TableCell>
                  <TableCell>{r.name}</TableCell>
                  <TableCell className="text-right">{r.avg_defect_ppm}</TableCell>
                  <TableCell className="text-right">{r.recent_fail_count}</TableCell>
                  <TableCell className="text-right">{r.recent_capa_count}</TableCell>
                  <TableCell>
                    <Badge variant={r.risk_level === '높음' ? 'danger' : 'warning'}>{r.risk_level}</Badge>
                  </TableCell>
                  <TableCell className="space-y-1">
                    <p>{r.rationale}</p>
                    <AiNarrative text={r.ai_narrative} />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </Card>

      <Card>
        <div className="mb-3 flex items-center justify-between">
          <AgentCardHeader title="CFO Copilot — 재무/현금흐름 인사이트 (조회전용)" />
          <Badge variant="info">관리자 전용</Badge>
        </div>
        {!canApply ? (
          <p className="text-xs text-text-secondary">관리자만 조회 가능</p>
        ) : (cfo.data ?? []).length === 0 ? (
          <p className="text-xs text-text-secondary">인사이트 없음</p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>제목</TableHead>
                <TableHead>내용</TableHead>
                <TableHead>심각도</TableHead>
                <TableHead>AI 설명</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(cfo.data ?? []).map((r, i) => (
                <TableRow key={i}>
                  <TableCell>{r.title}</TableCell>
                  <TableCell>{r.detail}</TableCell>
                  <TableCell>
                    <Badge variant={r.severity === '높음' ? 'danger' : r.severity === '중간' ? 'warning' : 'neutral'}>
                      {r.severity}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <AiNarrative text={r.ai_narrative} />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </Card>
    </div>
  )
}
