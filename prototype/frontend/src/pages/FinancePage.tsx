import { useQuery } from '@tanstack/react-query'
import { apiGet } from '@/lib/api'
import { useAuth } from '@/lib/auth-context'
import { Card, CardHeader, CardTitle } from '@/components/ui/card'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import { StatusBadge } from '@/components/StatusBadge'
import type { AccountingDocument } from '@/lib/types'

// v5 정책: 회계 전표는 조회도 관리자 전용(재무 민감정보) — 백엔드 require_roles("관리자")와
// 동일하게 프론트에서도 안내 배지로 명시한다(ui-identity.md "관리자 전용 안내 배지" 규칙).
export default function FinancePage() {
  const { hasRole } = useAuth()
  const isAdmin = hasRole('관리자')

  const docs = useQuery({
    queryKey: ['accounting-documents'],
    queryFn: () => apiGet<AccountingDocument[]>('/api/accounting/documents'),
    enabled: isAdmin,
  })

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <h1 className="text-xl font-semibold text-text-primary">회계</h1>
        <Badge variant="info">관리자 전용</Badge>
      </div>

      {!isAdmin ? (
        <Card>
          <p className="text-sm text-text-secondary">회계 전표는 재무 민감정보라 관리자만 조회할 수 있습니다.</p>
        </Card>
      ) : (
        <Card>
          <CardHeader>
            <CardTitle>전표 목록</CardTitle>
          </CardHeader>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>전표#</TableHead>
                <TableHead>유형</TableHead>
                <TableHead>일자</TableHead>
                <TableHead>적요</TableHead>
                <TableHead>상태</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(docs.data ?? []).map((d) => (
                <TableRow key={d.doc_id}>
                  <TableCell>{d.doc_id}</TableCell>
                  <TableCell>{d.doc_type}</TableCell>
                  <TableCell>{d.posting_date}</TableCell>
                  <TableCell>{d.description}</TableCell>
                  <TableCell>
                    <StatusBadge status={d.status} />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Card>
      )}
    </div>
  )
}
