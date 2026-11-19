import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { queryContracts, queryExampleContracts } from '../api/contracts'
import type { ContractFilters, ContractResults } from '../api/contracts'

const fields = [
  ['contract_id', '合同编号', 'text'],
  ['party_a', '甲方', 'text'],
  ['party_b', '乙方', 'text'],
  ['date_range_start', '最早签约日', 'date'],
  ['date_range_end', '最晚签约日', 'date'],
] as const

export default function ContractView({ mode, backendUrl, apiKey }: {
  mode: 'demo' | 'live'; backendUrl: string; apiKey: string
}) {
  const active = useRef<AbortController | null>(null)
  const [results, setResults] = useState<ContractResults | null>(null)
  const [message, setMessage] = useState('')
  const [loading, setLoading] = useState(false)
  useEffect(() => () => active.current?.abort(), [])

  async function search(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    const filters: ContractFilters = {}
    for (const [key] of fields) {
      const value = String(form.get(key) ?? '').trim()
      if (value) filters[key] = value
    }

    active.current?.abort()
    setResults(null)
    if (filters.date_range_start && filters.date_range_end
        && filters.date_range_start > filters.date_range_end) {
      setMessage('起始日期不能晚于截止日期。')
      setLoading(false)
      return
    }
    const controller = new AbortController()
    active.current = controller
    setMessage('')
    setLoading(true)
    try {
      const response = mode === 'demo'
        ? queryExampleContracts(filters)
        : await queryContracts(backendUrl, apiKey, filters, controller.signal)
      if (!controller.signal.aborted) setResults(response)
    } catch (error) {
      if (!controller.signal.aborted) setMessage((error as Error).message)
    } finally {
      if (!controller.signal.aborted) setLoading(false)
    }
  }

  return <section className="min-h-0 flex-1 overflow-auto p-4 sm:p-6">
    <h1 className="text-xl font-semibold">合同查询</h1>
    <p className="mt-1 text-sm text-muted">
      {mode === 'demo' ? '合成台账共 12 条记录，可试查 DEMO-001。' : '查询已索引合同，签约日期包含起止两日。'}
    </p>
    <form onSubmit={search} className="my-4 grid gap-3 rounded-lg border border-line bg-surface p-4 sm:grid-cols-2">
      {fields.map(([name, label, type]) => <label key={name} className="grid gap-1 text-sm">
        {label}
        <input name={name} type={type} maxLength={200}
          className="min-w-0 rounded border border-line bg-ink p-2 text-fg" />
      </label>)}
      <button disabled={loading} className="self-end rounded bg-teal/20 p-2 text-teal disabled:opacity-60">
        {loading ? '查询中…' : '查询合同'}
      </button>
    </form>
    <p role="status" className="mb-3 text-sm">
      {message || (results && ('匹配 ' + results.count + ' 条，显示 ' + results.returned_count + ' 条'
        + (results.truncated ? '。可缩小筛选范围查看其他记录。' : '。')))}
    </p>
    {results?.results.length === 0 && <p>没有符合条件的合同。</p>}
    <ul className="grid gap-2">
      {results?.results.map(({ parsed, metadata }, index) => <li key={index}
        className="break-words rounded-lg border border-line bg-surface p-3 text-sm">
        <strong>{parsed.contract_id || '编号缺失'}</strong>
        <p>{parsed.party_a || '甲方缺失'} → {parsed.party_b || '乙方缺失'} · {parsed.sign_date || '日期缺失'}</p>
        <p className="text-muted">{metadata.source || '来源缺失'}
          {metadata.page != null && ' · 第 ' + metadata.page + ' 页'}
          {metadata.table_index != null && ' · 表 ' + (metadata.table_index + 1)}
          {metadata.row_index != null && ' · 行 ' + (metadata.row_index + 1)}
        </p>
      </li>)}
    </ul>
  </section>
}
