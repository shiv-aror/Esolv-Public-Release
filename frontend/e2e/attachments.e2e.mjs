
import puppeteer from 'puppeteer-core'
import path from 'node:path'
const EXT = path.resolve(process.argv[2]), OUT = process.argv[3]
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
const results = []
const check = (n, ok, x = '') => { results.push(ok); console.log(ok ? 'PASS' : 'FAIL', n, x) }
const browser = await puppeteer.launch({ executablePath: process.env.CHROME_BIN, headless: false, userDataDir: `${OUT}/profile5`,
  args: [`--load-extension=${EXT}`, `--disable-extensions-except=${EXT}`, '--disable-features=DisableLoadExtensionCommandLineSwitch', '--no-first-run', '--window-size=1280,900'],
  ignoreDefaultArgs: ['--disable-extensions', '--enable-automation'], defaultViewport: null })
try {
  await sleep(2500)
  const sw = browser.targets().find((t) => t.type() === 'service_worker' && t.url().includes('chrome-extension://'))
  const extId = new URL(sw.url()).host; const worker = await sw.worker()
  const page = await browser.newPage(); await page.goto('http://localhost:5175/index.html'); await page.bringToFront()
  await worker.evaluate(async () => { const [t] = await chrome.tabs.query({ url: 'http://localhost:5175/*' }); await __esolvToggle(t) })
  await sleep(1500)
  const frame = page.frames().find((f) => f.url().includes(`${extId}/src/panel/index.html`))
  await frame.waitForSelector('#dev-email')
  await (await frame.evaluateHandle(() => [...document.querySelectorAll('button')].find((b) => b.textContent.trim() === 'Go'))).click()
  await frame.waitForSelector('.composer textarea')

  const dropFiles = async (spec) => {
    await frame.evaluate((spec) => {
      const dt = new DataTransfer()
      for (const [name, content, type] of spec) dt.items.add(new File([content], name, { type }))
      window.__dt = dt
      window.dispatchEvent(new DragEvent('dragenter', { dataTransfer: dt, bubbles: true, cancelable: true }))
      window.dispatchEvent(new DragEvent('dragover', { dataTransfer: dt, bubbles: true, cancelable: true }))
    }, spec)
    await sleep(250)
    window_overlay = await frame.evaluate(() => !!document.querySelector('.dropzone'))
    await frame.evaluate(() => window.dispatchEvent(new DragEvent('drop', { dataTransfer: window.__dt, bubbles: true, cancelable: true })))
  }
  let window_overlay = false

  await dropFiles([['plan.txt', 'ELD plan review for Maria Santos (ID 123456) is scheduled for November 5. Accommodations: extended time and a word bank.', 'text/plain'], ['virus.exe', 'MZ....', 'application/octet-stream']])
  check('drop overlay appears while dragging', window_overlay)
  await frame.waitForSelector('.chip-file', { timeout: 5000 })
  await frame.waitForFunction(() => document.querySelector('.chip-file .fn span')?.textContent.includes('KB'), { timeout: 15000 })
  const chips = await frame.evaluate(() => [...document.querySelectorAll('.chip-file')].map((c) => c.innerText.replace(/\n/g, ' ')))
  console.log(JSON.stringify(chips))
  check('supported file shows as a chip (not sent)', chips.length === 1 && chips[0].includes('plan.txt'))
  check('unsupported file (.exe) rejected', !chips.some((c) => c.includes('virus')))
  check('dropping did NOT send a message', (await frame.$$('.msg-user')).length === 0)
  await page.screenshot({ path: `${OUT}/a1-chip.png` })

  await frame.click('.chip-file > button')
  await sleep(300)
  check('X removes the attachment', (await frame.$$('.chip-file')).length === 0)
  check('overlay disappears after drop', (await frame.$$('.dropzone')).length === 0)

  await dropFiles([['plan.txt', 'ELD plan review for Maria Santos (ID 123456) is scheduled for November 5. Accommodations: extended time and a word bank.', 'text/plain']])
  await frame.waitForFunction(() => document.querySelector('.chip-file .fn span')?.textContent.includes('KB'), { timeout: 15000 })
  await (await frame.$('.composer textarea')).type('When is the review in my attached file and what accommodations are listed?')
  await page.keyboard.press('Enter')
  await frame.waitForSelector('.msg-user .chip-file', { timeout: 5000 })
  check('sent message shows the file chip', true)
  check('composer chips cleared after send', (await frame.$$('.composer .chip-file')).length === 0)
  await frame.waitForFunction(() => document.querySelector('.msg-ai .badge, .msg-ai .err'), { timeout: 90000 })
  const a = await frame.evaluate(() => ({ text: document.querySelector('.msg-ai .prose')?.innerText.slice(0, 260), badge: document.querySelector('.badge')?.innerText, src: [...document.querySelectorAll('.source')].map((s) => s.innerText.replace(/\n/g, ' | ')), err: document.querySelector('.err')?.innerText }))
  console.log(JSON.stringify(a, null, 1))
  check('answer uses the file content', /november 5|nov/i.test(a.text || '') && /extended time|word bank/i.test(a.text || ''))
  check('file listed as a source', a.src.some((s) => s.includes('Attached: plan.txt')))
  check('answer is verified', /Checked against sources/.test(a.badge || ''))
  check('real name restored for the teacher only if used', !/Student [A-Z2-7]{4}/.test(a.text || ''))
  await page.screenshot({ path: `${OUT}/a2-answer.png` })
} catch (e) { console.error('ERROR', e); results.push(false) }
finally { await sleep(300); await browser.close(); console.log(results.filter(Boolean).length + '/' + results.length) }
