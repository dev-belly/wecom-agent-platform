interface Props {
  mode: 'demo' | 'live'
  setMode: (mode: 'demo' | 'live') => void
  backendUrl: string
  setBackendUrl: (url: string) => void
  apiKey: string
  setApiKey: (key: string) => void
  view: 'chat' | 'quant' | 'contracts'
  setView: (view: 'chat' | 'quant' | 'contracts') => void
}

const views = [
  ['chat', '对话'],
  ['contracts', '合同查询'],
  ['quant', '量化分析'],
] as const

export default function Header({
  mode, setMode, backendUrl, setBackendUrl, apiKey, setApiKey, view, setView,
}: Props) {
  return (
    <header className="workspace-header">
      <div className="workspace-toolbar">
        <div className="workspace-brand">
          <span className="workspace-brand-mark" aria-hidden="true">A</span>
          <span>企微 Agent</span>
        </div>
        <nav className="workspace-segmented workspace-tabs" aria-label="工作区">
          {views.map(([id, label]) => (
            <button type="button" key={id} aria-pressed={view === id} onClick={() => setView(id)}>
              {label}
            </button>
          ))}
        </nav>
        <div className="workspace-segmented workspace-mode" role="group" aria-label="数据模式">
          <button type="button" aria-pressed={mode === 'demo'} onClick={() => setMode('demo')}>Demo</button>
          <button type="button" aria-pressed={mode === 'live'} onClick={() => setMode('live')}>Live</button>
        </div>
      </div>
      {mode === 'live' && (
        <div className="workspace-connection">
          <div className="workspace-connection-fields">
            <label>
              后端地址
              <input
                type="url"
                value={backendUrl}
                onChange={(event) => setBackendUrl(event.target.value)}
                placeholder="http://localhost:9000"
                spellCheck={false}
              />
            </label>
            <label>
              API Key
              <input
                type="password"
                value={apiKey}
                onChange={(event) => setApiKey(event.target.value)}
                placeholder="仅保留在当前会话"
                autoComplete="off"
                spellCheck={false}
              />
            </label>
          </div>
        </div>
      )}
    </header>
  )
}
