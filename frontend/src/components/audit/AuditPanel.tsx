'use client'

import { useState, useEffect, useCallback } from 'react'
import { api, AuditEntry } from '@/lib/api'

type Props = {
  onClose: () => void
}

const ACTION_LABELS: Record<string, string> = {
  import_bank_csv: 'Загрузка банковской выписки',
  import_onec_osv: 'Загрузка выгрузки 1С',
  create_obligation: 'Создание обязательства',
  mark_obligation_paid: 'Обязательство отмечено оплаченным',
  invite_user: 'Приглашение пользователя',
  update_user: 'Изменение пользователя',
  onboarding_dismiss: 'Onboarding завершён',
  onboarding_skip: 'Шаг onboarding пропущен',
  weekly_report_sent: 'Управленческий отчёт',
}

function formatDetail(entry: AuditEntry): string {
  const meta = entry.metadata || {}
  switch (entry.action) {
    case 'import_bank_csv':
      return [meta.filename, meta.bank ? `банк: ${meta.bank}` : null]
        .filter(Boolean)
        .join(' · ')
    case 'import_onec_osv':
      return meta.filename ? String(meta.filename) : ''
    case 'invite_user':
      return meta.email ? `${meta.email} (${meta.role})` : ''
    case 'update_user':
      return Object.entries(meta)
        .map(([k, v]) => `${k}: ${v}`)
        .join(', ')
    case 'weekly_report_sent':
      return meta.channel === 'email'
        ? `email: ${(meta.recipients as string[] | undefined)?.join(', ') || '—'}`
        : 'скачивание PDF'
    case 'onboarding_skip':
      return meta.step ? `шаг: ${meta.step}` : ''
    default:
      return entry.entity ? `${entry.entity}` : ''
  }
}

function formatDate(iso: string | null): string {
  if (!iso) return '—'
  const d = new Date(iso)
  return d.toLocaleString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function AuditPanel({ onClose }: Props) {
  const [entries, setEntries] = useState<AuditEntry[]>([])
  const [total, setTotal] = useState(0)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      const data = await api.listAuditLog()
      setEntries(data.entries)
      setTotal(data.total)
    } catch {
      setError('Не удалось загрузить журнал')
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center">
      <div className="absolute inset-0 bg-black/30" onClick={onClose} />
      <div className="relative bg-white w-full sm:max-w-lg sm:rounded-xl shadow-xl max-h-[90vh] flex flex-col">
        <div className="flex items-center justify-between px-4 py-3 border-b border-neutral-100">
          <h2 className="text-sm font-semibold text-neutral-900">Журнал действий</h2>
          <button
            onClick={onClose}
            className="text-neutral-400 hover:text-neutral-600 transition-colors text-lg leading-none"
          >
            ×
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-4 py-3">
          {isLoading && (
            <p className="text-sm text-neutral-500">Загрузка…</p>
          )}
          {error && (
            <p className="text-sm text-red-600">{error}</p>
          )}
          {!isLoading && !error && entries.length === 0 && (
            <p className="text-sm text-neutral-500">Записей пока нет</p>
          )}
          {!isLoading && entries.length > 0 && (
            <ul className="space-y-3">
              {entries.map((entry) => {
                const detail = formatDetail(entry)
                return (
                  <li
                    key={entry.id}
                    className="border border-neutral-100 rounded-lg px-3 py-2"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <p className="text-sm font-medium text-neutral-900">
                        {ACTION_LABELS[entry.action] || entry.action}
                      </p>
                      <time className="text-xs text-neutral-400 shrink-0">
                        {formatDate(entry.at)}
                      </time>
                    </div>
                    {entry.user_email && (
                      <p className="text-xs text-neutral-500 mt-0.5">{entry.user_email}</p>
                    )}
                    {detail && (
                      <p className="text-xs text-neutral-600 mt-1">{detail}</p>
                    )}
                  </li>
                )
              })}
            </ul>
          )}
        </div>

        {!isLoading && total > entries.length && (
          <p className="px-4 py-2 text-xs text-neutral-400 border-t border-neutral-100">
            Показано {entries.length} из {total}
          </p>
        )}
      </div>
    </div>
  )
}
