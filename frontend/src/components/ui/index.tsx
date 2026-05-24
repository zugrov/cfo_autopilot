import { ReactNode } from 'react'
import clsx from 'clsx'

type Props = {
  children: ReactNode
  className?: string
}

export function Card({ children, className }: Props) {
  return (
    <div className={clsx('bg-white rounded-xl border border-neutral-200 p-4', className)}>
      {children}
    </div>
  )
}

type BadgeProps = {
  variant: 'alert' | 'warn' | 'ok' | 'info'
  children: ReactNode
}

export function Badge({ variant, children }: BadgeProps) {
  const styles = {
    alert: 'bg-alert-soft text-alert border-alert/20',
    warn: 'bg-warn-soft text-warn border-warn/20',
    ok: 'bg-ok-soft text-ok border-ok/20',
    info: 'bg-neutral-100 text-neutral-700 border-neutral-200',
  }
  return (
    <span
      className={clsx(
        'inline-flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-full border',
        styles[variant],
      )}
    >
      {children}
    </span>
  )
}

type SkeletonProps = { className?: string }

export function Skeleton({ className }: SkeletonProps) {
  return <div className={clsx('animate-pulse bg-neutral-200 rounded', className)} />
}
