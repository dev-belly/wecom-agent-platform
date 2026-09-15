import type { Metrics } from '../types'

interface Props {
  metrics: Metrics
  mode: 'demo' | 'live'
}

function Metric({ label, value, accent }: { label: string; value: string; accent: string }) {
  return (
    <div className="flex items-baseline gap-1.5">
      <span className="text-[11px] text-muted">{label}</span>
      <span className={`text-sm font-mono font-medium ${accent}`}>{value}</span>
    </div>
  )
}

export default function MetricsBar({ metrics, mode }: Props) {
  const percentage = (value: number | null) => value === null ? '未评估' : `${(value * 100).toFixed(0)}%`
  return (
    <div className="flex items-center gap-5 px-4 py-1.5 border-t border-line bg-surface/40">
      <Metric label="Recall@10" value={percentage(metrics.recallAt10)} accent="text-teal" />
      <Metric label="Precision@3" value={percentage(metrics.precisionAt3)} accent="text-amber" />
      <Metric
        label="最近延迟"
        value={metrics.lastLatencyMs > 0 ? `${metrics.lastLatencyMs} ms` : '—'}
        accent="text-violet"
      />
      <span className="ml-auto text-[11px] text-muted">
        {mode === 'demo' ? '演示指标 · 非实测结果' : '检索质量需用标注集单独评估'}
      </span>
    </div>
  )
}
