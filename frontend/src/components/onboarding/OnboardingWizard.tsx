'use client'

import { useState, useRef, useEffect, useCallback } from 'react'
import { api, OnboardingStatus } from '@/lib/api'

type Props = {
  status: OnboardingStatus
  isOwner: boolean
  onStatusChange: (status: OnboardingStatus) => void
  onComplete: () => void
}

const BANKS = [
  { key: 'sber', label: 'Сбербанк' },
  { key: 'tinkoff', label: 'Тинькофф / Т-Банк' },
  { key: 'cbe', label: '1С ClientBankExchange' },
]

const STEPS = [
  { id: 'bank', label: 'Банк' },
  { id: 'onec', label: '1С' },
  { id: 'telegram', label: 'Telegram' },
] as const

function StepIndicator({ current }: { current: string }) {
  const order = ['bank', 'onec', 'telegram']
  const idx = order.indexOf(current)
  return (
    <div className="flex items-center justify-center gap-2 mb-6">
      {STEPS.map((s, i) => (
        <div key={s.id} className="flex items-center gap-2">
          <div
            className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-medium ${
              i < idx
                ? 'bg-trust text-white'
                : i === idx
                ? 'bg-neutral-900 text-white'
                : 'bg-neutral-100 text-neutral-400'
            }`}
          >
            {i + 1}
          </div>
          <span className={`text-xs hidden sm:inline ${i === idx ? 'text-neutral-900 font-medium' : 'text-neutral-400'}`}>
            {s.label}
          </span>
          {i < STEPS.length - 1 && (
            <div className={`w-8 h-px ${i < idx ? 'bg-trust' : 'bg-neutral-200'}`} />
          )}
        </div>
      ))}
    </div>
  )
}

export function OnboardingWizard({ status, isOwner, onStatusChange, onComplete }: Props) {
  const step = status.current_step ?? 'bank'
  const [bankKey, setBankKey] = useState('sber')
  const [file, setFile] = useState<File | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [hint, setHint] = useState<string | null>(null)
  const [tgCode, setTgCode] = useState<string | null>(null)
  const [tgExpires, setTgExpires] = useState<number | null>(null)
  const [tgSeconds, setTgSeconds] = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)

  const refresh = useCallback(async () => {
    const next = await api.getOnboardingStatus()
    onStatusChange(next)
    return next
  }, [onStatusChange])

  useEffect(() => {
    if (!tgExpires) return
    const tick = () => {
      const left = Math.max(0, Math.round((tgExpires - Date.now()) / 1000))
      setTgSeconds(left)
      if (left === 0) setTgCode(null)
    }
    tick()
    const id = setInterval(tick, 1000)
    return () => clearInterval(id)
  }, [tgExpires])

  async function handleBankUpload() {
    if (!file) return
    setIsLoading(true)
    setError(null)
    try {
      const result = await api.uploadCsv(file, bankKey)
      if (result.status === 'failed') {
        setError(result.error_log?.[0]?.error ?? 'Ошибка при загрузке')
        return
      }
      setFile(null)
      await refresh()
      onComplete()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Ошибка при загрузке')
    } finally {
      setIsLoading(false)
    }
  }

  async function handleOneCUpload() {
    if (!file) return
    setIsLoading(true)
    setError(null)
    setHint(null)
    try {
      const result = await api.uploadOneC(file)
      if (result.status === 'failed') {
        setError(result.error_log?.[0]?.error ?? 'Ошибка при загрузке')
        return
      }
      const meta = result.meta as { forecast_ready?: boolean } | null
      if (meta && !meta.forecast_ready) {
        setHint('Для прогноза загрузите ОСВ с aging-колонками или детализацию счёта 62.')
      }
      setFile(null)
      await refresh()
      onComplete()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Ошибка при загрузке')
    } finally {
      setIsLoading(false)
    }
  }

  async function handleSkip(skipStep: 'onec' | 'telegram') {
    setIsLoading(true)
    setError(null)
    try {
      const next = await api.skipOnboardingStep(skipStep)
      onStatusChange(next)
      onComplete()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Ошибка')
    } finally {
      setIsLoading(false)
    }
  }

  async function handleDismiss() {
    setIsLoading(true)
    setError(null)
    try {
      await api.dismissOnboarding()
      await refresh()
      onComplete()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Ошибка')
    } finally {
      setIsLoading(false)
    }
  }

  async function handleGetTelegramCode() {
    setIsLoading(true)
    setError(null)
    try {
      const result = await api.getTelegramConnectCode()
      setTgCode(result.code)
      setTgExpires(Date.now() + result.ttl_seconds * 1000)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Ошибка получения кода')
    } finally {
      setIsLoading(false)
    }
  }

  async function handleTelegramDone() {
    const me = await api.getMe()
    if (me.telegram_connected) {
      await refresh()
      onComplete()
    } else {
      setHint('Telegram ещё не привязан. Отправьте боту команду /connect с кодом.')
    }
  }

  const mm = Math.floor(tgSeconds / 60)
  const ss = String(tgSeconds % 60).padStart(2, '0')

  return (
    <div className="min-h-screen bg-neutral-50 flex flex-col">
      <header className="bg-white border-b border-neutral-200 px-4 py-3">
        <h1 className="text-base font-semibold text-neutral-900">Настройка автопилота</h1>
        <p className="text-xs text-neutral-500 mt-0.5">3 шага до первой финансовой сводки</p>
      </header>

      <div className="flex-1 flex items-start justify-center p-4 pt-8">
        <div className="bg-white rounded-2xl shadow-sm border border-neutral-100 p-6 w-full max-w-md">
          <StepIndicator current={step} />

          {step === 'bank' && (
            <div className="space-y-4">
              <div>
                <h2 className="text-lg font-semibold text-neutral-900">Банковская выписка</h2>
                <p className="text-sm text-neutral-500 mt-1">
                  Экспортируйте CSV из банк-клиента — это основа остатка и прогноза.
                </p>
              </div>
              <div>
                <label className="block text-xs font-medium text-neutral-500 mb-1">Банк</label>
                <select
                  value={bankKey}
                  onChange={(e) => setBankKey(e.target.value)}
                  className="w-full border border-neutral-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-trust/30"
                >
                  {BANKS.map((b) => (
                    <option key={b.key} value={b.key}>{b.label}</option>
                  ))}
                </select>
              </div>
              <FilePicker file={file} inputRef={inputRef} onChange={setFile} />
            </div>
          )}

          {step === 'onec' && (
            <div className="space-y-4">
              <div>
                <h2 className="text-lg font-semibold text-neutral-900">Дебиторка из 1С</h2>
                <p className="text-sm text-neutral-500 mt-1">
                  ОСВ или детализация счёта 62 — для прогноза поступлений и сверки с банком.
                </p>
              </div>
              <p className="text-xs text-neutral-500 bg-neutral-50 rounded-lg px-3 py-2">
                CSV с разделителем «;». Aging-колонки (0–30, 31–60, 61–90, 90+) или файл с датой документа.
              </p>
              <FilePicker file={file} inputRef={inputRef} onChange={setFile} />
            </div>
          )}

          {step === 'telegram' && isOwner && (
            <div className="space-y-4">
              <div>
                <h2 className="text-lg font-semibold text-neutral-900">Telegram-дайджест</h2>
                <p className="text-sm text-neutral-500 mt-1">
                  Утреннее сообщение с остатком и рисками — каждый день в 08:00.
                </p>
              </div>
              <div className="bg-neutral-50 rounded-lg p-3 text-xs text-neutral-600 space-y-1">
                <ol className="list-decimal list-inside space-y-0.5">
                  <li>Нажмите «Получить код»</li>
                  <li>Откройте бота в Telegram</li>
                  <li>Отправьте <span className="font-mono">/connect {'<код>'}</span></li>
                </ol>
              </div>
              {tgCode && tgSeconds > 0 ? (
                <div className="text-center space-y-2">
                  <p className="text-xs text-neutral-500">Код (действует {mm}:{ss}):</p>
                  <div className="text-3xl font-mono font-bold tracking-widest text-neutral-900 bg-neutral-50 rounded-lg py-3">
                    {tgCode}
                  </div>
                </div>
              ) : (
                <button
                  onClick={handleGetTelegramCode}
                  disabled={isLoading}
                  className="w-full py-2 text-sm font-medium bg-neutral-900 text-white rounded-lg hover:bg-neutral-800 disabled:opacity-50"
                >
                  {isLoading ? '…' : 'Получить код'}
                </button>
              )}
              <button
                onClick={handleTelegramDone}
                disabled={isLoading}
                className="w-full py-2 text-sm font-medium border border-neutral-200 text-neutral-700 rounded-lg hover:bg-neutral-50"
              >
                Я подключил Telegram
              </button>
            </div>
          )}

          {error && <p className="text-xs text-red-500 mt-3">{error}</p>}
          {hint && <p className="text-xs text-amber-700 bg-amber-50 rounded-lg px-3 py-2 mt-3">{hint}</p>}

          <div className="flex gap-2 mt-6 pt-4 border-t border-neutral-100">
            {step === 'bank' && (
              <button
                onClick={handleBankUpload}
                disabled={!file || isLoading}
                className="flex-1 bg-trust text-white font-medium py-2.5 rounded-lg text-sm hover:bg-trust-dark disabled:opacity-50"
              >
                {isLoading ? 'Загружаем…' : 'Загрузить и продолжить'}
              </button>
            )}
            {step === 'onec' && (
              <>
                <button
                  onClick={() => handleSkip('onec')}
                  disabled={isLoading}
                  className="flex-1 border border-neutral-200 text-neutral-600 font-medium py-2.5 rounded-lg text-sm hover:bg-neutral-50"
                >
                  Пропустить
                </button>
                <button
                  onClick={handleOneCUpload}
                  disabled={!file || isLoading}
                  className="flex-1 bg-trust text-white font-medium py-2.5 rounded-lg text-sm hover:bg-trust-dark disabled:opacity-50"
                >
                  {isLoading ? 'Загружаем…' : 'Загрузить'}
                </button>
              </>
            )}
            {step === 'telegram' && isOwner && (
              <>
                <button
                  onClick={() => handleSkip('telegram')}
                  disabled={isLoading}
                  className="flex-1 border border-neutral-200 text-neutral-600 font-medium py-2.5 rounded-lg text-sm hover:bg-neutral-50"
                >
                  Пропустить
                </button>
                <button
                  onClick={handleDismiss}
                  disabled={isLoading}
                  className="flex-1 bg-trust text-white font-medium py-2.5 rounded-lg text-sm hover:bg-trust-dark disabled:opacity-50"
                >
                  Перейти к дашборду
                </button>
              </>
            )}
          </div>

          {(step === 'onec') && (
            <button
              onClick={handleDismiss}
              disabled={isLoading}
              className="w-full mt-2 text-xs text-neutral-400 hover:text-neutral-600 py-1"
            >
              Перейти к дашборду без 1С
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

function FilePicker({
  file,
  inputRef,
  onChange,
}: {
  file: File | null
  inputRef: React.RefObject<HTMLInputElement | null>
  onChange: (f: File | null) => void
}) {
  return (
    <div>
      <label className="block text-xs font-medium text-neutral-500 mb-1">CSV файл</label>
      <div
        onClick={() => inputRef.current?.click()}
        className="border-2 border-dashed border-neutral-200 rounded-lg p-6 text-center cursor-pointer hover:border-trust/40 transition-colors"
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
        onChange={(e) => onChange(e.target.files?.[0] ?? null)}
      />
    </div>
  )
}
