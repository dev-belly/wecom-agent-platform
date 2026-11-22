import assert from 'node:assert/strict'
import test from 'node:test'
import { ContractQueryError, queryContracts, queryExampleContracts } from '../src/api/contracts.ts'

test('example filtering preserves exact IDs, inclusive dates, and total coverage', () => {
  const all = queryExampleContracts({})
  assert.equal(all.count, 12)
  assert.equal(all.returned_count, 10)
  assert.equal(all.truncated, true)
  const day = queryExampleContracts({ date_range_start: '2025-01-02', date_range_end: '2025-01-02' })
  assert.equal(day.results[0].parsed.contract_id, 'DEMO-002')
  assert.equal(day.count, 1)
  assert.equal(queryExampleContracts({ contract_id: 'DEMO-00' }).count, 0)
})

test('demo pages reach the last two contracts and retain source locations', () => {
  const first = queryExampleContracts({})
  assert.equal(first.next_offset, 10)
  const last = queryExampleContracts({}, first.next_offset)
  assert.equal(last.count, 12)
  assert.equal(last.offset, 10)
  assert.equal(last.index_revision, first.index_revision)
  assert.equal(last.next_offset, null)
  assert.deepEqual(last.results.map((row) => row.parsed.contract_id), ['DEMO-011', 'DEMO-012'])
  assert.deepEqual(last.results.map((row) => row.metadata.page), [3, 3])
})

test('live lookup uses the deterministic contract API and forwards cancellation', async (t) => {
  const controller = new AbortController()
  t.mock.method(globalThis, 'fetch', async (url, options) => {
    assert.equal(url, 'https://example.test/api/contracts/query')
    assert.equal(options.method, 'POST')
    assert.equal(options.headers.Authorization, 'Bearer example')
    assert.deepEqual(JSON.parse(options.body), { contract_id: '001' })
    assert.equal(options.signal, controller.signal)
    return Response.json({ count: 0, returned_count: 0, truncated: false, results: [] })
  })
  assert.equal((await queryContracts('https://example.test/', ' example ', { contract_id: '001' }, controller.signal)).count, 0)
})

test('live pages preserve the submitted filters and pin the index revision', async (t) => {
  const filters = { party_a: '示例' }
  const signal = new AbortController().signal
  const page = { offset: 10, index_revision: 'stored-revision' }
  const last = queryExampleContracts({}, 10)
  let response = { ...last, index_revision: page.index_revision }
  t.mock.method(globalThis, 'fetch', async (url, options) => {
    const endpoint = new URL(url)
    assert.equal(endpoint.pathname, '/api/contracts/query')
    assert.deepEqual(Object.fromEntries(endpoint.searchParams), { offset: '10', index_revision: 'stored-revision' })
    assert.deepEqual(JSON.parse(options.body), filters)
    assert.equal(options.signal, signal)
    return Response.json(response)
  })
  const request = () => queryContracts('https://example.test', 'example', filters, signal, page)
  assert.deepEqual(await request(), response)
  response = { ...response, offset: 0 }
  await assert.rejects(request, /页码或索引版本无效/)
  response = { ...last, index_revision: 'different-revision' }
  await assert.rejects(request, /页码或索引版本无效/)
})

test('the first page remains readable against a backend without pagination', async (t) => {
  const { count, returned_count, truncated, results } = queryExampleContracts({})
  t.mock.method(globalThis, 'fetch', async () =>
    Response.json({ count, returned_count, truncated, results, index_revision: 'old-revision' }))
  const legacy = await queryContracts('https://example.test', '', {}, new AbortController().signal)
  assert.equal(legacy.count, 12)
  assert.equal(legacy.returned_count, 10)
  assert.equal(legacy.next_offset, null)
  assert.equal(legacy.index_revision, null)
})

test('a rebuilt index surfaces a conflict that the browser can reset', async (t) => {
  t.mock.method(globalThis, 'fetch', async () =>
    Response.json({ detail: '文档索引已更新，请重新查询第一页' }, { status: 409 }))
  await assert.rejects(
    queryContracts('https://example.test', '', {}, new AbortController().signal, {
      offset: 10, index_revision: 'previous-revision',
    }),
    (error) => error instanceof ContractQueryError && error.status === 409 && /重新查询第一页/.test(error.message),
  )
})

test('malformed nested contract fields return an error before rendering', async (t) => {
  let row
  t.mock.method(globalThis, 'fetch', async () => Response.json({
    count: 1, returned_count: 1, truncated: false, results: [row],
  }))
  for (const malformed of [
    { parsed: { contract_id: { text: '001' } }, metadata: { page: 1 } },
    { parsed: { contract_id: '001' }, metadata: { source: ['report.pdf'] } },
    { parsed: { contract_id: '001' }, metadata: { row_index: '2' } },
    { parsed: [], metadata: {} },
  ]) {
    row = malformed
    await assert.rejects(
      queryContracts('https://example.test', '', {}, new AbortController().signal),
      /合同查询返回格式无效/,
    )
  }
  row = { parsed: { contract_id: '001', sign_date: null }, metadata: { page: null, table_index: 0 } }
  const valid = await queryContracts('https://example.test', '', {}, new AbortController().signal)
  assert.deepEqual(valid.results, [row])
})
