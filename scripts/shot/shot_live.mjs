import { chromium } from 'playwright-core'

const CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
const URL = 'https://dev-belly.github.io/wecom-agent-platform/'
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

const browser = await chromium.launch({
  executablePath: CHROME,
  headless: true,
  args: ['--no-sandbox', '--disable-gpu'],
})

// 直接渲染线上站点，验证部署真实可用
const q = await browser.newPage({
  viewport: { width: 1480, height: 1000 },
  deviceScaleFactor: 2,
})
await q.goto(URL, { waitUntil: 'networkidle' })
await sleep(800)
await q.getByRole('button', { name: '量化分析' }).click()
await sleep(900)
const qframe = q.frameLocator('iframe[title^="回测仪表盘"]')
await qframe.locator('canvas').first().waitFor({ timeout: 20000 }).catch(() => {})
await q.waitForTimeout(1800)
const content = q.locator('div.max-w-6xl')
await content.screenshot({ path: 'scripts/shot/shot_live.png' })
console.log('saved shot_live.png (live site render)')
await browser.close()
