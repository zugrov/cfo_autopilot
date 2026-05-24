'use client'

import { useEffect, useState, useCallback } from 'react'
import { api, DashboardData } from '@/lib/api'
import { DashboardView } from '@/components/dashboard/DashboardView'
import { UploadModal } from '@/components/dashboard/UploadModal'
import { ObligationsPanel } from '@/components/dashboard/ObligationsPanel'

type AuthMode = 'login' | 'register'

function AuthForm({ onSuccess }: { onSuccess: () => void }) {
  const [mode, setMode] = useState<AuthMode>('login')
  const [email, setEmail] = useState('')
  const [companyName, setCompanyName] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsLoading(true)
    setError(null)
    try {
      let result
      if (mode === 'register') {
        result = await api.register(email, companyName)
      } else {
        result = await api.login(email)
      }
      localStorage.setItem('access_token', result.access_token)
      onSuccess()
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Ошибка авторизации')
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-neutral-50 px-4">
      <div className="w-full max-w-sm">
        <h1 className="text-xl font-semibold text-neutral-900 mb-1">Финансовый автопилот</h1>
        <p className="text-sm text-neutral-500 mb-6">Управление деньгами для МСБ</p>

        <div className="flex gap-2 mb-6">
          <button
            onClick={() => setMode('login')}
            className={`flex-1 text-sm py-1.5 rounded font-medium transition-colors ${
              mode === 'login'
                ? 'bg-neutral-900 text-white'
                : 'bg-white text-neutral-600 border border-neutral-200 hover:bg-neutral-50'
            }`}
          >
            Войти
          </button>
          <button
            onClick={() => setMode('register')}
            className={`flex-1 text-sm py-1.5 rounded font-medium transition-colors ${
              mode === 'register'
                ? 'bg-neutral-900 text-white'
                : 'bg-white text-neutral-600 border border-neutral-200 hover:bg-neutral-50'
            }`}
          >
            Регистрация
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-3">
          {mode === 'register' && (
            <div>
              <label className="block text-xs font-medium text-neutral-700 mb-1">
                Название компании
              </label>
              <input
                type="text"
                value={companyName}
                onChange={(e) => setCompanyName(e.target.value)}
                required
                placeholder="ООО Ромашка"
                className="w-full px-3 py-2 text-sm border border-neutral-200 rounded outline-none focus:border-neutral-400 focus:ring-1 focus:ring-neutral-400"
              />
            </div>
          )}
          <div>
            <label className="block text-xs font-medium text-neutral-700 mb-1">Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              placeholder="ivan@company.ru"
              className="w-full px-3 py-2 text-sm border border-neutral-200 rounded outline-none focus:border-neutral-400 focus:ring-1 focus:ring-neutral-400"
            />
          </div>

          {error && <p className="text-xs text-red-500">{error}</p>}

          <button
            type="submit"
            disabled={isLoading}
            className="w-full py-2 text-sm font-medium bg-neutral-900 text-white rounded hover:bg-neutral-800 disabled:opacity-50 transition-colors"
          >
            {isLoading ? 'Загрузка…' : mode === 'register' ? 'Создать аккаунт' : 'Войти'}
          </button>
        </form>
      </div>
    </div>
  )
}

function TelegramModal({ onClose }: { onClose: () => void }) {
  const [chatId, setChatId] = useState('')
  const [isSaving, setIsSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsSaving(true)
    setError(null)
    try {
      await api.updateTelegram(chatId.trim())
      setSaved(true)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Ошибка сохранения')
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center">
      <div className="absolute inset-0 bg-black/30" onClick={onClose} />
      <div className="relative bg-white w-full sm:max-w-sm sm:rounded-xl shadow-xl p-5">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-semibold text-neutral-900">Настройки Telegram</h2>
          <button
            onClick={onClose}
            className="text-neutral-400 hover:text-neutral-600 transition-colors text-lg leading-none"
          >
            ×
          </button>
        </div>

        {saved ? (
          <div className="text-center py-4">
            <p className="text-sm font-medium text-green-700 mb-1">Сохранено!</p>
            <p className="text-xs text-neutral-500">
              Дайджест будет приходить каждое утро в 08:00
            </p>
            <button
              onClick={onClose}
              className="mt-4 px-4 py-1.5 text-xs bg-neutral-900 text-white rounded hover:bg-neutral-800 transition-colors"
            >
              Закрыть
            </button>
          </div>
        ) : (
          <form onSubmit={handleSave} className="space-y-3">
            <div className="bg-neutral-50 rounded-lg p-3 text-xs text-neutral-600 space-y-1">
              <p className="font-medium">Как найти свой Telegram Chat ID:</p>
              <ol className="list-decimal list-inside space-y-0.5">
                <li>Откройте Telegram</li>
                <li>Напишите боту <span className="font-mono">@userinfobot</span></li>
                <li>Скопируйте ваш <span className="font-mono">Id</span></li>
              </ol>
            </div>
            <div>
              <label className="block text-xs font-medium text-neutral-700 mb-1">
                Telegram Chat ID
              </label>
              <input
                type="text"
                value={chatId}
                onChange={(e) => setChatId(e.target.value)}
                required
                placeholder="123456789"
                className="w-full px-3 py-2 text-sm border border-neutral-200 rounded outline-none focus:border-neutral-400"
              />
            </div>
            {error && <p className="text-xs text-red-500">{error}</p>}
            <button
              type="submit"
              disabled={isSaving || !chatId.trim()}
              className="w-full py-2 text-sm font-medium bg-neutral-900 text-white rounded hover:bg-neutral-800 disabled:opacity-50 transition-colors"
            >
              {isSaving ? 'Сохранение…' : 'Сохранить'}
            </button>
          </form>
        )}
      </div>
    </div>
  )
}

export default function HomePage() {
  const [token, setToken] = useState<string | null>(null)
  const [data, setData] = useState<DashboardData | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [showUpload, setShowUpload] = useState(false)
  const [showObligations, setShowObligations] = useState(false)
  const [showTelegram, setShowTelegram] = useState(false)

  useEffect(() => {
    const stored = localStorage.getItem('access_token')
    setToken(stored)
  }, [])

  const fetchDashboard = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      const result = await api.getDashboard()
      setData(result)
    } catch (e: unknown) {
      if (e instanceof Error && e.message.includes('401')) {
        localStorage.removeItem('access_token')
        setToken(null)
        return
      }
      setError(e instanceof Error ? e.message : 'Ошибка загрузки')
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    if (token) {
      fetchDashboard()
    }
  }, [token, fetchDashboard])

  const handleLogout = () => {
    localStorage.removeItem('access_token')
    setToken(null)
    setData(null)
  }

  if (!token) {
    return <AuthForm onSuccess={() => setToken(localStorage.getItem('access_token'))} />
  }

  return (
    <>
      <header className="bg-white border-b border-neutral-200 px-4 py-3 flex items-center justify-between sticky top-0 z-10">
        <h1 className="text-base font-semibold text-neutral-900">Финансовый автопилот</h1>
        <div className="flex items-center gap-3">
          <button
            onClick={() => setShowObligations(true)}
            className="text-xs font-medium text-neutral-600 hover:text-neutral-900 transition-colors"
          >
            Обязательства
          </button>
          <button
            onClick={() => setShowUpload(true)}
            className="text-xs font-medium text-trust hover:text-trust-dark transition-colors"
          >
            + Выписка
          </button>
          <button
            onClick={() => setShowTelegram(true)}
            className="text-xs text-neutral-400 hover:text-neutral-600 transition-colors"
            title="Настроить Telegram-дайджест"
          >
            Telegram
          </button>
          <button
            onClick={handleLogout}
            className="text-xs text-neutral-400 hover:text-neutral-600 transition-colors"
          >
            Выйти
          </button>
        </div>
      </header>

      <main className="pb-8">
        <DashboardView
          data={data}
          isLoading={isLoading}
          error={error}
          onUploadClick={() => setShowUpload(true)}
        />
      </main>

      {showUpload && (
        <UploadModal
          onSuccess={fetchDashboard}
          onClose={() => setShowUpload(false)}
        />
      )}

      {showObligations && (
        <ObligationsPanel
          onClose={() => setShowObligations(false)}
          onRefreshDashboard={fetchDashboard}
        />
      )}

      {showTelegram && (
        <TelegramModal onClose={() => setShowTelegram(false)} />
      )}
    </>
  )
}
