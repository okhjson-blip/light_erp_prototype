import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiGet, apiPost, ApiError } from '@/lib/api'
import { useAuth } from '@/lib/auth-context'
import { Card, CardHeader, CardTitle } from '@/components/ui/card'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table'
import { Button } from '@/components/ui/button'
import { StatusBadge } from '@/components/StatusBadge'
import type { ApprovalWorkflow } from '@/lib/types'

export default function ApprovalsPage() {
  const { hasRole } = useAuth()
  const canDecide = hasRole('관리자')
  const qc = useQueryClient()
  const [error, setError] = useState('')
  const [msg, setMsg] = useState('')

  const approvals = useQuery({
    queryKey: ['approvals'],
    queryFn: () => apiGet<ApprovalWorkflow[]>('/api/approvals'),
  })

  const decide = useMutation({
    mutationFn: ({ workflowId, status }: { workflowId: number; status: 'APPROVED' | 'REJECTED' }) =>
      apiPost(`/api/approvals/${workflowId}/decision`, { status }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['approvals'] })
      setMsg('승인 처리되었습니다.')
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : '처리 실패'),
  })

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold text-text-primary">승인함</h1>
      {error && <p className="text-xs text-danger">{error}</p>}
      {msg && <p className="text-xs text-success">{msg}</p>}

      <Card>
        <CardHeader>
          <CardTitle>승인 대기 목록</CardTitle>
        </CardHeader>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>#</TableHead>
              <TableHead>문서유형</TableHead>
              <TableHead>문서#</TableHead>
              <TableHead>상태</TableHead>
              {canDecide && <TableHead>액션</TableHead>}
            </TableRow>
          </TableHeader>
          <TableBody>
            {(approvals.data ?? []).map((a) => (
              <TableRow key={a.workflow_id}>
                <TableCell>{a.workflow_id}</TableCell>
                <TableCell>{a.doc_type}</TableCell>
                <TableCell>{a.doc_id}</TableCell>
                <TableCell>
                  <StatusBadge status={a.status} />
                </TableCell>
                {canDecide && (
                  <TableCell>
                    {a.status === 'PENDING' && (
                      <div className="flex gap-1">
                        <Button
                          type="button"
                          size="sm"
                          variant="success"
                          onClick={() => decide.mutate({ workflowId: a.workflow_id, status: 'APPROVED' })}
                        >
                          승인
                        </Button>
                        <Button
                          type="button"
                          size="sm"
                          variant="danger"
                          onClick={() => decide.mutate({ workflowId: a.workflow_id, status: 'REJECTED' })}
                        >
                          반려
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
    </div>
  )
}
