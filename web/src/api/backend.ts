export interface BackendConnection {
  url: string
  apiKey: string
}

export function normalizeBackendUrl(value: string): string {
  let url: URL
  try {
    url = new URL(value.trim())
  } catch {
    throw new Error('请输入完整的后端地址，例如 http://localhost:9000。')
  }
  if ((url.protocol !== 'http:' && url.protocol !== 'https:') || url.username
      || url.password || url.search || url.hash) {
    throw new Error('后端地址须使用 HTTP 或 HTTPS，且仅包含主机、端口和路径。')
  }
  return url.origin + url.pathname.replace(/\/+$/, '')
}

export function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

export function backendErrorDetail(value: unknown): string {
  return isRecord(value) && typeof value.detail === 'string'
    ? value.detail.replace(/\s+/g, ' ').trim().slice(0, 160)
    : ''
}

export async function postBackend(
  baseUrl: string, path: string, apiKey: string, body: object, signal?: AbortSignal,
): Promise<Response> {
  const endpoint = normalizeBackendUrl(baseUrl) + path
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  const key = apiKey.trim()
  if (key) headers.Authorization = 'Bearer ' + key
  try {
    return await fetch(endpoint, { method: 'POST', headers, body: JSON.stringify(body), signal })
  } catch (error) {
    if (!signal?.aborted && error instanceof TypeError) {
      throw new Error('无法连接后端。请检查服务地址、运行状态和跨域配置。')
    }
    throw error
  }
}
