import { chromium } from 'playwright-core'

const CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
const URL = 'http://localhost:8123/wecom-agent-platform/'
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

const browser = await chromium.launch({
  executablePath: CHROME,
  headless: true,
  args: ['--no-sandbox', '--disable-gpu'],
})

// ── 1) 量化分析视图（全页）──────────────────────────
const q = await browser.newPage({
  viewport: { width: 1480, height: 1000 },
  deviceScaleFactor: 2,
})
await q.goto(URL, { waitUntil: 'networkidle' })
await sleep(700)
await q.getByRole('button', { name: '量化分析' }).click()
await sleep(900)
await q.screenshot({ path: 'scripts/shot/shot_quant.png', fullPage: true })
console.log('saved shot_quant.png')
await q.close()

// ── 2) 对话视图（因子查询）──────────────────────────
const c = await browser.newPage({
  viewport: { width: 1440, height: 900 },
  deviceScaleFactor: 2,
})
await c.goto(URL, { waitUntil: 'networkidle' })
await sleep(700)
const ta = c.locator('textarea')
await ta.fill('星辰科技 688001.SH 的风险因子')
await ta.press('Enter')
await sleep(1700)
// 展开工具追踪
const expandBtn = c.getByRole('button', { name: /工具调用追踪/ })
const label = await expandBtn.first().innerText().catch(() => '')
if (label.includes('展开')) await expandBtn.first().click()
await sleep(400)
await c.screenshot({ path: 'scripts/shot/shot_chat.png' })
console.log('saved shot_chat.png')
await c.close()

await browser.close()
