'use client'

import { useState, useRef } from 'react'
import { api } from '@/lib/api'

type Props = {
  onSuccess: () => void
  onClose: () => void
}

type SourceType = 'bank' | 'onec'

const BANKS = [
  { key: 'sber', label: 'Сбербанк' },
  { key: 'tinkoff', label: 'Тинькофф / Т-Банк' },
  { key: 'cbe', label: '1С ClientBankExchange' },
]

export function UploadModal({ onSuccess, onClose }: Props) {
  const [sourceType, setSourceType] = useState<SourceType>('bank')
  const [bankKey, setBankKey] = useState('sber')
  const [file, setFile] = useState<File | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [hint, setHint] = useState<string | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  async function handleUpload() {
    if (!file) return
    setIsLoading(true)
    setError(null)
    setHint(null)
    try {
      let result: Record<string, unknown>
      if (sourceType === 'onec') {
        result = await api.uploadOneC(file)
        if (result.status === 'failed') {
          setError((result.error_log as { error: string }[])?.[0]?.error ?? 'Ошибка при загрузке')
          return
        }
        const meta = result.meta as { forecast_ready?: boolean } | null
        if (meta && !meta.forecast_ready) {
          setHint('Для прогноза загрузите ОСВ с aging-колонками (0–30, 31–60, 61–90, 90+) или детализацию счёта 62.')
        }
        onSuccess()
        onClose()
      } else {
        result = await api.uploadCsv(file, bankKey)
        if (result.status === 'failed') {
          setError((result.error_log as { error: string }[])?.[0]?.error ?? 'Ошибка при загрузке')
          return
        }
        onSuccess()
        onClose()
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Ошибка при загрузке')
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="bg-white rounded-2xl shadow-xl p-6 w-full max-w-sm">
        <h2 className="text-lg font-semibold text-neutral-900 mb-4">Загрузить данные</h2>

        <div className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-neutral-500 mb-1">Источник</label>
            <div className="flex rounded-lg border border-neutral-200 overflow-hidden">
              <button
                onClick={() => setSourceType('bank')}
                className={`flex-1 py-2 text-sm font-medium transition-colors ${
                  sourceType === 'bank'
                    ? 'bg-neutral-900 text-white'
                    : 'text-neutral-600 hover:bg-neutral-50'
                }`}
              >
                Банк
              </button>
              <button
                onClick={() => setSourceType('onec')}
                className={`flex-1 py-2 text-sm font-medium transition-colors ${
                  sourceType === 'onec'
                    ? 'bg-neutral-900 text-white'
                    : 'text-neutral-600 hover:bg-neutral-50'
                }`}
              >
                1С ОСВ
              </button>
            </div>
          </div>

          {sourceType === 'bank' && (
            <div>
              <label className="block text-xs font-medium text-neutral-500 mb-1">Банк</label>
              <select
                value={bankKey}
                onChange={(e) => setBankKey(e.target.value)}
                className="w-full border border-neutral-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-trust/30"
              >
                {BANKS.map((b) => (
                  <option key={b.key} value={b.key}>
                    {b.label}
                  </option>
                ))}
              </select>
            </div>
          )}

          {sourceType === 'onec' && (
            <p className="text-xs text-neutral-500 bg-neutral-50 rounded-lg px-3 py-2">
              Оборотно-сальдовая ведомость (CSV, разделитель&nbsp;«;»). Для учёта в прогнозе нужны
              aging-колонки: 0–30, 31–60, 61–90, 90+.
            </p>
          )}

          <div>
            <label className="block text-xs font-medium text-neutral-500 mb-1">CSV файл</label>
            <div
              onClick={() => inputRef.current?.click()}
              className="border-2 border-dashed border-neutral-200 rounded-lg p-4 text-center cursor-pointer hover:border-trust/40 transition-colors"
            >
              {file ? (
                <p className="text-sm text-neutral-700">{file.name}</p>
              ) : (
                <p className="text-sm text-neutral-400">Нажмите для выбора файла</p>
              )}
            </div>
            <input
              ref={inputRef}
              type="file"
              accept=".csv,.txt"
              className="hidden"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            />
          </div>

          {isLoading && (
            <div className="w-full bg-neutral-100 rounded-full h-1.5">
              <div className="bg-trust h-1.5 rounded-full animate-pulse w-2/3" />
            </div>
          )}

          {error && <p className="text-xs text-alert">{error}</p>}
          {hint && <p className="text-xs text-neutral-500 bg-amber-50 rounded-lg px-3 py-2">{hint}</p>}

          <div className="flex gap-2 pt-2">
            <button
              onClick={onClose}
              className="flex-1 border border-neutral-200 text-neutral-600 font-medium py-2 rounded-lg text-sm hover:bg-neutral-50"
            >
              Отмена
            </button>
            <button
              onClick={handleUpload}
              disabled={!file || isLoading}
              className="flex-1 bg-trust text-white font-medium py-2 rounded-lg text-sm hover:bg-trust-dark disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {isLoading ? 'Загружаем…' : 'Загрузить'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
