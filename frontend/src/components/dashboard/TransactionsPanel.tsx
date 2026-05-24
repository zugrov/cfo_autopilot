'use client'

import { useState, useEffect, useCallback } from 'react'
import { api, TransactionItem } from '@/lib/api'

type Props = {
  onClose: () => void
}

function formatAmount(n: number): string {
  return `₽${n.toLocaleString('ru-RU')}`
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('ru-RU', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  })
}

export function TransactionsPanel({ onClose }: Props) {
  const [transactions, setTransactions] = useState<TransactionItem[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [isLoadingMore, setIsLoadingMore] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [hasMore, setHasMore] = useState(true)

  const PAGE_SIZE = 50

  const load = useCallback(async (offset = 0, append = false) => {
    if (offset === 0) {
      setIsLoading(true)
    } else {
      setIsLoadingMore(true)
    }
    setError(null)
    try {
      const data = await api.listTransactions(PAGE_SIZE, offset)
      const batch = data.transactions
      setTransactions((prev) => (append ? [...prev, ...batch] : batch))
      setHasMore(batch.length === PAGE_SIZE)
    } catch {
      setError('Не удалось загрузить операции')
    } finally {
      setIsLoading(false)
      setIsLoadingMore(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const handleLoadMore = () => {
    load(transactions.length, true)
  }

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center">
      <div className="absolute inset-0 bg-black/30" onClick={onClose} />
      <div className="relative bg-white w-full sm:max-w-lg sm:rounded-xl shadow-xl max-h-[90vh] flex flex-col">
        <div className="flex items-center justify-between px-4 py-3 border-b border-neutral-100">
          <h2 className="text-sm font-semibold text-neutral-900">Банковские операции</h2>
          <button
            onClick={onClose}
            className="text-neutral-400 hover:text-neutral-600 transition-colors text-lg leading-none"
          >
            ×
          </button>
        </div>

        <div className="overflow-y-auto flex-1 px-4 py-3 space-y-1">
          {error && (
            <p className="text-xs text-red-500 bg-red-50 rounded px-3 py-2">{error}</p>
          )}

          {isLoading ? (
            <div className="space-y-2">
              {[1, 2, 3, 4].map((i) => (
                <div key={i} className="h-14 bg-neutral-100 rounded animate-pulse" />
              ))}
            </div>
          ) : transactions.length === 0 ? (
            <p className="text-xs text-neutral-400 text-center py-8">
              Нет операций — загрузите банковскую выписку
            </p>
          ) : (
            <>
              {transactions.map((tx, i) => (
                <div
                  key={`${tx.date}-${tx.amount}-${i}`}
                  className="flex items-start justify-between py-2.5 px-3 rounded-lg hover:bg-neutral-50 gap-3"
                >
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium text-neutral-900 truncate">
                      {tx.counterparty || '—'}
                    </p>
                    {tx.purpose && (
                      <p className="text-xs text-neutral-500 truncate mt-0.5">{tx.purpose}</p>
                    )}
                    <p className="text-xs text-neutral-400 mt-0.5">{formatDate(tx.date)}</p>
                  </div>
                  <p
                    className={`text-sm font-semibold shrink-0 ${
                      tx.direction === 'credit' ? 'text-green-600' : 'text-red-500'
                    }`}
                  >
                    {tx.direction === 'credit' ? '+' : '−'}
                    {formatAmount(tx.amount)}
                  </p>
                </div>
              ))}

              {hasMore && (
                <button
                  onClick={handleLoadMore}
                  disabled={isLoadingMore}
                  className="w-full py-2 mt-2 text-xs font-medium text-neutral-600 border border-neutral-200 rounded-lg hover:bg-neutral-50 disabled:opacity-50 transition-colors"
                >
                  {isLoadingMore ? 'Загрузка…' : 'Показать ещё'}
                </button>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  )
}
