import puppeteer from 'puppeteer-core'
import path from 'node:path'
const EXT = path.resolve(process.argv[2]), OUT = process.argv[3]
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
const results = []
const check = (n, ok, x = '') => { results.push(ok); console.log(ok ? 'PASS' : 'FAIL', n, x) }
const browser = await puppeteer.launch({ executablePath: process.env.CHROME_BIN, headless: false, userDataDir: `${OUT}/profile4`,
  args: [`--load-extension=${EXT}`, `--disable-extensions-except=${EXT}`, '--disable-features=DisableLoadExtensionCommandLineSwitch', '--no-first-run', '--window-size=1280,900'],
  ignoreDefaultArgs: ['--disable-extensions', '--enable-automation'], defaultViewport: null })
try {
  await sleep(2500)
  const sw = browser.targets().find((t) => t.type() === 'service_worker' && t.url().includes('chrome-extension://'))
  const extId = new URL(sw.url()).host; const worker = await sw.worker()
  const page = await browser.newPage(); await page.goto('http://localhost:5175/index.html'); await page.bringToFront()
  await sleep(500)
  let opened = 'ok'
  try { await worker.evaluate(() => chrome.action.openPopup()) } catch (e) { opened = e.message }
  console.log('openPopup:', opened)
  await sleep(1500)
  const targets = browser.targets().map((t) => `${t.type()} ${t.url().slice(0, 90)}`)
  console.log(targets.join('\n'))
  const pt = browser.targets().find((t) => t.url().includes('/src/popup/index.html'))
  check('native toolbar popup opened', !!pt)
  if (pt) {
    const pp = await pt.asPage()
    await pp.waitForSelector('#dev-email', { timeout: 8000 })
    const dims = await pp.evaluate(() => [document.documentElement.scrollWidth, document.documentElement.scrollHeight])
    check('popup is compact (~400x590)', dims[0] <= 420 && dims[1] <= 620, JSON.stringify(dims))
    const fits = await pp.evaluate(() => { const c = document.querySelector('.center'); return [c.scrollHeight, c.clientHeight] })
    check('sign-in fits without scrolling', fits[0] <= fits[1] + 1, JSON.stringify(fits))
    await pp.screenshot({ path: `${OUT}/p1-signin.png` })
    await (await pp.evaluateHandle(() => [...document.querySelectorAll('button')].find((b) => b.textContent.trim() === 'Go'))).click()
    await pp.waitForSelector('.composer textarea', { timeout: 10000 })
    const fits2 = await pp.evaluate(() => { const c = document.querySelector('.scroll'); return [c.scrollHeight, c.clientHeight] })
    check('empty chat starters fit without scrolling', fits2[0] <= fits2[1] + 1, JSON.stringify(fits2))
    await pp.screenshot({ path: `${OUT}/p2-chat.png` })
    check('dev sign-in inside popup', true)
    await (await pp.$('.composer textarea')).type('How long do I monitor former English learners?')
    await pp.keyboard.press('Enter')
    await pp.waitForFunction(() => document.querySelector('.msg-ai .badge, .msg-ai .err'), { timeout: 90000 })
    const a = await pp.evaluate(() => ({ cites: document.querySelectorAll('.cite').length, badge: document.querySelector('.badge')?.innerText, err: document.querySelector('.err')?.innerText }))
    console.log(JSON.stringify(a))
    check('answer with citations in popup', a.cites > 0 && !a.err)
    await pp.screenshot({ path: `${OUT}/p3-answer.png` })

    await pp.evaluate(() => document.querySelector('button[aria-label="Open larger, resizable window"]').click())
    await sleep(2000)
    const host = await page.$('#esolv-root')
    check('Expand injects floating resizable window', !!host)
    await page.screenshot({ path: `${OUT}/p4-expanded.png` })
  }
} catch (e) { console.error('ERROR', e); results.push(false) }
finally { await sleep(300); await browser.close(); console.log(results.filter(Boolean).length + '/' + results.length) }
