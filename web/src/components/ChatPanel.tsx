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
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages, isLoading])

  const submit = () => {
    const text = input.trim()
    if (!text || isLoading) return
    onSend(text)
    setInput('')
  }

  return (
    <div className="flex-1 flex flex-col min-h-0">
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
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

      <div className="border-t border-line px-4 py-3 bg-surface/40">
        <div className="flex items-end gap-2">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                submit()
              }
            }}
            rows={1}
            placeholder="输入您的问题，Enter 发送 / Shift+Enter 换行"
            className="flex-1 resize-none rounded-lg bg-ink border border-line px-3 py-2.5 text-sm text-fg outline-none focus:border-blue placeholder:text-muted max-h-32"
          />
          <button
            onClick={submit}
            disabled={isLoading || !input.trim()}
            className="px-4 py-2.5 rounded-lg bg-blue text-white text-sm font-medium disabled:opacity-40 disabled:cursor-not-allowed hover:bg-blue/90 transition"
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
      className="w-1.5 h-1.5 rounded-full bg-muted animate-bounce"
      style={{ animationDelay: delay }}
    />
  )
}
