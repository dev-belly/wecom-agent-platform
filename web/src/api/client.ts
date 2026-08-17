import type { Message, TraceInfo } from '../types'

interface ChatApiResponse {
  reply: string
  trace_id: string
  intent: string
  latency_ms: number
  tool_used: string
  error?: string | null
}

// 连接真实后端（FastAPI /api/chat）
export async function sendToBackend(
  baseUrl: string,
  query: string,
): Promise<Message> {
  const url = baseUrl.replace(/\/+$/, '') + '/api/chat'
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message: query }),
  })

  if (!res.ok) {
    const text = await res.text().catch(() => '')
    return {
      id: crypto.randomUUID(),
      role: 'assistant',
      content: `后端请求失败（${res.status}）：${text.slice(0, 200)}`,
      error: true,
      trace: { intent: '', tool: '', params: {}, retrieved: [], latencyMs: 0 },
    }
  }

  const data: ChatApiResponse = await res.json()
  const trace: TraceInfo = {
    intent: data.intent || data.tool_used || '',
    tool: data.tool_used || data.intent || '',
    params: {},
    latencyMs: data.latency_ms ?? 0,
    retrieved: [],
  }

  return {
    id: crypto.randomUUID(),
    role: 'assistant',
    content: data.reply || '（无返回内容）',
    trace,
    error: !!data.error,
  }
}
