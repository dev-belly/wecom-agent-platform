import type { Message, TraceInfo } from '../types'
import { backendErrorDetail, isRecord, postBackend } from './backend.ts'

// 连接真实后端（FastAPI /api/chat）
export async function sendToBackend(
  baseUrl: string,
  query: string,
  apiKey: string,
  signal?: AbortSignal,
): Promise<Message> {
  const res = await postBackend(baseUrl, '/api/chat', apiKey, { message: query }, signal)
  const data: unknown = await res.json().catch(() => null)

  if (!res.ok) {
    const detail = backendErrorDetail(data)
    return {
      id: crypto.randomUUID(),
      role: 'assistant',
      content: `后端请求失败（HTTP ${res.status}）${detail ? `：${detail}` : ''}`,
      error: true,
    }
  }

  if (!isRecord(data) || typeof data.reply !== 'string') {
    throw new Error('后端返回格式无效')
  }
  const intent = typeof data.intent === 'string' ? data.intent : ''
  const tool = typeof data.tool_used === 'string' ? data.tool_used : ''
  const trace: TraceInfo = {
    intent: intent || tool,
    tool: tool || intent,
    params: {},
    latencyMs: typeof data.latency_ms === 'number' && Number.isFinite(data.latency_ms)
      && data.latency_ms >= 0 ? data.latency_ms : 0,
    retrieved: [],
  }

  return {
    id: crypto.randomUUID(),
    role: 'assistant',
    content: data.reply || '（无返回内容）',
    trace,
    error: typeof data.error === 'string' && data.error.length > 0,
  }
}
