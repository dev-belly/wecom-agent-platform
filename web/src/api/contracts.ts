export interface ContractFilters {
  contract_id?: string
  party_a?: string
  party_b?: string
  date_range_start?: string
  date_range_end?: string
}

export interface ContractRow {
  parsed: { contract_id?: string; party_a?: string; party_b?: string; sign_date?: string }
  metadata: { source?: string; page?: number; table_index?: number; row_index?: number }
}

export interface ContractResults {
  count: number
  returned_count: number
  truncated: boolean
  offset: number
  next_offset: number | null
  index_revision: string | null
  results: ContractRow[]
}

export interface ContractPage {
  offset: number
  index_revision: string
}

export const CONTRACT_PAGE_SIZE = 10

export class ContractQueryError extends Error {
  readonly status: number

  constructor(status: number, detail: string) {
    super('查询失败（HTTP ' + status + '）' + detail)
    this.status = status
  }
}

export async function queryContracts(
  baseUrl: string, apiKey: string, filters: ContractFilters, signal: AbortSignal, page?: ContractPage,
): Promise<ContractResults> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (apiKey.trim()) headers.Authorization = 'Bearer ' + apiKey.trim()
  const endpoint = baseUrl.replace(/\/+$/, '') + '/api/contracts/query'
  const pagination = page ? '?' + new URLSearchParams({
    offset: String(page.offset), index_revision: page.index_revision,
  }) : ''
  const response = await fetch(endpoint + pagination, {
    method: 'POST', headers, body: JSON.stringify(filters), signal,
  })
  const data = await response.json().catch(() => null)
  if (!response.ok) {
    const detail = typeof data?.detail === 'string' ? ' · ' + data.detail.slice(0, 160) : ''
    throw new ContractQueryError(response.status, detail)
  }
  if (!data || !Number.isSafeInteger(data.count) || !Array.isArray(data.results)
      || data.returned_count !== data.results.length || data.count < data.returned_count
      || data.truncated !== (data.count > data.returned_count)
      || data.results.some((row: ContractRow) => !row?.parsed || !row.metadata)) {
    throw new Error('合同查询返回格式无效')
  }
  if (!page && data.offset === undefined && data.next_offset === undefined) {
    return { ...data, offset: 0, next_offset: null, index_revision: null }
  }
  const offset = page?.offset ?? 0
  const countOnPage = Math.max(0, Math.min(CONTRACT_PAGE_SIZE, data.count - offset))
  const nextOffset = offset + countOnPage < data.count ? offset + countOnPage : null
  if (data.offset !== offset || data.next_offset !== nextOffset || data.returned_count !== countOnPage
      || typeof data.index_revision !== 'string' || !data.index_revision
      || (page && data.index_revision !== page.index_revision)) {
    throw new Error('合同查询返回的页码或索引版本无效，请重新查询。')
  }
  return data
}

const examples: ContractRow[] = Array.from({ length: 12 }, (_, offset) => ({
  parsed: {
    contract_id: 'DEMO-' + String(offset + 1).padStart(3, '0'),
    party_a: '北辰示例公司',
    party_b: offset % 2 ? '长河示例机构' : '松林示例机构',
    sign_date: '2025-01-' + String(offset + 1).padStart(2, '0'),
  },
  metadata: { source: '示例合同台账.pdf', page: offset < 6 ? 2 : 3, table_index: 0, row_index: offset % 6 },
}))

export function queryExampleContracts(filters: ContractFilters, offset = 0): ContractResults {
  const matches = examples.filter(({ parsed }) =>
    (!filters.contract_id || parsed.contract_id === filters.contract_id) &&
    (!filters.party_a || parsed.party_a?.includes(filters.party_a)) &&
    (!filters.party_b || parsed.party_b?.includes(filters.party_b)) &&
    (!filters.date_range_start || (parsed.sign_date ?? '') >= filters.date_range_start) &&
    (!filters.date_range_end || (parsed.sign_date ?? '') <= filters.date_range_end),
  )
  const results = matches.slice(offset, offset + CONTRACT_PAGE_SIZE)
  const nextOffset = offset + results.length
  return {
    count: matches.length,
    returned_count: results.length,
    truncated: matches.length > results.length,
    offset,
    next_offset: nextOffset < matches.length ? nextOffset : null,
    index_revision: 'demo-v1',
    results,
  }
}
