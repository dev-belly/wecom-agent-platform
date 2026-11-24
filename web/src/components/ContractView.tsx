import { useLayoutEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import type { BackendConnection } from '../api/backend'
import { CONTRACT_PAGE_SIZE, ContractQueryError, queryContracts, queryExampleContracts } from '../api/contracts'
import type { ContractFilters, ContractPage, ContractResults, ContractRow } from '../api/contracts'
import './ContractView.css'

const SAMPLE_CONTRACT_ID = 'DEMO-001'

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

function initialSearch(mode: 'demo' | 'live'): SearchResult | null {
  return mode === 'demo' ? { filters: {}, page: queryExampleContracts({}) } : null
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

function ContractResult({ parsed, metadata }: ContractRow) {
  return (
    <details className="contract-result">
      <summary className="contract-result-grid">
        <span className="contract-number">
          <span className="sr-only">合同编号 </span>
          {parsed.contract_id || '编号缺失'}
        </span>
        <span>
          <span className="contract-row-label">甲方 </span>
          {parsed.party_a || '—'}
        </span>
        <span>
          <span className="contract-row-label">乙方 </span>
          {parsed.party_b || '—'}
        </span>
        <span className="contract-date">
          <span className="contract-row-label">签约日 </span>
          {parsed.sign_date || '—'}
        </span>
        <span className="contract-source-toggle">
          <span className="sr-only">来源 </span>
          {metadata.page == null ? '查看' : '第 ' + metadata.page + ' 页'}
          <span className="contract-chevron" aria-hidden="true" />
        </span>
      </summary>
      <dl className="contract-provenance">
        <div><dt>来源文件</dt><dd>{metadata.source || '—'}</dd></div>
        <div><dt>页码</dt><dd>{metadata.page ?? '—'}</dd></div>
        <div><dt>表格</dt><dd>{metadata.table_index == null ? '—' : metadata.table_index + 1}</dd></div>
        <div><dt>行号</dt><dd>{metadata.row_index == null ? '—' : metadata.row_index + 1}</dd></div>
      </dl>
    </details>
  )
}

export default function ContractView({ mode, connection }: {
  mode: 'demo' | 'live'; connection: BackendConnection
}) {
  const active = useRef<AbortController | null>(null)
  const formRef = useRef<HTMLFormElement>(null)
  const resultsHeadingRef = useRef<HTMLDivElement>(null)
  const [current, setCurrent] = useState<SearchResult | null>(() => initialSearch(mode))
  const [message, setMessage] = useState('')
  const [loading, setLoading] = useState(false)
  useLayoutEffect(() => {
    if (mode === 'live') {
      setCurrent(null)
      setMessage('')
      setLoading(false)
    }
    return () => active.current?.abort()
  }, [connection, mode])

  function search(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    const filters: ContractFilters = {}
    for (const [key] of fields) {
      const value = String(form.get(key) ?? '').trim()
      if (value) filters[key] = value
    }

    resultsHeadingRef.current?.scrollIntoView({ block: 'nearest' })
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

  function resetSearch() {
    formRef.current?.reset()
    active.current?.abort()
    setCurrent(initialSearch(mode))
    setMessage('')
    setLoading(false)
  }

  function searchExample() {
    const form = formRef.current
    const contractId = form?.elements.namedItem('contract_id')
    if (!form || !(contractId instanceof HTMLInputElement)) return
    form.reset()
    contractId.value = SAMPLE_CONTRACT_ID
    form.requestSubmit()
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
        : await queryContracts(connection.url, connection.apiKey, filters, controller.signal, page)
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
  const status = loading ? '查询中…' : page ? describeResults(page) : '可填写筛选条件，也可直接查询全部合同。'

  return (
    <section className="contract-page" aria-labelledby="contract-title">
      <div className="contract-workspace">
        <div className="contract-hero">
          <div>
            <p className="contract-scope">{mode === 'demo' ? '合成演示数据' : '合同索引'}</p>
            <h1 id="contract-title">合同查询</h1>
            <p className="contract-intro">按合同编号、签约方或日期筛选，展开记录查看来源文件与页码。</p>
          </div>
          {mode === 'demo' && (
            <button type="button" className="contract-example" onClick={searchExample}>
              <span className="contract-example-icon" aria-hidden="true" />
              <span>
                <span className="contract-example-label">试查示例合同</span>
                <strong>{SAMPLE_CONTRACT_ID}</strong>
              </span>
              <span className="contract-example-arrow" aria-hidden="true">↗</span>
            </button>
          )}
        </div>
        <form ref={formRef} onSubmit={search} className="contract-panel contract-filters" aria-labelledby="filter-heading">
          <div className="contract-panel-heading">
            <h2 id="filter-heading">筛选条件</h2>
            <button type="button" className="contract-reset" onClick={resetSearch}>清空筛选</button>
          </div>
          <div className="contract-fields">
            {fields.map(([name, label, type]) => (
              <label key={name}>
                {label}
                <input name={name} type={type} maxLength={200}
                  placeholder={name === 'contract_id' ? '输入完整编号' : undefined} />
              </label>
            ))}
            <button type="submit" disabled={loading} className="contract-submit">
              {loading ? '查询中…' : '查询合同'}
            </button>
          </div>
        </form>
        <section className="contract-panel" aria-labelledby="results-heading">
          <div ref={resultsHeadingRef} className="contract-panel-heading contract-results-heading">
            <div>
              <h2 id="results-heading">查询结果</h2>
              <p role="status" className={message ? 'contract-status contract-error' : 'contract-status'}>
                {message || status}
              </p>
            </div>
            {showPagination && <nav aria-label="合同结果分页" className="contract-pagination">
              <button type="button" disabled={loading || !page.offset}
                onClick={() => changePage(Math.max(0, page.offset - CONTRACT_PAGE_SIZE))}>上一页</button>
              <button type="button" disabled={loading || page.next_offset === null}
                onClick={() => changePage(page.next_offset)}>下一页</button>
            </nav>}
          </div>
          {page && page.results.length > 0 && (
            <>
              <div className="contract-result-grid contract-result-head" aria-hidden="true">
                <span>合同编号</span>
                <span>甲方</span>
                <span>乙方</span>
                <span>签约日期</span>
                <span>来源</span>
              </div>
              <ul role="list" aria-label="合同结果" aria-busy={loading}>
                {page.results.map((row, index) => (
                  <li key={JSON.stringify([page.offset + index, row.parsed.contract_id, row.metadata])}>
                    <ContractResult {...row} />
                  </li>
                ))}
              </ul>
            </>
          )}
        </section>
      </div>
    </section>
  )
}
