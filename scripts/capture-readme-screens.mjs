/**
 * Capture README screenshots for ai-travel-helper.
 * Needs: Vite :5174 proxying to travel backend :8001
 */
import { chromium } from 'playwright'
import path from 'path'
import fs from 'fs'
import { fileURLToPath } from 'url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const OUT = path.join(__dirname, '..', 'docs', 'screenshots')
const BASE = 'http://127.0.0.1:5174'

async function shot(page, name) {
  const file = path.join(OUT, name)
  await page.screenshot({ path: file, fullPage: false })
  console.log('saved', file)
}

async function main() {
  fs.mkdirSync(OUT, { recursive: true })
  const browser = await chromium.launch({ headless: true })
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })
  page.setDefaultTimeout(240000)

  await page.goto(BASE, { waitUntil: 'networkidle' })
  await page.waitForTimeout(800)
  await shot(page, '01-empty.png')

  await page.fill('input[placeholder*="北京"]', '杭州')
  await page.fill('input[type="number"]', '3')
  await page.getByRole('button', { name: '美食' }).click()
  await page.getByRole('button', { name: '自然风光' }).click()
  await page.waitForTimeout(400)
  await shot(page, '02-form-ready.png')

  await page.getByRole('button', { name: '生成行程' }).click()

  await page.waitForSelector('text=执行状态', { timeout: 60000 })
  await page.waitForTimeout(1500)
  await shot(page, '03-generating-flow.png')

  await page.waitForSelector('text=工具调用', { timeout: 120000 })
  const toolsBtn = page.locator('button', { hasText: '工具调用' })
  await toolsBtn.first().click()
  await page.waitForTimeout(800)
  await shot(page, '04-tools.png')

  await page.waitForSelector('text=天行程', { timeout: 180000 })
  // wait until flow reaches 完成 or markdown has enough content
  try {
    await page.waitForFunction(
      () => {
        const t = document.body.innerText
        return t.includes('完成') && (t.includes('导出 PDF') || t.includes('继续修改') || t.includes('Day'))
      },
      { timeout: 120000 },
    )
  } catch (_) {
    console.log('did not reach fully done; capturing near-final')
  }
  await page.waitForTimeout(2500)
  await shot(page, '05-result.png')

  await page.locator('text=地图与路线规划').scrollIntoViewIfNeeded()
  await page.waitForTimeout(3000)
  await shot(page, '06-map.png')

  await browser.close()
  console.log('done')
}

main().catch((e) => {
  console.error(e)
  process.exit(1)
})
