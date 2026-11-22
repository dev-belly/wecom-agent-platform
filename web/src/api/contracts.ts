import { backendErrorDetail, isRecord, postBackend } from './backend.ts'

export interface ContractFilters {
  contract_id?: string
  party_a?: string
  party_b?: string
  date_range_start?: string
  date_range_end?: string
}

export interface ContractRow {
  parsed: { contract_id?: string | null; party_a?: string | null; party_b?: string | null; sign_date?: string | null }
  metadata: { source?: string | null; page?: number | null; table_index?: number | null; row_index?: number | null }
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

function isContractRow(row: unknown): row is ContractRow {
  if (!isRecord(row) || !isRecord(row.parsed) || !isRecord(row.metadata)) return false
  const { contract_id, party_a, party_b, sign_date } = row.parsed
  const { source, page, table_index, row_index } = row.metadata
  return [contract_id, party_a, party_b, sign_date, source].every(
    (value) => value == null || typeof value === 'string',
  ) && [page, table_index, row_index].every(
    (value) => value == null || (typeof value === 'number' && Number.isSafeInteger(value) && value >= 0),
  )
}

export async function queryContracts(
  baseUrl: string, apiKey: string, filters: ContractFilters, signal: AbortSignal, page?: ContractPage,
): Promise<ContractResults> {
  const pagination = page ? '?' + new URLSearchParams({
    offset: String(page.offset), index_revision: page.index_revision,
  }) : ''
  const response = await postBackend(baseUrl, '/api/contracts/query' + pagination, apiKey, filters, signal)
  const data: unknown = await response.json().catch(() => null)
  if (!response.ok) {
    const detail = backendErrorDetail(data)
    throw new ContractQueryError(response.status, detail ? ' · ' + detail : '')
  }
  if (!isRecord(data)) throw new Error('合同查询返回格式无效')
  const { count, returned_count, truncated, results } = data
  if (typeof count !== 'number' || !Number.isSafeInteger(count) || !Array.isArray(results)
      || returned_count !== results.length || count < returned_count
      || truncated !== (count > returned_count) || !results.every(isContractRow)) {
    throw new Error('合同查询返回格式无效')
  }
  const result = { ...data, count, returned_count, truncated, results }
  if (!page && data.offset === undefined && data.next_offset === undefined) {
    return { ...result, offset: 0, next_offset: null, index_revision: null }
  }
  const offset = page?.offset ?? 0
  const countOnPage = Math.max(0, Math.min(CONTRACT_PAGE_SIZE, count - offset))
  const nextOffset = offset + countOnPage < count ? offset + countOnPage : null
  if (data.offset !== offset || data.next_offset !== nextOffset || data.returned_count !== countOnPage
      || typeof data.index_revision !== 'string' || !data.index_revision
      || (page && data.index_revision !== page.index_revision)) {
    throw new Error('合同查询返回的页码或索引版本无效，请重新查询。')
  }
  return { ...result, offset, next_offset: nextOffset, index_revision: data.index_revision }
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
