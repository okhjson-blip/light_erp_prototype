import type { ReactNode } from 'react'
import { Card } from '@/components/ui/card'
import { cn } from '@/lib/utils'

interface KpiCardProps {
  label: string
  value: ReactNode
  hint?: string
  tone?: 'default' | 'success' | 'warning' | 'danger'
}

const TONE_CLASS: Record<NonNullable<KpiCardProps['tone']>, string> = {
  default: 'text-text-primary',
  success: 'text-success',
  warning: 'text-warning',
  danger: 'text-danger',
}

export function KpiCard({ label, value, hint, tone = 'default' }: KpiCardProps) {
  return (
    <Card>
      <div className="text-xs text-text-secondary">{label}</div>
      <div className={cn('mt-1 text-2xl font-semibold', TONE_CLASS[tone])}>{value}</div>
      {hint && <div className="mt-1 text-xs text-text-secondary">{hint}</div>}
    </Card>
  )
}
