'use client'

import { DashboardData } from '@/lib/api'
import { Badge, Card, Skeleton } from '@/components/ui'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'

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

  const deficitDays = forecast?.deficit_day_14
    ? Math.ceil(
        (new Date(forecast.deficit_day_14).getTime() - Date.now()) / (1000 * 60 * 60 * 24),
      )
    : null

  const chartData = forecast?.days_preview?.map((d) => ({
    date: formatDate(d.date),
    balance: d.balance,
  }))

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

      {/* 2. ДЕФИЦИТ — alert badge */}
      {deficitDays !== null && deficitDays <= 14 && (
        <Card className="border-alert/30 bg-alert-soft">
          <div className="flex items-center gap-2">
            <span className="text-alert text-lg">⚠</span>
            <div>
              <p className="font-semibold text-alert text-sm">
                Кассовый разрыв через {deficitDays} дней
              </p>
              <p className="text-xs text-alert/70">
                {formatDate(forecast!.deficit_day_14!)}
              </p>
            </div>
          </div>
        </Card>
      )}

      {/* No obligations warning */}
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

      {/* ОБЪЯСНЕНИЕ */}
      {explain?.top_reason && (
        <Card>
          <p className="text-xs text-neutral-400 uppercase tracking-wide font-medium mb-1">
            Главная причина изменения
          </p>
          <p className="text-sm text-neutral-700">{explain.top_reason}</p>
        </Card>
      )}

      {/* 4. SPARKLINE прогноза */}
      {chartData && chartData.length > 0 && (
        <Card>
          <p className="text-xs text-neutral-400 uppercase tracking-wide font-medium mb-3">
            Прогноз 30 дней
          </p>
          <ResponsiveContainer width="100%" height={80}>
            <LineChart data={chartData}>
              <XAxis dataKey="date" hide />
              <YAxis hide />
              <Tooltip
                formatter={(v: number) => [formatRub(v), 'Прогноз']}
                labelStyle={{ fontSize: 11 }}
                contentStyle={{ fontSize: 12, borderRadius: 6 }}
              />
              <Line
                type="monotone"
                dataKey="balance"
                stroke={deficitDays !== null && deficitDays <= 30 ? '#D93B3B' : '#1B4F8A'}
                strokeWidth={2}
                dot={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </Card>
      )}
    </div>
  )
}
