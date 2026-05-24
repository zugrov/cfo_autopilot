'use client'

import { OnboardingStatus } from '@/lib/api'

type Props = {
  status: OnboardingStatus
  isOwner: boolean
  onUploadOneC: () => void
  onConnectTelegram: () => void
}

export function OnboardingBanner({ status, isOwner, onUploadOneC, onConnectTelegram }: Props) {
  if (!status.show_banner) return null

  const onec = status.steps.find((s) => s.id === 'onec')
  const telegram = status.steps.find((s) => s.id === 'telegram')

  const showOnec = onec && !onec.done && !onec.skipped
  const showTelegram = isOwner && telegram && !telegram.done && !telegram.skipped

  if (!showOnec && !showTelegram) return null

  return (
    <div className="max-w-lg mx-auto mt-4 px-4">
      <div className="bg-trust/5 border border-trust/20 rounded-xl px-4 py-3 space-y-2">
        <p className="text-xs font-medium text-trust">Завершите настройку</p>
        {showOnec && (
          <div className="flex items-center justify-between gap-2">
            <p className="text-xs text-neutral-600">Добавьте 1С для прогноза дебиторки и сверки с банком</p>
            <button
              onClick={onUploadOneC}
              className="text-xs font-medium text-trust hover:text-trust-dark shrink-0"
            >
              Загрузить
            </button>
          </div>
        )}
        {showTelegram && (
          <div className="flex items-center justify-between gap-2">
            <p className="text-xs text-neutral-600">Подключите Telegram для утреннего дайджеста</p>
            <button
              onClick={onConnectTelegram}
              className="text-xs font-medium text-trust hover:text-trust-dark shrink-0"
            >
              Подключить
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
