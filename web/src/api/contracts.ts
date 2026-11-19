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
  results: ContractRow[]
}

export async function queryContracts(
  baseUrl: string, apiKey: string, filters: ContractFilters, signal: AbortSignal,
): Promise<ContractResults> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (apiKey.trim()) headers.Authorization = 'Bearer ' + apiKey.trim()
  const response = await fetch(baseUrl.replace(/\/+$/, '') + '/api/contracts/query', {
    method: 'POST', headers, body: JSON.stringify(filters), signal,
  })
  const data = await response.json().catch(() => null)
  if (!response.ok) {
    const detail = typeof data?.detail === 'string' ? ' · ' + data.detail.slice(0, 160) : ''
    throw new Error('查询失败（HTTP ' + response.status + '）' + detail)
  }
  if (!data || !Number.isInteger(data.count) || !Array.isArray(data.results)
      || data.returned_count !== data.results.length || data.count < data.returned_count
      || data.truncated !== (data.count > data.returned_count)
      || data.results.some((row: ContractRow) => !row?.parsed || !row.metadata)) {
    throw new Error('合同查询返回格式无效')
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

export function queryExampleContracts(filters: ContractFilters): ContractResults {
  const matches = examples.filter(({ parsed }) =>
    (!filters.contract_id || parsed.contract_id === filters.contract_id) &&
    (!filters.party_a || parsed.party_a?.includes(filters.party_a)) &&
    (!filters.party_b || parsed.party_b?.includes(filters.party_b)) &&
    (!filters.date_range_start || (parsed.sign_date ?? '') >= filters.date_range_start) &&
    (!filters.date_range_end || (parsed.sign_date ?? '') <= filters.date_range_end),
  )
  const results = matches.slice(0, 10)
  return { count: matches.length, returned_count: results.length, truncated: matches.length > 10, results }
}
