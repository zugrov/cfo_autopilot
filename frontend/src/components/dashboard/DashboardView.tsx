'use client'

import { DashboardData, ExplainReason, CashGapSignal } from '@/lib/api'import { Badge, Card, Skeleton } from '@/components/ui'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts'

type Props = {
  data: DashboardData | null
  isLoading: boolean
  error: string | null
  onUploadClick: () => void
}

function formatRub(amount: number): string {
  return `₽\u00a0${amount.toLocaleString('ru-RU', { maximumFractionDigits: 0 })}`
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' })
}

function ReasonIcon({ type }: { type: string }) {
  if (type === 'debit') return <span className="text-red-500">↓</span>
  if (type === 'credit') return <span className="text-green-600">↑</span>
  return <span className="text-amber-500">📅</span>
}

const SEVERITY_CARD: Record<string, string> = {
  critical: 'border-alert/30 bg-alert-soft',
  warning: 'border-amber-300 bg-amber-50',
  info: 'border-neutral-200 bg-neutral-50',
}

const SEVERITY_TEXT: Record<string, string> = {
  critical: 'text-alert',
  warning: 'text-amber-700',
  info: 'text-neutral-600',
}

const SEVERITY_SUBTEXT: Record<string, string> = {
  critical: 'text-alert/70',
  warning: 'text-amber-600/70',
  info: 'text-neutral-400',
}

const SEVERITY_ICON: Record<string, string> = {
  critical: '⚠',
  warning: '⚠',
  info: 'ℹ',
}

function CashGapCard({ signal }: { signal: CashGapSignal }) {
  const { severity, days_until, date: gapDate, is_stress } = signal
  const cardClass = SEVERITY_CARD[severity] ?? SEVERITY_CARD.info
  const textClass = SEVERITY_TEXT[severity] ?? SEVERITY_TEXT.info
  const subClass = SEVERITY_SUBTEXT[severity] ?? SEVERITY_SUBTEXT.info
  const icon = SEVERITY_ICON[severity] ?? 'ℹ'

  const verb =
    severity === 'critical'
      ? 'Кассовый разрыв'
      : severity === 'warning'
      ? 'Кассовый разрыв возможен'
      : 'Риск кассового разрыва'

  return (
    <Card className={cardClass}>
      <div className="flex items-start gap-2">
        <span className={`${textClass} text-lg shrink-0`}>{icon}</span>
        <div>
          <p className={`font-semibold ${textClass} text-sm`}>
            {verb} через {days_until} дней
          </p>
          <p className={`text-xs ${subClass}`}>
            {formatDate(gapDate)}
            {is_stress && ' · если поступления −15%'}
          </p>
        </div>
      </div>
    </Card>
  )
}

const BUCKET_LABELS: Record<string, string> = {
  '0_30':   '0–30 дней',
  '31_60':  '31–60 дней',
  '61_90':  '61–90 дней',
  '90_plus': 'Просрочено',
  'unknown': 'Без срока',
}

function ReceivablesCard({ receivables }: { receivables: NonNullable<DashboardData['receivables']> }) {
  const sorted = [...receivables.buckets].sort((a, b) => {
    const order = ['0_30', '31_60', '61_90', '90_plus', 'unknown']
    return order.indexOf(a.bucket) - order.indexOf(b.bucket)
  })
  return (
    <Card>
      <div className="flex items-center justify-between mb-3">
        <p className="text-xs text-neutral-400 uppercase tracking-wide font-medium">
          Дебиторка (1С)
        </p>
        <p className="text-sm font-semibold text-neutral-900">
          {formatRub(receivables.total_open)}
        </p>
      </div>
      <div className="space-y-1.5">
        {sorted.map((b) => (
          <div key={b.bucket} className="flex items-center justify-between">
            <p className={`text-xs ${b.bucket === '90_plus' ? 'text-alert font-medium' : 'text-neutral-600'}`}>
              {BUCKET_LABELS[b.bucket] ?? b.bucket}
              <span className="text-neutral-400 ml-1">({b.count})</span>
            </p>
            <p className={`text-sm font-medium ${b.bucket === '90_plus' ? 'text-alert' : 'text-neutral-800'}`}>
              {formatRub(b.amount)}
            </p>
          </div>
        ))}
      </div>
    </Card>
  )
}

function ExplainBlock({ explain }: { explain: NonNullable<DashboardData['explain']> }) {
  if (!explain.reasons.length) return null
  return (
    <Card>
      <p className="text-xs text-neutral-400 uppercase tracking-wide font-medium mb-2">
        Объяснение
      </p>
      <p className="text-xs text-neutral-500 mb-3">{explain.headline}</p>
      <div className="space-y-2">
        {explain.reasons.map((r: ExplainReason, i: number) => (
          <div key={i} className="flex items-start justify-between gap-2">
            <div className="flex items-start gap-1.5 min-w-0 flex-1">
              <ReasonIcon type={r.type} />
              <p className="text-sm text-neutral-700 truncate">{r.label}</p>
            </div>
            <div className="text-right shrink-0">
              <p className="text-sm font-medium text-neutral-900">{formatRub(r.amount)}</p>
              {r.date && (
                <p className="text-xs text-neutral-400">{formatDate(r.date)}</p>
              )}
            </div>
          </div>
        ))}
      </div>
    </Card>
  )
}

export function DashboardView({ data, isLoading, error, onUploadClick }: Props) {
  if (error) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] gap-3 text-neutral-500">
        <p className="text-alert">Не удалось загрузить данные</p>
        <button
          onClick={() => window.location.reload()}
          className="text-sm text-trust underline"
        >
          Повторить
        </button>
      </div>
    )
  }

  if (isLoading) {
    return (
      <div className="space-y-4 p-4">
        <Skeleton className="h-20 w-full" />
        <Skeleton className="h-12 w-2/3" />
        <Skeleton className="h-32 w-full" />
        <Skeleton className="h-24 w-full" />
      </div>
    )
  }

  if (!data || !data.has_data) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4 p-6 text-center">
        <div className="text-4xl">📊</div>
        <h2 className="text-xl font-semibold text-neutral-800">Загрузите данные</h2>
        <p className="text-neutral-500 text-sm max-w-xs">
          Загрузите банковскую выписку или ОСВ из 1С, чтобы увидеть финансовую сводку
        </p>
        <button
          onClick={onUploadClick}
          className="bg-trust text-white font-medium px-6 py-3 rounded-lg hover:bg-trust-dark transition-colors"
        >
          Загрузить выписку
        </button>
      </div>
    )
  }

  const { balance, forecast, obligations, explain, stale, receivables } = data

  const deficitSignal = forecast?.deficit_signal ?? null
  const hasAgingDetail = forecast?.has_aging_detail ?? false

  // Цвет линии графика по severity
  const lineColor =
    deficitSignal?.severity === 'critical'
      ? '#D93B3B'
      : deficitSignal?.severity === 'warning'
      ? '#F59E0B'
      : '#1B4F8A'

  const baseMap = new Map((forecast?.days_preview ?? []).map((d) => [d.date, d.balance]))
  const stressMap = new Map((forecast?.days_stress ?? []).map((d) => [d.date, d.balance]))
  const allDates = [...new Set([...baseMap.keys(), ...stressMap.keys()])].sort()

  const chartData = allDates.map((date) => ({
    date: formatDate(date),
    base: baseMap.get(date) ?? null,
    stress: stressMap.get(date) ?? null,
  }))

  const hasStress = stressMap.size > 0

  return (
    <div className="space-y-4 p-4 max-w-lg mx-auto">
      {/* 1. ОСТАТОК — hero */}
      <Card>
        <div className="flex items-start justify-between">
          <div>
            <p className="text-xs text-neutral-400 uppercase tracking-wide font-medium">
              Остаток сейчас
            </p>
            <p className="text-3xl font-bold text-neutral-900 mt-1">
              {formatRub(balance!)}
            </p>
            {explain && (
              <p className="text-xs text-neutral-500 mt-1">{explain.headline}</p>
            )}
          </div>
          {stale.is_stale && (
            <Badge variant="warn">Данные {stale.hours}ч назад</Badge>
          )}
        </div>
      </Card>

      {/* 2. КАССОВЫЙ РАЗРЫВ — severity card, показывать при любом severity до 90д */}
      {deficitSignal && <CashGapCard signal={deficitSignal} />}

      {/* Прогноз неполный — нет обязательств */}
      {forecast && !forecast.has_obligations && (
        <Card className="border-warn/30 bg-warn-soft">
          <p className="text-xs text-warn font-medium">
            Прогноз неполный — добавьте обязательства для точного прогноза
          </p>
        </Card>
      )}

      {/* Прогноз неполный — дебиторка без aging-детализации */}
      {receivables && receivables.total_open > 0 && !hasAgingDetail && (
        <Card className="border-warn/30 bg-warn-soft">
          <p className="text-xs text-warn font-medium">
            Загрузите ОСВ с aging-колонками (0–30, 31–60, 61–90, 90+) для учёта дебиторки в прогнозе
          </p>
        </Card>
      )}

      {/* 3. БЛИЖАЙШИЕ ОБЯЗАТЕЛЬСТВА */}
      {obligations.length > 0 && (
        <Card>
          <p className="text-xs text-neutral-400 uppercase tracking-wide font-medium mb-3">
            Ближайшие обязательства
          </p>
          <div className="space-y-2">
            {obligations.map((ob, i) => (
              <div key={i} className="flex items-center justify-between">
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-neutral-800 truncate">
                    {ob.description}
                  </p>
                  <p className="text-xs text-neutral-400">через {ob.days_until} дн.</p>
                </div>
                <p className="text-sm font-semibold text-neutral-800 ml-4">
                  {formatRub(ob.amount)}
                </p>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* 4. ДЕБИТОРКА (1С) */}
      {receivables && receivables.total_open > 0 && (
        <ReceivablesCard receivables={receivables} />
      )}

      {/* 5. ОБЪЯСНЕНИЕ — top-3 drivers */}
      {explain && <ExplainBlock explain={explain} />}

      {/* 6. КАССОВЫЙ ПРОГНОЗ 90 дней */}
      {chartData.length > 0 && (
        <Card>
          <p className="text-xs text-neutral-400 uppercase tracking-wide font-medium mb-3">
            Кассовый прогноз, 90 дней
          </p>
          <ResponsiveContainer width="100%" height={120}>
            <LineChart data={chartData} margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
              <XAxis
                dataKey="date"
                tick={{ fontSize: 9, fill: '#9ca3af' }}
                interval={Math.floor(chartData.length / 4)}
                tickLine={false}
                axisLine={false}
              />
              <YAxis hide />
              <Tooltip
                formatter={(v: number, name: string) => [
                  formatRub(v),
                  name === 'base' ? 'По текущим данным' : 'Если поступления −15%',
                ]}
                labelStyle={{ fontSize: 10 }}
                contentStyle={{ fontSize: 11, borderRadius: 6 }}
              />
              {hasStress && (
                <Legend
                  formatter={(value) =>
                    value === 'base' ? 'По текущим данным' : 'Если поступления −15%'
                  }
                  iconType="line"
                  wrapperStyle={{ fontSize: 10, paddingTop: 4 }}
                />
              )}
              <Line
                type="monotone"
                dataKey="base"
                name="base"
                stroke={lineColor}
                strokeWidth={2}
                dot={false}
                connectNulls
              />
              {hasStress && (
                <Line
                  type="monotone"
                  dataKey="stress"
                  name="stress"
                  stroke="#F59E0B"
                  strokeWidth={1.5}
                  strokeDasharray="4 3"
                  dot={false}
                  connectNulls
                />
              )}
            </LineChart>
          </ResponsiveContainer>
        </Card>
      )}
    </div>
  )
}
