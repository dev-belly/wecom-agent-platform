import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { CONTRACT_PAGE_SIZE, ContractQueryError, queryContracts, queryExampleContracts } from '../api/contracts'
import type { ContractFilters, ContractPage, ContractResults } from '../api/contracts'

const fields = [
  ['contract_id', '合同编号', 'text'],
  ['party_a', '甲方', 'text'],
  ['party_b', '乙方', 'text'],
  ['date_range_start', '最早签约日', 'date'],
  ['date_range_end', '最晚签约日', 'date'],
] as const

interface SearchResult {
  filters: ContractFilters
  page: ContractResults
}

function describeResults(page: ContractResults) {
  if (!page.count) return '没有符合条件的合同。'
  const total = '匹配 ' + page.count + ' 条'
  if (!page.returned_count) return total + '，此页没有记录。'
  const first = page.offset + 1
  const last = page.offset + page.returned_count
  const range = first === last ? String(first) : first + '–' + last
  const summary = total + '，显示第 ' + range + ' 条。'
  return page.truncated && page.index_revision === null ? summary + '可缩小筛选范围查看其他记录。' : summary
}

export default function ContractView({ mode, backendUrl, apiKey }: {
  mode: 'demo' | 'live'; backendUrl: string; apiKey: string
}) {
  const active = useRef<AbortController | null>(null)
  const [current, setCurrent] = useState<SearchResult | null>(() =>
    mode === 'demo' ? { filters: {}, page: queryExampleContracts({}) } : null,
  )
  const [message, setMessage] = useState('')
  const [loading, setLoading] = useState(false)
  useEffect(() => () => active.current?.abort(), [])

  function search(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    const filters: ContractFilters = {}
    for (const [key] of fields) {
      const value = String(form.get(key) ?? '').trim()
      if (value) filters[key] = value
    }

    if (filters.date_range_start && filters.date_range_end
        && filters.date_range_start > filters.date_range_end) {
      active.current?.abort()
      setCurrent(null)
      setMessage('起始日期不能晚于截止日期。')
      setLoading(false)
      return
    }
    void load(filters)
  }

  async function load(filters: ContractFilters, page?: ContractPage) {
    active.current?.abort()
    const controller = new AbortController()
    active.current = controller
    if (!page) setCurrent(null)
    setMessage('')
    setLoading(true)
    try {
      const response = mode === 'demo'
        ? queryExampleContracts(filters, page?.offset)
        : await queryContracts(backendUrl, apiKey, filters, controller.signal, page)
      if (!controller.signal.aborted) setCurrent({ filters, page: response })
    } catch (error) {
      if (controller.signal.aborted) return
      if (error instanceof ContractQueryError && error.status === 409) setCurrent(null)
      setMessage(error instanceof Error ? error.message : '合同查询失败，请重试。')
    } finally {
      if (!controller.signal.aborted) setLoading(false)
    }
  }

  function changePage(offset: number | null) {
    if (current?.page.index_revision && offset !== null) {
      void load(current.filters, { offset, index_revision: current.page.index_revision })
    }
  }

  const page = current?.page
  const showPagination = page?.index_revision && (page.offset > 0 || page.next_offset !== null)

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
    <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
      <p role="status" className="text-sm">
        {message || (loading ? '查询中…' : page && describeResults(page))}
      </p>
      {showPagination && <nav aria-label="合同结果分页" className="flex gap-2">
        <button type="button" disabled={loading || !page.offset}
          onClick={() => changePage(Math.max(0, page.offset - CONTRACT_PAGE_SIZE))}
          className="rounded border border-line px-3 py-1.5 text-sm text-fg hover:bg-surface disabled:opacity-50">上一页</button>
        <button type="button" disabled={loading || page.next_offset === null}
          onClick={() => changePage(page.next_offset)}
          className="rounded border border-line px-3 py-1.5 text-sm text-fg hover:bg-surface disabled:opacity-50">下一页</button>
      </nav>}
    </div>
    <ul aria-label="合同结果" aria-busy={loading} className="grid gap-2">
      {page?.results.map(({ parsed, metadata }, index) => <li key={page.offset + index}
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
