'use client'

import { useState, useRef, useEffect } from 'react'
import { api } from '@/lib/api'
import { Skeleton } from '@/components/ui'

type Message = {
  role: 'user' | 'assistant'
  text: string
}

const SUGGESTED_QUESTIONS = [
  'Сколько денег сейчас на счёте?',
  'Когда ожидается кассовый разрыв?',
  'Почему изменился остаток за последние 7 дней?',
  'Какой главный финансовый риск сегодня?',
  'Каков прогноз остатка на 30 дней вперёд?',
]

type Props = {
  onClose: () => void
}

export function AiChatPanel({ onClose }: Props) {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    inputRef.current?.focus()
  }, [])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isLoading])

  const sendQuestion = async (question: string) => {
    const q = question.trim()
    if (!q || isLoading) return

    setInput('')
    setError(null)
    setMessages((prev) => [...prev, { role: 'user', text: q }])
    setIsLoading(true)

    try {
      const result = await api.askAI(q)
      setMessages((prev) => [...prev, { role: 'assistant', text: result.answer }])
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Не удалось получить ответ')
    } finally {
      setIsLoading(false)
    }
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    sendQuestion(input)
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendQuestion(input)
    }
  }

  const isEmpty = messages.length === 0 && !isLoading

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center">
      <div className="absolute inset-0 bg-black/30" onClick={onClose} />
      <div className="relative bg-white w-full sm:max-w-lg sm:rounded-xl shadow-xl flex flex-col h-[85vh] sm:h-[70vh]">

        {/* Заголовок */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-neutral-200 shrink-0">
          <div>
            <h2 className="text-sm font-semibold text-neutral-900">Спросить автопилот</h2>
            <p className="text-xs text-neutral-400">AI CFO на основе ваших данных</p>
          </div>
          <button
            onClick={onClose}
            className="text-neutral-400 hover:text-neutral-600 transition-colors text-lg leading-none"
          >
            ×
          </button>
        </div>

        {/* Сообщения */}
        <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3">
          {isEmpty && (
            <div className="flex flex-col items-center justify-center h-full gap-4">
              <p className="text-sm text-neutral-500 text-center">
                Задайте вопрос о ваших финансах
              </p>
              <div className="w-full space-y-2">
                {SUGGESTED_QUESTIONS.map((q) => (
                  <button
                    key={q}
                    onClick={() => sendQuestion(q)}
                    className="w-full text-left text-xs px-3 py-2 rounded-lg border border-neutral-200 text-neutral-700 hover:border-neutral-400 hover:bg-neutral-50 transition-colors"
                  >
                    {q}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((msg, i) => (
            <div
              key={i}
              className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              <div
                className={
                  msg.role === 'user'
                    ? 'bg-neutral-900 text-white rounded-xl px-3 py-2 ml-8 text-sm'
                    : 'bg-white border border-neutral-200 rounded-xl px-3 py-2 mr-8 text-sm text-neutral-800 whitespace-pre-wrap'
                }
              >
                {msg.text}
              </div>
            </div>
          ))}

          {isLoading && (
            <div className="flex justify-start">
              <div className="mr-8 w-full">
                <Skeleton className="h-16 w-full" />
              </div>
            </div>
          )}

          {error && (
            <div className="text-xs text-red-500 bg-red-50 rounded-lg px-3 py-2">
              {error}
            </div>
          )}

          <div ref={bottomRef} />
        </div>

        {/* Подсказки после первого ответа */}
        {!isEmpty && !isLoading && (
          <div className="px-4 pb-1 flex gap-2 overflow-x-auto shrink-0 scrollbar-hide">
            {SUGGESTED_QUESTIONS.slice(0, 3).map((q) => (
              <button
                key={q}
                onClick={() => sendQuestion(q)}
                className="shrink-0 text-xs px-2.5 py-1 rounded-full border border-neutral-200 text-neutral-600 hover:border-neutral-400 hover:bg-neutral-50 transition-colors whitespace-nowrap"
              >
                {q}
              </button>
            ))}
          </div>
        )}

        {/* Ввод */}
        <form
          onSubmit={handleSubmit}
          className="px-4 py-3 border-t border-neutral-200 shrink-0 flex gap-2 items-end"
        >
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Задайте вопрос…"
            rows={1}
            className="flex-1 resize-none px-3 py-2 text-sm border border-neutral-200 rounded-lg outline-none focus:border-neutral-400 focus:ring-1 focus:ring-neutral-400 max-h-24 overflow-y-auto"
          />
          <button
            type="submit"
            disabled={!input.trim() || isLoading}
            className="px-4 py-2 text-sm font-medium bg-neutral-900 text-white rounded-lg hover:bg-neutral-800 disabled:opacity-40 transition-colors shrink-0"
          >
            Отправить
          </button>
        </form>
      </div>
    </div>
  )
}
