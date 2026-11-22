import { useEffect, useRef, useState } from 'react'
import type { Message } from '../types'
import MessageBubble from './MessageBubble'

interface Props {
  messages: Message[]
  isLoading: boolean
  onSend: (text: string) => void
}

const SUGGESTIONS = [
  '查询合同 HT20240315001 的信息',
  '星辰稳健增益 1 号最新净值是多少',
  '客户 C2024001 的持仓情况',
]

export default function ChatPanel({ messages, isLoading, onSend }: Props) {
  const [input, setInput] = useState('')
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const panel = scrollRef.current
    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    panel?.scrollTo({ top: panel.scrollHeight, behavior: reducedMotion ? 'auto' : 'smooth' })
  }, [messages, isLoading])

  const submit = () => {
    const text = input.trim()
    if (!text || isLoading) return
    onSend(text)
    setInput('')
  }

  return (
    <div className="flex-1 flex flex-col min-h-0">
      <div ref={scrollRef} className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-4xl space-y-4 px-4 py-6 sm:px-6">
          <h1 className="text-2xl font-bold tracking-tight">Agent 对话</h1>
          {messages.map((m) => (
            <MessageBubble key={m.id} message={m} />
          ))}

          {isLoading && (
            <div className="flex justify-start">
              <div className="rounded-2xl rounded-bl-sm px-4 py-3 bg-surface border border-line">
                <div className="flex items-center gap-1.5">
                  <Dot delay="0ms" />
                  <Dot delay="150ms" />
                  <Dot delay="300ms" />
                  <span className="text-xs text-muted ml-1">Agent 推理中…</span>
                </div>
              </div>
            </div>
          )}

          {messages.length <= 1 && !isLoading && (
            <div className="pt-2">
              <div className="text-xs text-muted mb-2">试试这些提问：</div>
              <div className="flex flex-wrap gap-2">
                {SUGGESTIONS.map((s) => (
                  <button
                    key={s}
                    onClick={() => onSend(s)}
                    className="px-3 py-1.5 rounded-full border border-line bg-surface2/50 text-xs text-fg/90 hover:border-blue/50 hover:text-blue transition"
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="border-t border-line bg-surface px-4 py-3 sm:px-6">
        <div className="mx-auto flex max-w-4xl items-end gap-2">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey
                  && !e.nativeEvent.isComposing && e.keyCode !== 229) {
                e.preventDefault()
                submit()
              }
            }}
            rows={1}
            maxLength={2000}
            placeholder="输入您的问题，Enter 发送 / Shift+Enter 换行"
            aria-label="给 Agent 的问题"
            className="min-w-0 flex-1 resize-none rounded-xl border border-line bg-ink px-3 py-2.5 text-base text-fg focus:border-blue placeholder:text-muted sm:text-sm"
          />
          <button
            onClick={submit}
            disabled={isLoading || !input.trim()}
            className="shrink-0 rounded-xl bg-blue px-4 py-2.5 text-sm font-semibold text-white hover:bg-blue/90 disabled:cursor-not-allowed disabled:opacity-40"
          >
            发送
          </button>
        </div>
      </div>
    </div>
  )
}

function Dot({ delay }: { delay: string }) {
  return (
    <span
      className="h-1.5 w-1.5 rounded-full bg-muted motion-safe:animate-bounce"
      style={{ animationDelay: delay }}
    />
  )
}
