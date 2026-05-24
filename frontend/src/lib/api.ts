const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

function getToken(): string | null {
  if (typeof window === 'undefined') return null
  return localStorage.getItem('access_token')
}

export function saveToken(token: string): void {
  if (typeof window !== 'undefined') {
    localStorage.setItem('access_token', token)
  }
}

export function clearToken(): void {
  if (typeof window !== 'undefined') {
    localStorage.removeItem('access_token')
  }
}

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const token = getToken()
  const headers: HeadersInit = {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...options?.headers,
  }
  const res = await fetch(`${API_BASE}${path}`, { ...options, headers })
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(error.detail ?? 'API error')
  }
  return res.json() as Promise<T>
}

export type ExplainReason = {
  type: 'debit' | 'credit' | 'obligations'
  label: string
  amount: number
  date: string | null
}

export type DashboardData = {
  has_data: boolean
  balance: number | null
  forecast: {
    deficit_day_7: string | null
    deficit_day_14: string | null
    deficit_day_30: string | null
    deficit_day_91: string | null
    deficit_day_14_stress: string | null
    deficit_signal: { date: string; is_stress: boolean } | null
    has_obligations: boolean
    days_preview: Array<{ date: string; balance: number }>
    days_stress: Array<{ date: string; balance: number }>
  } | null
  obligations: Array<{
    due_date: string
    amount: number
    description: string
    days_until: number
  }>
  alerts: Array<{ type: string; payload: Record<string, unknown> }>
  explain: {
    headline: string
    reasons: ExplainReason[]
  } | null
  stale: { is_stale: boolean; hours: number | null }
  last_import_at: string | null
}

export type ObligationItem = {
  id: string
  due_date: string
  amount: number
  description: string
  status: string
  is_recurring: boolean
}

export const api = {
  getDashboard: () => apiFetch<DashboardData>('/dashboard/today'),

  register: (email: string, companyName: string) =>
    apiFetch<{ access_token: string; company_id: string; user_id: string }>('/auth/register', {
      method: 'POST',
      body: JSON.stringify({ email, company_name: companyName }),
    }),

  login: (email: string) =>
    apiFetch<{ access_token: string; company_id: string; user_id: string }>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email }),
    }),

  uploadCsv: (file: File, bankKey: string) => {
    const fd = new FormData()
    fd.append('file', file)
    fd.append('bank_key', bankKey)
    const token = getToken()
    return fetch(`${API_BASE}/imports/bank`, {
      method: 'POST',
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: fd,
    }).then((r) => r.json())
  },

  listObligations: () =>
    apiFetch<{ obligations: ObligationItem[] }>('/obligations'),

  createObligation: (data: {
    due_date: string
    amount: number
    description: string
    is_recurring?: boolean
  }) =>
    apiFetch<{ id: string; status: string }>('/obligations', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  payObligation: (id: string) =>
    apiFetch<{ status: string }>(`/obligations/${id}/pay`, { method: 'PATCH' }),

  updateTelegram: (telegramChatId: string) =>
    apiFetch<{ status: string; telegram_chat_id: string }>('/auth/me/telegram', {
      method: 'PATCH',
      body: JSON.stringify({ telegram_chat_id: telegramChatId }),
    }),

  getTelegramConnectCode: () =>
    apiFetch<{ code: string; ttl_seconds: number }>('/auth/me/telegram/connect-code', {
      method: 'POST',
    }),

  askAI: (question: string) =>
    apiFetch<{ answer: string; provider: string; cached: boolean }>('/ai/chat', {
      method: 'POST',
      body: JSON.stringify({ question }),
    }),
}
