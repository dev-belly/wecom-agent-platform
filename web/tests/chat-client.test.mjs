import assert from 'node:assert/strict'
import test from 'node:test'
import { sendToBackend } from '../src/api/client.ts'

test('live request sends its abort signal and key only to the selected backend', async () => {
  const originalFetch = globalThis.fetch
  const controller = new AbortController()
  let requestedUrl = ''
  globalThis.fetch = async (url, options) => {
    requestedUrl = url
    assert.equal(options.signal, controller.signal)
    assert.equal(options.headers.Authorization, 'Bearer secret')
    assert.deepEqual(JSON.parse(options.body), { message: 'hello' })
    return Response.json({
      reply: 'answer', trace_id: 'trace-1', intent: 'risk_query',
      latency_ms: 12, tool_used: 'risk_query',
    })
  }
  try {
    const reply = await sendToBackend('http://127.0.0.1:9000/', 'hello', 'secret', controller.signal)
    assert.equal(requestedUrl, 'http://127.0.0.1:9000/api/chat')
    assert.equal(reply.content, 'answer')
  } finally {
    globalThis.fetch = originalFetch
  }
})

test('switching modes can abort an outstanding live request', async () => {
  const originalFetch = globalThis.fetch
  const controller = new AbortController()
  globalThis.fetch = (_url, options) => new Promise((_resolve, reject) => {
    options.signal.addEventListener('abort', () => {
      reject(new DOMException('Aborted', 'AbortError'))
    }, { once: true })
  })
  try {
    const pending = sendToBackend('http://127.0.0.1:9000', 'hello', '', controller.signal)
    controller.abort()
    await assert.rejects(pending, { name: 'AbortError' })
  } finally {
    globalThis.fetch = originalFetch
  }
})

test('a valid reply remains readable when optional trace fields are malformed', async (t) => {
  t.mock.method(globalThis, 'fetch', async () => Response.json({
    reply: '合同 001', intent: { name: 'contract_query' }, tool_used: ['contract_query'], latency_ms: '12',
  }))
  const reply = await sendToBackend('https://example.test', '查询合同', '')
  assert.equal(reply.content, '合同 001')
  assert.deepEqual(reply.trace, { intent: '', tool: '', latencyMs: 0, params: {}, retrieved: [] })
})

test('backend requests normalize a service path and report unavailable hosts', async (t) => {
  const fetch = t.mock.method(globalThis, 'fetch', async (url) => {
    assert.equal(url, 'https://example.test/service/api/chat')
    throw new TypeError('Failed to fetch')
  })
  await assert.rejects(sendToBackend(' https://example.test/service/ ', 'hello', ''), /无法连接后端/)
  await assert.rejects(sendToBackend('https://example.test/?wrong=1', 'hello', ''), /后端地址须使用/)
  assert.equal(fetch.mock.callCount(), 1)
})
