import { useState } from 'react'
import type { TraceInfo } from '../types'
import { toolLabel } from '../constants'
import RetrievalPipeline from './RetrievalPipeline'

interface Props {
  trace: TraceInfo
}

export default function ToolTrace({ trace }: Props) {
  const [open, setOpen] = useState(true)

  const hasTool = trace.tool && trace.tool !== 'general'

  return (
    <div className="mt-2 rounded-lg border border-line bg-surface2/50 overflow-hidden">
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between px-3 py-2 text-left hover:bg-surface2 transition"
      >
        <div className="flex items-center gap-2 text-xs">
          <span className="text-muted">工具调用追踪</span>
          {hasTool && (
            <span className="px-1.5 py-0.5 rounded bg-blue/15 text-blue text-[11px] font-medium">
              {toolLabel(trace.tool)}
            </span>
          )}
          <span className="font-mono text-[11px] text-teal">
            {trace.latencyMs > 0 ? `${trace.latencyMs} ms` : '—'}
          </span>
        </div>
        <span className="text-muted text-xs">{open ? '收起' : '展开'}</span>
      </button>

      {open && (
        <div className="px-3 pb-3 text-xs border-t border-line">
          <div className="grid grid-cols-2 gap-x-4 gap-y-1.5 py-2">
            <div>
              <span className="text-muted">意图识别：</span>
              <span className="font-mono text-fg/90">{trace.intent || '—'}</span>
            </div>
            <div>
              <span className="text-muted">调用工具：</span>
              <span className="font-mono text-fg/90">{trace.tool || '—'}</span>
            </div>
          </div>

          {trace.params && Object.keys(trace.params).length > 0 && (
            <div className="mb-2">
              <div className="text-muted mb-1">查询参数（Pydantic 校验通过）：</div>
              <pre className="text-[11px] font-mono bg-ink/60 rounded px-2 py-1.5 overflow-x-auto text-fg/90">
                {JSON.stringify(trace.params, null, 2)}
              </pre>
            </div>
          )}

          <RetrievalPipeline chunks={trace.retrieved} />
        </div>
      )}
    </div>
  )
}
