'use client'

import { DashboardData, ExplainReason } from '@/lib/api'
import { Badge, Card, Skeleton } from '@/components/ui'
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

function daysUntil(iso: string): number {
  return Math.ceil((new Date(iso).getTime() - Date.now()) / 86400000)
}

function ReasonIcon({ type }: { type: string }) {
  if (type === 'debit') return <span className="text-red-500">↓</span>
  if (type === 'credit') return <span className="text-green-600">↑</span>
  return <span className="text-amber-500">📅</span>
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
        <h2 className="text-xl font-semibold text-neutral-800">Загрузите банковскую выписку</h2>
        <p className="text-neutral-500 text-sm max-w-xs">
          Загрузите CSV-файл из Сбербанка или Тинькофф, чтобы увидеть финансовую сводку
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

  const { balance, forecast, obligations, alerts, explain, stale } = data

  // B3: сигнал кассового разрыва — ранний из base/stress
  const deficitSignal = forecast?.deficit_signal
  const deficitDays = deficitSignal ? daysUntil(deficitSignal.date) : null

  // Объединяем base + stress для графика
  const baseMap = new Map((forecast?.days_preview ?? []).map((d) => [d.date, d.balance]))
  const stressMap = new Map((forecast?.days_stress ?? []).map((d) => [d.date, d.balance]))
  const allDates = [...new Set([...baseMap.keys(), ...stressMap.keys()])].sort()

  const chartData = allDates.map((date) => ({
    date: formatDate(date),
    base: baseMap.get(date) ?? null,
    stress: stressMap.get(date) ?? null,
  }))

  const hasStress = stressMap.size > 0
  const isDeficitRisk = deficitDays !== null && deficitDays <= 30

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

      {/* 2. КАССОВЫЙ РАЗРЫВ — B3 сигнал */}
      {deficitDays !== null && deficitDays <= 30 && (
        <Card className="border-alert/30 bg-alert-soft">
          <div className="flex items-start gap-2">
            <span className="text-alert text-lg shrink-0">⚠</span>
            <div>
              <p className="font-semibold text-alert text-sm">
                Кассовый разрыв{deficitSignal?.is_stress ? ' возможен' : ''} через {deficitDays} дней
              </p>
              <p className="text-xs text-alert/70">
                {formatDate(deficitSignal!.date)}
                {deficitSignal?.is_stress && ' · если поступления −15%'}
              </p>
            </div>
          </div>
        </Card>
      )}

      {/* Нет обязательств — прогноз неполный */}
      {forecast && !forecast.has_obligations && (
        <Card className="border-warn/30 bg-warn-soft">
          <p className="text-xs text-warn font-medium">
            Прогноз неполный — добавьте обязательства
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

      {/* 4. ОБЪЯСНЕНИЕ — C2 top-3 */}
      {explain && <ExplainBlock explain={explain} />}

      {/* 5. КАССОВЫЙ ПРОГНОЗ 90 дней — A2+E3 */}
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
                stroke={isDeficitRisk ? '#D93B3B' : '#1B4F8A'}
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
