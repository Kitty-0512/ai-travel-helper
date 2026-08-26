import { chromium } from 'playwright'
import path from 'path'
import fs from 'fs'
import { fileURLToPath } from 'url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const OUT = path.join(__dirname, '..', 'docs', 'screenshots')
const BASE = 'http://127.0.0.1:5174'
const STORAGE_KEY = 'ai_travel_helper_user_id'
const DEMO_USER_ID = 'demo'

async function shot(page, name) {
  const file = path.join(OUT, name)
  await page.screenshot({ path: file, fullPage: false })
  console.log('saved', file)
}

async function openHistorySession(page) {
  await page.waitForTimeout(2500)
  const historyCard = page.locator('[class*="cursor-pointer"]').first()
  if (await historyCard.count()) {
    await historyCard.click().catch(() => {})
    await page.waitForTimeout(4000)
    return true
  }
  return false
}

async function clickFirstMarker(page) {
  const selectors = ['.amap-marker', '.amap-overlays [title]', '.amap-icon img']
  for (const selector of selectors) {
    const loc = page.locator(selector).first()
    if (await loc.count()) {
      await loc.click({ force: true }).catch(() => {})
      await page.waitForTimeout(1500)
      return true
    }
  }
  return false
}

async function main() {
  fs.mkdirSync(OUT, { recursive: true })
  const browser = await chromium.launch({ headless: true })
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })
  page.setDefaultTimeout(180000)

  await page.addInitScript(
    ({ key, userId }) => {
      window.localStorage.setItem(key, userId)
    },
    { key: STORAGE_KEY, userId: DEMO_USER_ID },
  )

  await page.goto(BASE, { waitUntil: 'networkidle' })
  await page.waitForTimeout(2000)
  await openHistorySession(page)

  await page.locator('text=地图与路线规划').scrollIntoViewIfNeeded()
  await page.waitForTimeout(2500)

  await page.getByText('最短路径').click().catch(() => {})
  await page.waitForTimeout(2500)
  await shot(page, '11-shortest-route.png')

  const opened = await clickFirstMarker(page)
  if (!opened) console.log('marker popup not opened')
  await shot(page, '12-poi-popup.png')

  await browser.close()
  console.log('done')
}

main().catch((e) => {
  console.error(e)
  process.exit(1)
})
