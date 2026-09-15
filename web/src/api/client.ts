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
  apiKey: string,
): Promise<Message> {
  const url = baseUrl.replace(/\/+$/, '') + '/api/chat'
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  const normalizedApiKey = apiKey.trim()
  if (normalizedApiKey) {
    headers.Authorization = `Bearer ${normalizedApiKey}`
  }
  const res = await fetch(url, {
    method: 'POST',
    headers,
    body: JSON.stringify({ message: query }),
  })

  if (!res.ok) {
    const contentType = res.headers.get('content-type') ?? ''
    let detail = ''
    if (contentType.includes('application/json')) {
      const body = (await res.json().catch(() => null)) as { detail?: unknown } | null
      if (typeof body?.detail === 'string') {
        detail = body.detail.replace(/\s+/g, ' ').trim().slice(0, 160)
      }
    }
    return {
      id: crypto.randomUUID(),
      role: 'assistant',
      content: `后端请求失败（HTTP ${res.status}）${detail ? `：${detail}` : ''}`,
      error: true,
      trace: { intent: '', tool: '', params: {}, retrieved: [], latencyMs: 0 },
    }
  }

  const data = (await res.json().catch(() => null)) as ChatApiResponse | null
  if (!data || typeof data.reply !== 'string') {
    throw new Error('后端返回格式无效')
  }
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
