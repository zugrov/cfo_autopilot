'use client'

import { useState, useRef } from 'react'
import { api } from '@/lib/api'

type Props = {
  onSuccess: () => void
  onClose: () => void
}

const BANKS = [
  { key: 'sber', label: 'Сбербанк' },
  { key: 'tinkoff', label: 'Тинькофф / Т-Банк' },
  { key: 'cbe', label: '1С ClientBankExchange' },
]

export function UploadModal({ onSuccess, onClose }: Props) {
  const [bankKey, setBankKey] = useState('sber')
  const [file, setFile] = useState<File | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  async function handleUpload() {
    if (!file) return
    setIsLoading(true)
    setError(null)
    try {
      const result = await api.uploadCsv(file, bankKey)
      if (result.status === 'failed') {
        setError(result.error_log?.[0]?.error ?? 'Ошибка при загрузке')
      } else {
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
        <h2 className="text-lg font-semibold text-neutral-900 mb-4">Загрузить выписку</h2>

        <div className="space-y-4">
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
