import { useEffect, useMemo, useRef, useState } from 'react'
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
  const [apiKey, setApiKey] = useState(() => {
    try { return sessionStorage.getItem('wecom-agent-api-key') ?? '' }
    catch { return '' }
  })
  const [view, setView] = useState<'chat' | 'quant'>('chat')
  const [messages, setMessages] = useState<Message[]>(() => [welcomeMessage()])
  const [isLoading, setIsLoading] = useState(false)
  const [metrics, setMetrics] = useState<Metrics>(DEMO_METRICS)
  const activeRequest = useRef<AbortController | null>(null)
  const requestGeneration = useRef(0)

  useEffect(() => {
    try {
      if (apiKey) sessionStorage.setItem('wecom-agent-api-key', apiKey)
      else sessionStorage.removeItem('wecom-agent-api-key')
    } catch { /* Storage can be unavailable in privacy-restricted browsers. */ }
  }, [apiKey])

  useEffect(() => () => {
    requestGeneration.current += 1
    activeRequest.current?.abort()
  }, [])

  const activeTool = useMemo(() => {
    for (let i = messages.length - 1; i >= 0; i--) {
      const t = messages[i].trace?.tool
      if (t && t !== 'general') return t
    }
    return null
  }, [messages])

  const handleSend = async (text: string) => {
    const query = text.trim()
    if (!query || query.length > 2000 || activeRequest.current) return
    const controller = new AbortController()
    activeRequest.current = controller
    const generation = ++requestGeneration.current
    const userMsg: Message = {
      id: crypto.randomUUID(),
      role: 'user',
      content: query,
    }
    setMessages((prev) => [...prev, userMsg])
    setIsLoading(true)

    try {
      if (mode === 'live') {
        const reply = await sendToBackend(backendUrl, query, apiKey, controller.signal)
        if (generation !== requestGeneration.current) return
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
        if (generation !== requestGeneration.current) return
        const demo = getDemoReply(query)
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
      if (generation !== requestGeneration.current || controller.signal.aborted) return
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
      if (generation === requestGeneration.current) {
        activeRequest.current = null
        setIsLoading(false)
      }
    }
  }

  const changeMode = (nextMode: 'demo' | 'live') => {
    if (nextMode === mode) return
    requestGeneration.current += 1
    activeRequest.current?.abort()
    activeRequest.current = null
    setIsLoading(false)
    setMessages([welcomeMessage()])
    setMode(nextMode)
    setMetrics(nextMode === 'demo' ? DEMO_METRICS : {
      recallAt10: null,
      precisionAt3: null,
      lastLatencyMs: 0,
    })
  }

  return (
    <div className="flex h-screen bg-ink text-fg">
      <Sidebar activeTool={activeTool} />
      <div className="flex-1 flex flex-col min-w-0">
        <Header
          mode={mode}
          setMode={changeMode}
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
          <ChatPanel key={mode} messages={messages} isLoading={isLoading} onSend={handleSend} />
        )}
        <MetricsBar metrics={metrics} mode={mode} />
      </div>
    </div>
  )
}
