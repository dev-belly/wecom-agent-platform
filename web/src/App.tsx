import { useEffect, useMemo, useState } from 'react'
import type { Message, Metrics } from './types'
import { welcomeMessage, getDemoReply } from './demo/mock'
import { sendToBackend } from './api/client'
import Header from './components/Header'
import Sidebar from './components/Sidebar'
import ChatPanel from './components/ChatPanel'
import MetricsBar from './components/MetricsBar'
import QuantView from './components/QuantView'

const DEMO_METRICS: Metrics = {
  recallAt10: 0.91,
  precisionAt3: 0.87,
  lastLatencyMs: 412,
}

export default function App() {
  const [mode, setMode] = useState<'demo' | 'live'>('demo')
  const [backendUrl, setBackendUrl] = useState('http://localhost:9000')
  const [apiKey, setApiKey] = useState(() => sessionStorage.getItem('wecom-agent-api-key') ?? '')
  const [view, setView] = useState<'chat' | 'quant'>('chat')
  const [messages, setMessages] = useState<Message[]>(() => [welcomeMessage()])
  const [isLoading, setIsLoading] = useState(false)
  const [metrics, setMetrics] = useState<Metrics>(DEMO_METRICS)

  useEffect(() => {
    if (apiKey) {
      sessionStorage.setItem('wecom-agent-api-key', apiKey)
    } else {
      sessionStorage.removeItem('wecom-agent-api-key')
    }
  }, [apiKey])

  const activeTool = useMemo(() => {
    for (let i = messages.length - 1; i >= 0; i--) {
      const t = messages[i].trace?.tool
      if (t && t !== 'general') return t
    }
    return null
  }, [messages])

  const handleSend = async (text: string) => {
    const userMsg: Message = {
      id: crypto.randomUUID(),
      role: 'user',
      content: text,
    }
    setMessages((prev) => [...prev, userMsg])
    setIsLoading(true)

    try {
      if (mode === 'live') {
        const reply = await sendToBackend(backendUrl, text, apiKey)
        setMessages((prev) => [...prev, reply])
        if (reply.trace) {
          setMetrics((m) => ({
            ...m,
            lastLatencyMs: reply.trace?.latencyMs ?? m.lastLatencyMs,
          }))
        }
      } else {
        // 模拟推理延迟
        await new Promise((r) => setTimeout(r, 600))
        const demo = getDemoReply(text)
        const reply: Message = {
          id: crypto.randomUUID(),
          role: 'assistant',
          content: demo.content,
          trace: demo.trace,
        }
        setMessages((prev) => [...prev, reply])
        setMetrics((m) => ({
          ...m,
          lastLatencyMs: demo.trace.latencyMs || m.lastLatencyMs,
        }))
      }
    } catch (e) {
      setMessages((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          role: 'assistant',
          content: `出错了：${(e as Error).message}`,
          error: true,
          trace: { intent: '', tool: '', params: {}, retrieved: [], latencyMs: 0 },
        },
      ])
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="flex h-screen bg-ink text-fg">
      <Sidebar activeTool={activeTool} />
      <div className="flex-1 flex flex-col min-w-0">
        <Header
          mode={mode}
          setMode={(m) => {
            setMode(m)
            setMetrics(m === 'demo' ? DEMO_METRICS : {
              recallAt10: null,
              precisionAt3: null,
              lastLatencyMs: 0,
            })
          }}
          backendUrl={backendUrl}
          setBackendUrl={setBackendUrl}
          apiKey={apiKey}
          setApiKey={setApiKey}
          view={view}
          setView={setView}
        />
        {view === 'quant' ? (
          <QuantView />
        ) : (
          <ChatPanel messages={messages} isLoading={isLoading} onSend={handleSend} />
        )}
        <MetricsBar metrics={metrics} mode={mode} />
      </div>
    </div>
  )
}
