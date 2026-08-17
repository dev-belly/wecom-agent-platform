import type { RetrievedChunk } from '../types'

interface Props {
  chunks: RetrievedChunk[]
}

// 检索链路可视化：BM25 → Dense Vector → Rerank → Top-3
export default function RetrievalPipeline({ chunks }: Props) {
  if (!chunks || chunks.length === 0) {
    return (
      <div className="text-xs text-muted mt-2">
        未触发检索（通用对话，无工具调用）
      </div>
    )
  }

  const steps = [
    { key: 'bm25', label: 'BM25', sub: '关键词召回 top-50', color: 'text-teal' },
    { key: 'vector', label: 'Dense Vector', sub: 'bge-large-zh top-20', color: 'text-amber' },
    { key: 'rerank', label: 'Reranker', sub: 'bge-reranker-v2-m3', color: 'text-violet' },
  ]

  return (
    <div className="mt-3">
      <div className="flex items-center gap-1 text-[11px] text-muted mb-2">
        <span>混合检索链路</span>
      </div>
      <div className="flex items-center gap-1 flex-wrap">
        {steps.map((s, i) => (
          <div key={s.key} className="flex items-center gap-1">
            <div className="px-2.5 py-1.5 rounded-md bg-surface2 border border-line">
              <div className={`text-xs font-medium ${s.color}`}>{s.label}</div>
              <div className="text-[10px] text-muted">{s.sub}</div>
            </div>
            {i < steps.length - 1 && (
              <span className="text-muted text-sm">→</span>
            )}
          </div>
        ))}
        <span className="text-muted text-sm">→</span>
        <div className="px-2.5 py-1.5 rounded-md bg-surface2 border border-blue/40">
          <div className="text-xs font-medium text-blue">Top-3</div>
          <div className="text-[10px] text-muted">RRF 融合 + 重排</div>
        </div>
      </div>

      <div className="mt-3 space-y-1.5">
        {chunks.slice(0, 3).map((c, i) => (
          <div
            key={i}
            className="flex items-start gap-2 rounded-md bg-surface2/60 border border-line px-2.5 py-1.5"
          >
            <span className="mt-0.5 text-[10px] font-mono text-muted shrink-0">
              #{i + 1}
            </span>
            <span className="text-[11px] text-fg/90 leading-relaxed flex-1 break-all">
              {c.text}
            </span>
            <span className="text-[10px] font-mono text-teal shrink-0">
              {typeof c.rerankScore === 'number'
                ? `rerank ${c.rerankScore.toFixed(2)}`
                : `sim ${c.score.toFixed(2)}`}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}
