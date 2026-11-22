import { useEffect, useMemo, useRef, useState } from 'react'
import type { Message, Metrics } from './types'
import { welcomeMessage, getDemoReply } from './demo/mock'
import { sendToBackend } from './api/client'
import { isRecord, normalizeBackendUrl } from './api/backend'
import type { BackendConnection } from './api/backend'
import Header from './components/Header'
import Sidebar from './components/Sidebar'
import ChatPanel from './components/ChatPanel'
import MetricsBar from './components/MetricsBar'
import QuantView from './components/QuantView'
import ContractView from './components/ContractView'

const DEMO_METRICS: Metrics = {
  recallAt10: 0.91,
  precisionAt3: 0.87,
  lastLatencyMs: 412,
}

type View = 'chat' | 'quant' | 'contracts'
type Mode = 'demo' | 'live'

const CONNECTION_KEY = 'wecom-agent-connection'
const DEFAULT_CONNECTION: BackendConnection = { url: 'http://localhost:9000', apiKey: '' }
const LIVE_METRICS: Metrics = { recallAt10: null, precisionAt3: null, lastLatencyMs: 0 }

function restoreConnection(): BackendConnection {
  try {
    const saved: unknown = JSON.parse(sessionStorage.getItem(CONNECTION_KEY) ?? 'null')
    if (isRecord(saved) && typeof saved.url === 'string' && typeof saved.apiKey === 'string') {
      return { url: normalizeBackendUrl(saved.url), apiKey: saved.apiKey }
    }
  } catch { /* Storage can be unavailable or contain outdated values. */ }
  return DEFAULT_CONNECTION
}

function readView(): View {
  const requested = new URLSearchParams(window.location.search).get('view')
  return requested === 'contracts' || requested === 'quant' ? requested : 'chat'
}

function startConversation(mode: Mode): Message[] {
  if (mode === 'demo') return [welcomeMessage()]
  return [{
    id: 'welcome',
    role: 'assistant',
    content: '已切换到 **Live 模式**。对话使用已应用的后端连接。请输入合同编号、产品代码或客户编号开始查询。',
  }]
}

export default function App() {
  const [mode, setMode] = useState<Mode>('demo')
  const [connection, setConnection] = useState(restoreConnection)
  const [view, setView] = useState(readView)
  const [messages, setMessages] = useState<Message[]>(() => startConversation('demo'))
  const [chatRevision, setChatRevision] = useState(0)
  const [isLoading, setIsLoading] = useState(false)
  const [metrics, setMetrics] = useState<Metrics>(DEMO_METRICS)
  const activeRequest = useRef<AbortController | null>(null)

  useEffect(() => {
    try {
      // A key saved by the old UI has no stored address to bind it to.
      sessionStorage.removeItem('wecom-agent-api-key')
      sessionStorage.setItem(CONNECTION_KEY, JSON.stringify(connection))
    } catch { /* Storage can be unavailable in privacy-restricted browsers. */ }
  }, [connection])

  useEffect(() => {
    const restoreView = () => setView(readView())
    window.addEventListener('popstate', restoreView)
    return () => window.removeEventListener('popstate', restoreView)
  }, [])

  useEffect(() => () => {
    activeRequest.current?.abort()
    activeRequest.current = null
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
    const userMsg: Message = {
      id: crypto.randomUUID(),
      role: 'user',
      content: query,
    }
    setMessages((prev) => [...prev, userMsg])
    setIsLoading(true)

    try {
      if (mode === 'live') {
        const reply = await sendToBackend(connection.url, query, connection.apiKey, controller.signal)
        if (controller.signal.aborted) return
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
        if (controller.signal.aborted) return
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
      if (controller.signal.aborted) return
      setMessages((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          role: 'assistant',
          content: e instanceof Error ? e.message : '对话请求失败，请重试。',
          error: true,
        },
      ])
    } finally {
      if (activeRequest.current === controller) {
        activeRequest.current = null
        setIsLoading(false)
      }
    }
  }

  function resetConversation(nextMode: Mode) {
    activeRequest.current?.abort()
    activeRequest.current = null
    setIsLoading(false)
    setMessages(startConversation(nextMode))
    setChatRevision((revision) => revision + 1)
    setMetrics(nextMode === 'demo' ? DEMO_METRICS : LIVE_METRICS)
  }

  function changeMode(nextMode: Mode) {
    if (nextMode === mode) return
    resetConversation(nextMode)
    setMode(nextMode)
  }

  function applyConnection(next: BackendConnection) {
    if (next.url === connection.url && next.apiKey === connection.apiKey) return
    resetConversation(mode)
    setConnection(next)
  }

  function changeView(nextView: View) {
    if (nextView === view) return
    const url = new URL(window.location.href)
    if (nextView === 'chat') url.searchParams.delete('view')
    else url.searchParams.set('view', nextView)
    window.history.pushState(window.history.state, '', url)
    setView(nextView)
  }

  return (
    <div className="flex h-dvh flex-col bg-ink text-fg">
      <Header
        mode={mode}
        setMode={changeMode}
        connection={connection}
        onApplyConnection={applyConnection}
        view={view}
        setView={changeView}
      />
      <div className="flex min-h-0 flex-1">
        {view === 'chat' && <Sidebar activeTool={activeTool} />}
        <main className="flex min-h-0 min-w-0 flex-1 flex-col">
          <div className={view === 'chat' ? 'flex min-h-0 flex-1 flex-col' : 'hidden'}>
            <ChatPanel key={chatRevision} visible={view === 'chat'} mode={mode}
              messages={messages} isLoading={isLoading} onSend={handleSend} />
            <MetricsBar metrics={metrics} mode={mode} />
          </div>
          <div className={view === 'contracts' ? 'flex min-h-0 flex-1 flex-col' : 'hidden'}>
            <ContractView key={mode} mode={mode} connection={connection} />
          </div>
          {view === 'quant' && <QuantView />}
        </main>
      </div>
    </div>
  )
}
