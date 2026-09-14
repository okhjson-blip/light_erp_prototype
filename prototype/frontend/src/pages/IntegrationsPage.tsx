import { useState, type ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Factory, Boxes } from 'lucide-react'
import { apiGet } from '@/lib/api'
import { Card, CardHeader, CardTitle } from '@/components/ui/card'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table'
import { Button } from '@/components/ui/button'
import { StatusBadge } from '@/components/StatusBadge'
import type { IntegrationEvent } from '@/lib/types'

const SOURCE_ICON: Record<string, ReactNode> = {
  MES: <Factory size={14} className="text-role-production" />,
  WMS: <Boxes size={14} className="text-brand" />,
}

export default function IntegrationsPage() {
  const [expanded, setExpanded] = useState<Set<number>>(new Set())

  const events = useQuery({
    queryKey: ['integration-events'],
    queryFn: () => apiGet<IntegrationEvent[]>('/api/integrations/events'),
  })

  function toggle(eventId: number) {
    setExpanded((prev) => {
      const next = new Set(prev)
      if (next.has(eventId)) next.delete(eventId)
      else next.add(eventId)
      return next
    })
  }

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold text-text-primary">연동 로그</h1>
      <p className="text-xs text-text-secondary">
        실제 MES/WMS 시스템이 아직 없어 <code>simulate_mes_wms.py</code> 스크립트로 Webhook 이벤트를
        시뮬레이션합니다. 아래는 수신된 이벤트 로그입니다.
      </p>

      <Card>
        <CardHeader>
          <CardTitle>이벤트 로그</CardTitle>
        </CardHeader>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>#</TableHead>
              <TableHead>시스템</TableHead>
              <TableHead>이벤트</TableHead>
              <TableHead>상태</TableHead>
              <TableHead>페이로드</TableHead>
              <TableHead>수신시각</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {(events.data ?? []).map((e) => (
              <TableRow key={e.event_id}>
                <TableCell>{e.event_id}</TableCell>
                <TableCell>
                  <span className="flex items-center gap-1">
                    {SOURCE_ICON[e.source_system]}
                    {e.source_system}
                  </span>
                </TableCell>
                <TableCell>{e.event_type}</TableCell>
                <TableCell>
                  <StatusBadge status={e.status} />
                </TableCell>
                <TableCell className="max-w-xs">
                  {expanded.has(e.event_id) ? (
                    <pre className="whitespace-pre-wrap break-all text-xs text-text-secondary">{e.payload_json}</pre>
                  ) : (
                    <Button type="button" size="sm" variant="ghost" onClick={() => toggle(e.event_id)}>
                      보기
                    </Button>
                  )}
                </TableCell>
                <TableCell>{e.received_at}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Card>
    </div>
  )
}
