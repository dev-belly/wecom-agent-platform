import assert from 'node:assert/strict'
import test from 'node:test'
import { queryContracts, queryExampleContracts } from '../src/api/contracts.ts'

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
