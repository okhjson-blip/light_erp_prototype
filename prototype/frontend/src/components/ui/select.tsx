import * as React from 'react'
import { cn } from '@/lib/utils'

// 네이티브 <select>를 Input과 동일한 톤으로 스타일링만 한다(Radix 드롭다운은 이 프로토타입 규모엔
// 과설계라 판단 — CLAUDE.md "Simplicity First" 참고).
function Select({ className, ...props }: React.SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select
      className={cn(
        'h-9 w-full rounded-control border border-border-default bg-card px-3 text-sm text-text-primary focus:border-brand focus:outline-none',
        className,
      )}
      {...props}
    />
  )
}

export { Select }
