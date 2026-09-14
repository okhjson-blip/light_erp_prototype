import { Badge } from '@/components/ui/badge'

/* ui-identity.md의 semantic 매핑을 상태값 전체에 일관 적용한다:
   완료/정상 계열 = success, 대기 계열 = warning, 진행중 계열 = info, 오류/반려 계열 = danger.
   SO(OPEN→DELIVERED→INVOICED) / PO(OPEN→RECEIVED) / PR(OPEN→CONVERTED) / 승인(PENDING/APPROVED/REJECTED) 전부 포괄. */
const SUCCESS = new Set(['INVOICED', 'RECEIVED', 'COMPLETED', 'APPROVED'])
const INFO = new Set(['DELIVERED', 'CONVERTED', 'IN_PROGRESS', 'SHIPPED'])
const WARNING = new Set(['OPEN', 'PLANNED', 'PENDING'])
const DANGER = new Set(['REJECTED', 'DEFECTIVE', 'SCRAPPED'])

export function StatusBadge({ status }: { status: string }) {
  const variant = SUCCESS.has(status)
    ? 'success'
    : INFO.has(status)
      ? 'info'
      : WARNING.has(status)
        ? 'warning'
        : DANGER.has(status)
          ? 'danger'
          : 'neutral'
  return <Badge variant={variant}>{status}</Badge>
}
