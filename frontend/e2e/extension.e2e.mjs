import puppeteer from 'puppeteer-core'
import path from 'node:path'
const EXT = path.resolve(process.argv[2]), OUT = process.argv[3]
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
const results = []
const check = (name, ok, extra = '') => { results.push([name, ok]); console.log(ok ? 'PASS' : 'FAIL', name, extra) }
const browser = await puppeteer.launch({
  executablePath: process.env.CHROME_BIN, headless: false, userDataDir: `${OUT}/profile2`,
  args: [`--load-extension=${EXT}`, `--disable-extensions-except=${EXT}`, '--disable-features=DisableLoadExtensionCommandLineSwitch', '--no-first-run', '--window-size=1280,900'],
  ignoreDefaultArgs: ['--disable-extensions', '--enable-automation'], defaultViewport: null,
})
try {
  await sleep(2500)
  const sw = browser.targets().find((t) => t.type() === 'service_worker' && t.url().includes('chrome-extension://'))
  const extId = new URL(sw.url()).host
  const worker = await sw.worker()
  const page = await browser.newPage()
  await page.goto('http://localhost:5175/index.html')
  await page.bringToFront()
  await worker.evaluate(async () => { const [t] = await chrome.tabs.query({ url: 'http://localhost:5175/*' }); await __esolvToggle(t) })
  await sleep(1500)
  const frame = page.frames().find((f) => f.url().includes(`${extId}/src/panel/index.html`))
  check('panel iframe loaded from extension origin', !!frame)


  await frame.waitForSelector('#dev-email')
  const goBtn = await frame.evaluateHandle(() => [...document.querySelectorAll('button')].find((b) => b.textContent.trim() === 'Go'))
  await goBtn.click()
  await frame.waitForSelector('.composer textarea', { timeout: 10000 })
  check('dev sign-in reaches chat', true)
  const session = await frame.evaluate(() => chrome.storage.session.get('session').then((r) => !!r.session))
  check('session stored in chrome.storage.session', session)


  const iframeEl = await frame.frameElement()
  const b0 = await iframeEl.boundingBox()
  await page.mouse.move(b0.x + 8, b0.y + b0.height - 8)
  await page.mouse.down()
  await page.mouse.move(b0.x - 150, b0.y + b0.height + 40, { steps: 8 })
  await page.mouse.up()
  await sleep(700)
  const b1 = await iframeEl.boundingBox()
  check('bottom-left drag enlarges window', b1.width > b0.width + 100 && b1.height > b0.height + 20, `${Math.round(b0.width)}x${Math.round(b0.height)} -> ${Math.round(b1.width)}x${Math.round(b1.height)}`)
  check('right/top edges stay anchored', Math.abs((b1.x + b1.width) - (b0.x + b0.width)) < 2 && Math.abs(b1.y - b0.y) < 2)


  await page.mouse.move(b1.x + 120, b1.y + 26)
  await page.mouse.down()
  await page.mouse.move(b1.x - 100, b1.y + 86, { steps: 8 })
  await page.mouse.up()
  const b2 = await iframeEl.boundingBox()
  check('header drag moves window', b2.x < b1.x - 80 && b2.y > b1.y + 30, `dx=${Math.round(b2.x - b1.x)} dy=${Math.round(b2.y - b1.y)}`)


  await page.evaluate(() => { const r = document.createRange(); r.selectNodeContents(document.getElementById('p')); const s = getSelection(); s.removeAllRanges(); s.addRange(r) })
  await frame.evaluate(() => { [...document.querySelectorAll('button')].find((b) => b.textContent.includes('This page'))?.click() })
  const ta = await frame.$('.composer textarea')
  await ta.type('Using this page as context, when is ELD paperwork due after enrollment?')
  await page.keyboard.press('Enter')
  const pageTag = await frame.waitForSelector('.page-tag', { timeout: 15000 }).then(() => true).catch(() => false)
  check('"This page" context attached to message', pageTag)
  await frame.waitForSelector('.msg-ai .prose', { timeout: 90000 })
  await frame.waitForFunction(() => document.querySelector('.msg-ai .badge, .msg-ai .err'), { timeout: 90000 })
  const ans = await frame.evaluate(() => ({ text: document.querySelector('.msg-ai .prose')?.innerText.slice(0, 200), cites: document.querySelectorAll('.cite').length, badge: document.querySelector('.badge')?.innerText, err: document.querySelector('.err')?.innerText }))
  console.log(JSON.stringify(ans))
  check('answer rendered with citation chips + badge', ans.cites > 0 && !!ans.badge && !ans.err)
  await page.screenshot({ path: `${OUT}/02-chat.png` })


  await frame.evaluate(() => { [...document.querySelectorAll('button')].find((b) => b.getAttribute('aria-label')?.startsWith('Attach'))?.click() })
  await sleep(300)
  await frame.evaluate(() => { [...document.querySelectorAll('.pop-menu button')].find((b) => b.textContent.includes('Capture'))?.click() })
  await frame.waitForSelector('.scrim .btn.primary', { timeout: 5000 })
  await frame.click('.scrim .btn.primary')
  const thumb = await frame.waitForSelector('.thumb img', { timeout: 10000 }).then(() => true).catch(() => false)
  check('tab screenshot captured and attached', thumb)
  const panelHidden = thumb && (await frame.evaluate(() => document.querySelector('.thumb img').src.length)) > 5000
  check('screenshot has real image data', panelHidden)
  if (thumb) {
    await (await frame.$('.composer textarea')).type('What heading is on the page in the screenshot?')
    await page.keyboard.press('Enter')
    await frame.waitForFunction(() => document.querySelectorAll('.msg-ai').length >= 2 && !document.querySelector('.msg-ai:last-child .status-line') && document.querySelector('.msg-ai:last-child .prose'), { timeout: 90000 })
    await sleep(3000)
    const t2 = await frame.evaluate(() => document.querySelector('.msg-ai:last-child .prose')?.innerText.slice(0, 160))
    console.log('vision answer:', t2)
    check('model answered about the screenshot', /ELD|MCPS|Resources/i.test(t2 || ''))
  }
  await page.screenshot({ path: `${OUT}/03-vision.png` })


  await frame.evaluate(() => document.querySelector('button[aria-label="Close Esolv"]').click())
  await sleep(500)
  await worker.evaluate(async () => { const [t] = await chrome.tabs.query({ url: 'http://localhost:5175/*' }); await __esolvToggle(t) })
  await sleep(600)
  const b3 = await iframeEl.boundingBox()
  check('close then icon-toggle reopens (size kept)', b3 && Math.abs(b3.width - b2.width) < 2)


  const cpage = await browser.newPage()
  await cpage.goto('chrome://version')
  await worker.evaluate(async () => { const [t] = await chrome.tabs.query({ url: 'chrome://version/*' }); await __esolvToggle(t) })
  await sleep(1500)
  const fallbackTab = browser.targets().find((t) => t.url() === `chrome-extension://${extId}/src/panel/index.html`)
  check('chrome:// page falls back to a regular tab', !!fallbackTab)
} catch (e) { console.error('ERROR', e); results.push(['no exception', false]) }
finally {
  await sleep(500); await browser.close()
  const failed = results.filter((r) => !r[1]).length
  console.log(`\n${results.length - failed}/${results.length} checks passed`)
  process.exitCode = failed ? 1 : 0
}
