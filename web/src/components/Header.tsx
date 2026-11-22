import { useState } from 'react'
import type { FormEvent } from 'react'
import { normalizeBackendUrl } from '../api/backend'
import type { BackendConnection } from '../api/backend'

interface Props {
  mode: 'demo' | 'live'
  setMode: (mode: 'demo' | 'live') => void
  connection: BackendConnection
  onApplyConnection: (connection: BackendConnection) => void
  view: 'chat' | 'quant' | 'contracts'
  setView: (view: 'chat' | 'quant' | 'contracts') => void
}

const views = [
  ['chat', '对话'],
  ['contracts', '合同查询'],
  ['quant', '量化分析'],
] as const

function LiveSettings({ connection, onApply }: {
  connection: BackendConnection
  onApply: (connection: BackendConnection) => void
}) {
  const [address, setAddress] = useState(connection.url)
  const [key, setKey] = useState(connection.apiKey)
  const [error, setError] = useState('')
  const saveEnabled = address !== connection.url || key !== connection.apiKey

  function apply(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    try {
      const url = normalizeBackendUrl(address)
      const apiKey = key.trim()
      if (apiKey && apiKey === connection.apiKey && new URL(url).origin !== new URL(connection.url).origin) {
        setKey('')
        setError('请为新地址填写 API Key，或留空后再次应用。')
        return
      }
      onApply({ url, apiKey })
      setAddress(url)
      setKey(apiKey)
      setError('')
    } catch (problem) {
      setError(problem instanceof Error ? problem.message : '无法应用连接。')
    }
  }

  return (
    <div className="workspace-connection">
      <form className="workspace-connection-fields" aria-label="Live 连接设置" onSubmit={apply} noValidate>
        <label>
          后端地址
          <input
            type="url"
            value={address}
            onChange={(event) => {
              setAddress(event.target.value)
              setError('')
            }}
            placeholder="http://localhost:9000"
            spellCheck={false}
          />
        </label>
        <label>
          API Key
          <input
            type="password"
            value={key}
            onChange={(event) => {
              setKey(event.target.value)
              setError('')
            }}
            placeholder="当前会话"
            autoComplete="off"
            spellCheck={false}
          />
        </label>
        <button className="workspace-connection-apply" type="submit" disabled={!saveEnabled}>应用连接</button>
        {error && <p className="workspace-connection-error" role="alert">{error}</p>}
      </form>
    </div>
  )
}

export default function Header({
  mode, setMode, connection, onApplyConnection, view, setView,
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
        <LiveSettings connection={connection} onApply={onApplyConnection} />
      )}
    </header>
  )
}
