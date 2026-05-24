'use client'

import { useState, useEffect, useCallback } from 'react'
import { api, TeamMember } from '@/lib/api'

type Props = {
  onClose: () => void
}

const ROLE_LABELS: Record<string, string> = {
  owner: 'Собственник',
  accountant: 'Финансист',
  viewer: 'Наблюдатель',
}

export function TeamPanel({ onClose }: Props) {
  const [members, setMembers] = useState<TeamMember[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [email, setEmail] = useState('')
  const [role, setRole] = useState<'accountant' | 'viewer'>('viewer')
  const [isSaving, setIsSaving] = useState(false)
  const [updatingId, setUpdatingId] = useState<string | null>(null)

  const load = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      const data = await api.listUsers()
      setMembers(data.users)
    } catch {
      setError('Не удалось загрузить команду')
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const handleInvite = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsSaving(true)
    setError(null)
    try {
      await api.inviteUser(email, role)
      setEmail('')
      await load()
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Ошибка приглашения')
    } finally {
      setIsSaving(false)
    }
  }

  const handleDeactivate = async (member: TeamMember) => {
    if (member.role === 'owner') return
    setUpdatingId(member.id)
    setError(null)
    try {
      await api.updateUser(member.id, { is_active: false })
      await load()
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Ошибка обновления')
    } finally {
      setUpdatingId(null)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center">
      <div className="absolute inset-0 bg-black/30" onClick={onClose} />
      <div className="relative bg-white w-full sm:max-w-lg sm:rounded-xl shadow-xl max-h-[90vh] flex flex-col">
        <div className="flex items-center justify-between px-4 py-3 border-b border-neutral-100">
          <h2 className="text-sm font-semibold text-neutral-900">Команда</h2>
          <button
            onClick={onClose}
            className="text-neutral-400 hover:text-neutral-600 transition-colors text-lg leading-none"
          >
            ×
          </button>
        </div>

        <div className="overflow-y-auto flex-1 px-4 py-3 space-y-4">
          {error && (
            <p className="text-xs text-red-500 bg-red-50 rounded px-3 py-2">{error}</p>
          )}

          <form onSubmit={handleInvite} className="border border-neutral-200 rounded-lg p-3 space-y-2">
            <p className="text-xs font-medium text-neutral-700">Пригласить пользователя</p>
            <p className="text-xs text-neutral-400">
              После приглашения пользователь входит через «Войти» с указанным email.
            </p>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="fin@company.ru"
              className="w-full px-2 py-1.5 text-sm border border-neutral-200 rounded outline-none focus:border-neutral-400"
            />
            <select
              value={role}
              onChange={(e) => setRole(e.target.value as 'accountant' | 'viewer')}
              className="w-full px-2 py-1.5 text-sm border border-neutral-200 rounded outline-none focus:border-neutral-400"
            >
              <option value="viewer">Наблюдатель (только чтение)</option>
              <option value="accountant">Финансист (загрузка + обязательства)</option>
            </select>
            <button
              type="submit"
              disabled={isSaving}
              className="w-full py-1.5 text-xs font-medium bg-neutral-900 text-white rounded hover:bg-neutral-800 disabled:opacity-50"
            >
              {isSaving ? 'Приглашение…' : 'Пригласить'}
            </button>
          </form>

          {isLoading ? (
            <div className="space-y-2">
              {[1, 2].map((i) => (
                <div key={i} className="h-12 bg-neutral-100 rounded animate-pulse" />
              ))}
            </div>
          ) : (
            <div className="space-y-1">
              {members.map((m) => (
                <div
                  key={m.id}
                  className="flex items-center justify-between py-2 px-3 rounded-lg hover:bg-neutral-50 group"
                >
                  <div className="min-w-0 flex-1">
                    <p className={`text-sm truncate ${m.is_active ? 'text-neutral-900' : 'text-neutral-400 line-through'}`}>
                      {m.email}
                    </p>
                    <p className="text-xs text-neutral-500">
                      {ROLE_LABELS[m.role] ?? m.role}
                      {!m.is_active && ' · деактивирован'}
                    </p>
                  </div>
                  {m.role !== 'owner' && m.is_active && (
                    <button
                      onClick={() => handleDeactivate(m)}
                      disabled={updatingId === m.id}
                      className="text-xs px-2 py-0.5 text-red-600 border border-red-200 rounded opacity-0 group-hover:opacity-100 disabled:opacity-50 transition-all hover:bg-red-50"
                    >
                      {updatingId === m.id ? '…' : 'Деактивировать'}
                    </button>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
