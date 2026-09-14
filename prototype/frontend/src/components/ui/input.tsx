import * as React from 'react'
import { cn } from '@/lib/utils'

function Input({ className, type, ...props }: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      type={type}
      className={cn(
        'h-9 w-full rounded-control border border-border-default bg-card px-3 text-sm text-text-primary placeholder:text-text-secondary focus:border-brand focus:outline-none',
        className,
      )}
      {...props}
    />
  )
}

export { Input }
