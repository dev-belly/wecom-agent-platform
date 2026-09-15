import { useState } from 'react'

interface Props {
  mode: 'demo' | 'live'
  setMode: (m: 'demo' | 'live') => void
  backendUrl: string
  setBackendUrl: (u: string) => void
  apiKey: string
  setApiKey: (key: string) => void
  view: 'chat' | 'quant'
  setView: (v: 'chat' | 'quant') => void
}

export default function Header({
  mode,
  setMode,
  backendUrl,
  setBackendUrl,
  apiKey,
  setApiKey,
  view,
  setView,
}: Props) {
  const [editing, setEditing] = useState(false)

  return (
    <header className="flex items-center gap-3 px-4 py-3 border-b border-line bg-surface/40">
      <div className="flex items-center gap-2">
        <div className="w-8 h-8 rounded-lg bg-teal/15 border border-teal/30 flex items-center justify-center font-mono font-bold text-teal">
          A
        </div>
        <div>
          <div className="text-sm font-semibold text-fg leading-tight">
            企微智能运营 Agent 平台
          </div>
          <div className="text-[11px] text-muted leading-tight">
            金融合同与产品要素智能查询
          </div>
        </div>
      </div>

      <div className="ml-auto flex items-center gap-2">
        <div className="flex rounded-lg border border-line overflow-hidden text-xs">
          <button
            onClick={() => setView('chat')}
            className={`px-3 py-1.5 transition ${
              view === 'chat' ? 'bg-teal/20 text-teal' : 'text-muted hover:text-fg'
            }`}
          >
            对话
          </button>
          <button
            onClick={() => setView('quant')}
            className={`px-3 py-1.5 transition ${
              view === 'quant' ? 'bg-teal/20 text-teal' : 'text-muted hover:text-fg'
            }`}
          >
            量化分析
          </button>
        </div>

        {mode === 'live' && (
          <div className="flex items-center gap-2">
            {editing ? (
              <input
                autoFocus
                value={backendUrl}
                onChange={(e) => setBackendUrl(e.target.value)}
                onBlur={() => setEditing(false)}
                onKeyDown={(e) => e.key === 'Enter' && setEditing(false)}
                placeholder="http://localhost:9000"
                aria-label="后端地址"
                className="w-48 px-2 py-1 rounded-md bg-ink border border-line text-xs font-mono text-fg outline-none focus:border-blue"
              />
            ) : (
              <button
                onClick={() => setEditing(true)}
                className="px-2 py-1 rounded-md bg-surface2 border border-line text-[11px] text-muted hover:text-fg"
                title="点击编辑后端地址"
              >
                {backendUrl || '未配置地址'}
              </button>
            )}
            <input
              type="password"
              value={apiKey}
              onChange={(event) => setApiKey(event.target.value)}
              placeholder="API Key（仅本次会话）"
              aria-label="API Key"
              autoComplete="off"
              spellCheck={false}
              className="w-44 px-2 py-1 rounded-md bg-ink border border-line text-xs font-mono text-fg outline-none focus:border-blue"
            />
          </div>
        )}

        <div className="flex rounded-lg border border-line overflow-hidden text-xs">
          <button
            onClick={() => setMode('demo')}
            className={`px-3 py-1.5 transition ${
              mode === 'demo'
                ? 'bg-teal/20 text-teal'
                : 'text-muted hover:text-fg'
            }`}
          >
            Demo
          </button>
          <button
            onClick={() => setMode('live')}
            className={`px-3 py-1.5 transition ${
              mode === 'live' ? 'bg-blue/20 text-blue' : 'text-muted hover:text-fg'
            }`}
          >
            Live
          </button>
        </div>
      </div>
    </header>
  )
}
