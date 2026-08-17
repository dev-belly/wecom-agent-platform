export interface RetrievedChunk {
  text: string
  score: number
  source: 'bm25' | 'vector' | 'fusion'
  rerankScore?: number
}

export interface TraceInfo {
  intent: string
  tool: string
  params: Record<string, unknown>
  retrieved: RetrievedChunk[]
  latencyMs: number
}

export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  trace?: TraceInfo
  error?: boolean
}

export interface ToolMeta {
  name: string
  label: string
  desc: string
}

export interface Metrics {
  recallAt10: number
  precisionAt3: number
  lastLatencyMs: number
}
