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
