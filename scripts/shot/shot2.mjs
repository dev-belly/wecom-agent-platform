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
// 等待内嵌回测仪表盘 iframe 渲染（含 CDN 库与图表）
const qframe = q.frameLocator('iframe[title^="回测仪表盘"]')
await qframe.locator('canvas').first().waitFor({ timeout: 20000 }).catch(() => {})
await q.waitForTimeout(1800)
// QuantView 为内部滚动容器，fullPage 不生效；改截内容元素以获取完整高度（含仪表盘）
const qContent = q.locator('div.max-w-6xl')
await qContent.screenshot({ path: 'scripts/shot/shot_quant.png' })
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
