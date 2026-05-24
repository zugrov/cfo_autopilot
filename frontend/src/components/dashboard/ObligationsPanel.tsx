'use client'

import { useState, useEffect, useCallback } from 'react'
import { api, ObligationItem } from '@/lib/api'

type Props = {
  onClose: () => void
  onRefreshDashboard: () => void
}

type FormState = {
  due_date: string
  amount: string
  description: string
  is_recurring: boolean
}

const EMPTY_FORM: FormState = {
  due_date: '',
  amount: '',
  description: '',
  is_recurring: false,
}

function formatAmount(n: number): string {
  return `₽${n.toLocaleString('ru-RU')}`
}

function daysLabel(dueDate: string): string {
  const diff = Math.ceil(
    (new Date(dueDate).getTime() - new Date().setHours(0, 0, 0, 0)) / 86400000
  )
  if (diff < 0) return `просрочено ${Math.abs(diff)} дн.`
  if (diff === 0) return 'сегодня'
  if (diff === 1) return 'завтра'
  return `через ${diff} дн.`
}

function statusBadge(status: string, dueDate: string): string {
  if (status === 'paid') return 'text-green-600'
  const diff = Math.ceil(
    (new Date(dueDate).getTime() - new Date().setHours(0, 0, 0, 0)) / 86400000
  )
  if (diff < 0) return 'text-red-500'
  if (diff <= 3) return 'text-amber-500'
  return 'text-neutral-500'
}

export function ObligationsPanel({ onClose, onRefreshDashboard }: Props) {
  const [obligations, setObligations] = useState<ObligationItem[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState<FormState>(EMPTY_FORM)
  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [payingId, setPayingId] = useState<string | null>(null)

  const load = useCallback(async () => {
    setIsLoading(true)
    try {
      const data = await api.listObligations()
      setObligations(data.obligations)
    } catch {
      setError('Не удалось загрузить обязательства')
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsSaving(true)
    setError(null)
    try {
      await api.createObligation({
        due_date: form.due_date,
        amount: parseFloat(form.amount),
        description: form.description,
        is_recurring: form.is_recurring,
      })
      setForm(EMPTY_FORM)
      setShowForm(false)
      await load()
      onRefreshDashboard()
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Ошибка создания')
    } finally {
      setIsSaving(false)
    }
  }

  const handlePay = async (id: string) => {
    setPayingId(id)
    try {
      await api.payObligation(id)
      await load()
      onRefreshDashboard()
    } catch {
      setError('Ошибка при обновлении статуса')
    } finally {
      setPayingId(null)
    }
  }

  const pending = obligations.filter((o) => o.status === 'pending')
  const paid = obligations.filter((o) => o.status === 'paid')

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center">
      <div className="absolute inset-0 bg-black/30" onClick={onClose} />
      <div className="relative bg-white w-full sm:max-w-lg sm:rounded-xl shadow-xl max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-neutral-100">
          <h2 className="text-sm font-semibold text-neutral-900">Платёжный календарь</h2>
          <button
            onClick={onClose}
            className="text-neutral-400 hover:text-neutral-600 transition-colors text-lg leading-none"
          >
            ×
          </button>
        </div>

        {/* Content */}
        <div className="overflow-y-auto flex-1 px-4 py-3 space-y-4">
          {error && (
            <p className="text-xs text-red-500 bg-red-50 rounded px-3 py-2">{error}</p>
          )}

          {/* Форма создания */}
          {showForm ? (
            <form onSubmit={handleCreate} className="border border-neutral-200 rounded-lg p-3 space-y-2">
              <p className="text-xs font-medium text-neutral-700 mb-1">Новое обязательство</p>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block text-xs text-neutral-500 mb-0.5">Дата</label>
                  <input
                    type="date"
                    required
                    value={form.due_date}
                    onChange={(e) => setForm((f) => ({ ...f, due_date: e.target.value }))}
                    className="w-full px-2 py-1.5 text-sm border border-neutral-200 rounded outline-none focus:border-neutral-400"
                  />
                </div>
                <div>
                  <label className="block text-xs text-neutral-500 mb-0.5">Сумма, ₽</label>
                  <input
                    type="number"
                    required
                    min="1"
                    step="0.01"
                    value={form.amount}
                    onChange={(e) => setForm((f) => ({ ...f, amount: e.target.value }))}
                    placeholder="150000"
                    className="w-full px-2 py-1.5 text-sm border border-neutral-200 rounded outline-none focus:border-neutral-400"
                  />
                </div>
              </div>
              <div>
                <label className="block text-xs text-neutral-500 mb-0.5">Описание</label>
                <input
                  type="text"
                  required
                  value={form.description}
                  onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
                  placeholder="Зарплата, аренда, налог..."
                  className="w-full px-2 py-1.5 text-sm border border-neutral-200 rounded outline-none focus:border-neutral-400"
                />
              </div>
              <label className="flex items-center gap-2 text-xs text-neutral-600 cursor-pointer">
                <input
                  type="checkbox"
                  checked={form.is_recurring}
                  onChange={(e) => setForm((f) => ({ ...f, is_recurring: e.target.checked }))}
                  className="rounded"
                />
                Повторяющееся (ежемесячно)
              </label>
              <div className="flex gap-2 pt-1">
                <button
                  type="submit"
                  disabled={isSaving}
                  className="flex-1 py-1.5 text-xs font-medium bg-neutral-900 text-white rounded hover:bg-neutral-800 disabled:opacity-50 transition-colors"
                >
                  {isSaving ? 'Сохранение…' : 'Сохранить'}
                </button>
                <button
                  type="button"
                  onClick={() => { setShowForm(false); setForm(EMPTY_FORM) }}
                  className="px-3 py-1.5 text-xs text-neutral-500 border border-neutral-200 rounded hover:bg-neutral-50 transition-colors"
                >
                  Отмена
                </button>
              </div>
            </form>
          ) : (
            <button
              onClick={() => setShowForm(true)}
              className="w-full py-2 text-xs font-medium text-neutral-600 border border-dashed border-neutral-300 rounded-lg hover:bg-neutral-50 transition-colors"
            >
              + Добавить обязательство
            </button>
          )}

          {/* Ожидающие */}
          {isLoading ? (
            <div className="space-y-2">
              {[1, 2, 3].map((i) => (
                <div key={i} className="h-12 bg-neutral-100 rounded animate-pulse" />
              ))}
            </div>
          ) : pending.length === 0 && !showForm ? (
            <p className="text-xs text-neutral-400 text-center py-4">
              Нет предстоящих обязательств
            </p>
          ) : (
            <div className="space-y-1">
              {pending.map((o) => (
                <div
                  key={o.id}
                  className="flex items-center justify-between py-2 px-3 rounded-lg hover:bg-neutral-50 group"
                >
                  <div className="min-w-0 flex-1">
                    <p className="text-sm text-neutral-900 truncate">{o.description}</p>
                    <p className={`text-xs ${statusBadge(o.status, o.due_date)}`}>
                      {o.due_date} · {daysLabel(o.due_date)}
                      {o.is_recurring && ' · повтор'}
                    </p>
                  </div>
                  <div className="flex items-center gap-2 ml-3 shrink-0">
                    <span className="text-sm font-medium text-neutral-900">
                      {formatAmount(o.amount)}
                    </span>
                    <button
                      onClick={() => handlePay(o.id)}
                      disabled={payingId === o.id}
                      className="text-xs px-2 py-0.5 bg-neutral-900 text-white rounded opacity-0 group-hover:opacity-100 disabled:opacity-50 transition-all hover:bg-neutral-700"
                    >
                      {payingId === o.id ? '…' : 'Оплачено'}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Оплаченные */}
          {paid.length > 0 && (
            <details className="group">
              <summary className="text-xs text-neutral-400 cursor-pointer select-none hover:text-neutral-600 transition-colors">
                Оплаченные ({paid.length})
              </summary>
              <div className="mt-1 space-y-1">
                {paid.map((o) => (
                  <div
                    key={o.id}
                    className="flex items-center justify-between py-1.5 px-3 opacity-50"
                  >
                    <div className="min-w-0 flex-1">
                      <p className="text-sm text-neutral-600 truncate line-through">{o.description}</p>
                      <p className="text-xs text-neutral-400">{o.due_date}</p>
                    </div>
                    <span className="text-sm text-neutral-500 ml-3">{formatAmount(o.amount)}</span>
                  </div>
                ))}
              </div>
            </details>
          )}
        </div>
      </div>
    </div>
  )
}
