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

export type CashGapSignal = {
  date: string
  is_stress: boolean
  days_until: number
  severity: 'critical' | 'warning' | 'info'
}

export type ReconciliationIssue = {
  kind: 'erp_only' | 'bank_only' | 'amount_mismatch'
  counterparty: string
  amount: number
  detail: string
}

export type DashboardData = {
  has_data: boolean
  balance: number | null
  forecast: {
    deficit_day_7: string | null
    deficit_day_14: string | null
    deficit_day_30: string | null
    deficit_day_91: string | null
    deficit_signal: CashGapSignal | null
    has_obligations: boolean
    has_receivables: boolean
    has_aging_detail: boolean
    days_preview: Array<{ date: string; balance: number; receivable_collections?: number }>
    days_stress: Array<{ date: string; balance: number }>
  } | null
  obligations: Array<{
    due_date: string
    amount: number
    description: string
    days_until: number
  }>
  explain: {
    headline: string
    reasons: ExplainReason[]
  } | null
  receivables: {
    total_open: number
    buckets: Array<{ bucket: string; amount: number; count: number }>
    top_counterparties: Array<{
      name: string
      amount: number
      bucket: string
      due_date: string | null
    }>
  } | null
  reconciliation: {
    has_issues: boolean
    issues: ReconciliationIssue[]
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

export type UserMe = {
  email: string
  role: 'owner' | 'accountant' | 'viewer'
  company_id: string
  telegram_connected: boolean
}

export type OnboardingStep = {
  id: 'bank' | 'onec' | 'telegram'
  done: boolean
  required: boolean
  skipped: boolean
}

export type OnboardingStatus = {
  steps: OnboardingStep[]
  current_step: 'bank' | 'onec' | 'telegram' | null
  show_wizard: boolean
  show_banner: boolean
  dismissed: boolean
}

export type TransactionItem = {
  date: string
  amount: number
  direction: 'credit' | 'debit'
  counterparty: string | null
  purpose: string | null
}

export type TeamMember = {
  id: string
  email: string
  role: 'owner' | 'accountant' | 'viewer'
  is_active: boolean
  created_at: string | null
  telegram_connected: boolean
}

export const api = {
  getDashboard: () => apiFetch<DashboardData>('/dashboard/today'),

  getMe: () => apiFetch<UserMe>('/auth/me'),

  getOnboardingStatus: () => apiFetch<OnboardingStatus>('/onboarding/status'),

  dismissOnboarding: () =>
    apiFetch<OnboardingStatus>('/onboarding/dismiss', { method: 'POST' }),

  skipOnboardingStep: (step: 'onec' | 'telegram') =>
    apiFetch<OnboardingStatus>('/onboarding/skip', {
      method: 'POST',
      body: JSON.stringify({ step }),
    }),

  listTransactions: (limit = 50, offset = 0) =>
    apiFetch<{ transactions: TransactionItem[] }>(
      `/dashboard/transactions?limit=${limit}&offset=${offset}`
    ),

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

  uploadOneC: (file: File) => {
    const fd = new FormData()
    fd.append('file', file)
    const token = getToken()
    return fetch(`${API_BASE}/imports/onec`, {
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

  listUsers: () => apiFetch<{ users: TeamMember[] }>('/users'),

  inviteUser: (email: string, role: 'accountant' | 'viewer') =>
    apiFetch<{ id: string; email: string; role: string; is_active: boolean }>('/users', {
      method: 'POST',
      body: JSON.stringify({ email, role }),
    }),

  updateUser: (id: string, patch: { role?: string; is_active?: boolean }) =>
    apiFetch<{ id: string; email: string; role: string; is_active: boolean }>(`/users/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(patch),
    }),

  downloadWeeklyReport: async (): Promise<Blob> => {
    const token = getToken()
    const res = await fetch(`${API_BASE}/reports/weekly`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
    if (!res.ok) {
      const error = await res.json().catch(() => ({ detail: res.statusText }))
      throw new Error(error.detail ?? 'Ошибка загрузки отчёта')
    }
    return res.blob()
  },
}
