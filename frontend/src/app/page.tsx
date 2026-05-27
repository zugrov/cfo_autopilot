'use client'

import { useEffect, useState, useCallback } from 'react'
import { api, DashboardData, UserMe, OnboardingStatus } from '@/lib/api'
import { DashboardView } from '@/components/dashboard/DashboardView'
import { UploadModal } from '@/components/dashboard/UploadModal'
import { ObligationsPanel } from '@/components/dashboard/ObligationsPanel'
import { AiChatPanel } from '@/components/dashboard/AiChatPanel'
import { TransactionsPanel } from '@/components/dashboard/TransactionsPanel'
import { OnboardingWizard } from '@/components/onboarding/OnboardingWizard'
import { OnboardingBanner } from '@/components/onboarding/OnboardingBanner'
import { TeamPanel } from '@/components/team/TeamPanel'
import { AuditPanel } from '@/components/audit/AuditPanel'

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
  const [code, setCode] = useState<string | null>(null)
  const [expiresAt, setExpiresAt] = useState<number | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [secondsLeft, setSecondsLeft] = useState(0)

  useEffect(() => {
    if (!expiresAt) return
    const tick = () => {
      const left = Math.max(0, Math.round((expiresAt - Date.now()) / 1000))
      setSecondsLeft(left)
      if (left === 0) setCode(null)
    }
    tick()
    const id = setInterval(tick, 1000)
    return () => clearInterval(id)
  }, [expiresAt])

  const handleGetCode = async () => {
    setIsLoading(true)
    setError(null)
    try {
      const result = await api.getTelegramConnectCode()
      setCode(result.code)
      setExpiresAt(Date.now() + result.ttl_seconds * 1000)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Ошибка получения кода')
    } finally {
      setIsLoading(false)
    }
  }

  const mm = Math.floor(secondsLeft / 60)
  const ss = String(secondsLeft % 60).padStart(2, '0')

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

        <div className="space-y-4">
          <div className="bg-neutral-50 rounded-lg p-3 text-xs text-neutral-600 space-y-1">
            <p className="font-medium">Как привязать Telegram:</p>
            <ol className="list-decimal list-inside space-y-0.5">
              <li>Нажмите «Получить код» ниже</li>
              <li>Откройте бота в Telegram</li>
              <li>Отправьте <span className="font-mono">/connect {'<код>'}</span></li>
            </ol>
          </div>

          {error && (
            <p className="text-xs text-red-500 bg-red-50 rounded px-3 py-2">{error}</p>
          )}

          {code && secondsLeft > 0 ? (
            <div className="text-center space-y-2">
              <p className="text-xs text-neutral-500">Ваш код (действует {mm}:{ss}):</p>
              <div className="text-3xl font-mono font-bold tracking-widest text-neutral-900 bg-neutral-50 rounded-lg py-3">
                {code}
              </div>
              <p className="text-xs text-neutral-400">
                Отправьте боту: <span className="font-mono text-neutral-600">/connect {code}</span>
              </p>
            </div>
          ) : (
            <button
              onClick={handleGetCode}
              disabled={isLoading}
              className="w-full py-2 text-sm font-medium bg-neutral-900 text-white rounded hover:bg-neutral-800 disabled:opacity-50 transition-colors"
            >
              {isLoading ? 'Получение кода…' : code ? 'Получить новый код' : 'Получить код'}
            </button>
          )}

          <p className="text-xs text-neutral-400 text-center">
            После привязки дайджест будет приходить каждое утро в 08:00
          </p>
        </div>
      </div>
    </div>
  )
}

type ActivePanel = 'upload' | 'obligations' | 'transactions' | 'telegram' | 'ai' | 'team' | 'audit' | null

export default function HomePage() {
  const [token, setToken] = useState<string | null>(null)
  const [user, setUser] = useState<UserMe | null>(null)
  const [data, setData] = useState<DashboardData | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [activePanel, setActivePanel] = useState<ActivePanel>(null)
  const [onboarding, setOnboarding] = useState<OnboardingStatus | null>(null)
  const [isDownloadingReport, setIsDownloadingReport] = useState(false)

  const openPanel = (panel: Exclude<ActivePanel, null>) => setActivePanel(panel)
  const closePanel = () => setActivePanel(null)

  const canImport = user?.role !== 'viewer'
  const canEditObligations = user?.role !== 'viewer'
  const isOwner = user?.role === 'owner'

  useEffect(() => {
    const stored = localStorage.getItem('access_token')
    setToken(stored)
  }, [])

  const fetchUser = useCallback(async () => {
    try {
      const me = await api.getMe()
      setUser(me)
    } catch {
      setUser(null)
    }
  }, [])

  const fetchOnboarding = useCallback(async () => {
    try {
      const status = await api.getOnboardingStatus()
      setOnboarding(status)
    } catch {
      setOnboarding(null)
    }
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
      fetchUser()
      fetchDashboard()
      fetchOnboarding()
    }
  }, [token, fetchUser, fetchDashboard, fetchOnboarding])

  const handleOnboardingComplete = useCallback(async () => {
    await Promise.all([fetchOnboarding(), fetchDashboard(), fetchUser()])
  }, [fetchOnboarding, fetchDashboard, fetchUser])

  const handleLogout = () => {
    localStorage.removeItem('access_token')
    setToken(null)
    setUser(null)
    setData(null)
    setOnboarding(null)
  }

  const handleDownloadReport = async () => {
    setIsDownloadingReport(true)
    try {
      const blob = await api.downloadWeeklyReport()
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `report-${new Date().toISOString().slice(0, 10)}.pdf`
      link.click()
      URL.revokeObjectURL(url)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Не удалось скачать отчёт')
    } finally {
      setIsDownloadingReport(false)
    }
  }

  if (!token) {
    return <AuthForm onSuccess={() => setToken(localStorage.getItem('access_token'))} />
  }

  if (onboarding?.show_wizard && canImport) {
    return (
      <OnboardingWizard
        status={onboarding}
        isOwner={isOwner}
        onStatusChange={setOnboarding}
        onComplete={handleOnboardingComplete}
      />
    )
  }

  return (
    <>
      <header className="bg-white border-b border-neutral-200 px-4 py-3 flex items-center justify-between sticky top-0 z-10">
        <h1 className="text-base font-semibold text-neutral-900">Финансовый автопилот</h1>
        <div className="flex items-center gap-3">
          <button
            onClick={() => openPanel('transactions')}
            className="text-xs font-medium text-neutral-600 hover:text-neutral-900 transition-colors"
          >
            Операции
          </button>
          <button
            onClick={() => openPanel('obligations')}
            className="text-xs font-medium text-neutral-600 hover:text-neutral-900 transition-colors"
          >
            Обязательства
          </button>
          <button
            onClick={() => openPanel('ai')}
            className="text-xs font-medium text-trust hover:text-trust-dark transition-colors"
          >
            Спросить
          </button>
          {canImport && (
          <button
            onClick={() => openPanel('upload')}
            className="text-xs font-medium text-trust hover:text-trust-dark transition-colors"
          >
            + Выписка
          </button>
          )}
          {isOwner && (
          <button
            onClick={handleDownloadReport}
            disabled={isDownloadingReport}
            className="text-xs font-medium text-neutral-600 hover:text-neutral-900 transition-colors disabled:opacity-50"
          >
            {isDownloadingReport ? 'Загрузка…' : 'Скачать отчёт'}
          </button>
          )}
          {isOwner && (
          <button
            onClick={() => openPanel('audit')}
            className="text-xs font-medium text-neutral-600 hover:text-neutral-900 transition-colors"
          >
            Журнал
          </button>
          )}
          {isOwner && (
          <button
            onClick={() => openPanel('team')}
            className="text-xs font-medium text-neutral-600 hover:text-neutral-900 transition-colors"
          >
            Команда
          </button>
          )}
          {isOwner && (
          <button
            onClick={() => openPanel('telegram')}
            className="text-xs text-neutral-400 hover:text-neutral-600 transition-colors"
            title="Настроить Telegram-дайджест"
          >
            Telegram
          </button>
          )}
          <button
            onClick={handleLogout}
            className="text-xs text-neutral-400 hover:text-neutral-600 transition-colors"
          >
            Выйти
          </button>
        </div>
      </header>

      <main className="pb-8">
        {onboarding && (
          <OnboardingBanner
            status={onboarding}
            isOwner={isOwner}
            onUploadOneC={() => openPanel('upload')}
            onConnectTelegram={() => openPanel('telegram')}
          />
        )}
        <DashboardView
          data={data}
          isLoading={isLoading}
          error={error}
          onUploadClick={() => canImport && openPanel('upload')}
          onTransactionsClick={() => openPanel('transactions')}
          canImport={canImport}
        />
      </main>

      {activePanel === 'upload' && (
        <UploadModal
          onSuccess={() => {
            fetchDashboard()
            fetchOnboarding()
          }}
          onClose={closePanel}
        />
      )}

      {activePanel === 'obligations' && (
        <ObligationsPanel
          onClose={closePanel}
          onRefreshDashboard={fetchDashboard}
          canEdit={canEditObligations}
        />
      )}

      {activePanel === 'transactions' && (
        <TransactionsPanel onClose={closePanel} />
      )}

      {activePanel === 'telegram' && (
        <TelegramModal onClose={closePanel} />
      )}

      {activePanel === 'ai' && (
        <AiChatPanel onClose={closePanel} />
      )}

      {activePanel === 'team' && (
        <TeamPanel onClose={closePanel} />
      )}

      {activePanel === 'audit' && (
        <AuditPanel onClose={closePanel} />
      )}
    </>
  )
}
