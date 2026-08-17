import type { Message } from '../types'
import ToolTrace from './ToolTrace'

interface Props {
  message: Message
}

// 简单 Markdown：加粗 **x** 与换行
function renderText(text: string) {
  const lines = text.split('\n')
  return lines.map((line, i) => {
    const parts = line.split(/(\*\*[^*]+\*\*)/g)
    return (
      <p key={i} className="leading-relaxed">
        {parts.map((p, j) => {
          if (p.startsWith('**') && p.endsWith('**')) {
            return (
              <strong key={j} className="font-semibold text-fg">
                {p.slice(2, -2)}
              </strong>
            )
          }
          return <span key={j}>{p}</span>
        })}
      </p>
    )
  })
}

export default function MessageBubble({ message }: Props) {
  const isUser = message.role === 'user'

  if (isUser) {
    return (
      <div className="flex justify-end">
        <div className="max-w-[78%] rounded-2xl rounded-br-sm bg-blue/20 border border-blue/30 px-4 py-2.5 text-sm text-fg">
          {message.content}
        </div>
      </div>
    )
  }

  return (
    <div className="flex justify-start">
      <div className="max-w-[88%]">
        <div
          className={`rounded-2xl rounded-bl-sm px-4 py-2.5 text-sm border ${
            message.error
              ? 'bg-rose/10 border-rose/30 text-rose'
              : 'bg-surface border-line text-fg/95'
          }`}
        >
          {renderText(message.content)}
        </div>
        {message.trace && <ToolTrace trace={message.trace} />}
      </div>
    </div>
  )
}
