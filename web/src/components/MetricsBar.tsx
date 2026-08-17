import type { Metrics } from '../types'

interface Props {
  metrics: Metrics
}

function Metric({ label, value, accent }: { label: string; value: string; accent: string }) {
  return (
    <div className="flex items-baseline gap-1.5">
      <span className="text-[11px] text-muted">{label}</span>
      <span className={`text-sm font-mono font-medium ${accent}`}>{value}</span>
    </div>
  )
}

export default function MetricsBar({ metrics }: Props) {
  return (
    <div className="flex items-center gap-5 px-4 py-1.5 border-t border-line bg-surface/40">
      <Metric label="Recall@10" value={`${(metrics.recallAt10 * 100).toFixed(0)}%`} accent="text-teal" />
      <Metric label="Precision@3" value={`${(metrics.precisionAt3 * 100).toFixed(0)}%`} accent="text-amber" />
      <Metric
        label="最近延迟"
        value={metrics.lastLatencyMs > 0 ? `${metrics.lastLatencyMs} ms` : '—'}
        accent="text-violet"
      />
      <span className="ml-auto text-[11px] text-muted">
        混合检索 · vLLM Qwen3-14B AWQ
      </span>
    </div>
  )
}
