
import { googleFlow } from '../lib/auth'
import { saveSession } from '../lib/api'
import launcherFile from '../content/launcher?script'

const PANEL_PATH = 'src/panel/index.html'

function injectable(url?: string): boolean {
  if (!url) return false
  if (!/^https?:/i.test(url)) return false
  return !/^https:\/\/(chromewebstore\.google\.com|chrome\.google\.com\/webstore)/i.test(url)
}

async function activeTab(): Promise<chrome.tabs.Tab | undefined> {
  const [tab] = await chrome.tabs.query({ active: true, lastFocusedWindow: true })
  return tab
}


async function openPopoutWindow() {
  const { esolvWindowId } = (await chrome.storage.session.get('esolvWindowId')) as { esolvWindowId?: number }
  if (esolvWindowId) {
    try {
      await chrome.windows.update(esolvWindowId, { focused: true })
      return
    } catch {

    }
  }
  const w = await chrome.windows.create({ url: chrome.runtime.getURL(`${PANEL_PATH}?mode=window`), type: 'popup', width: 440, height: 700 })
  if (w?.id) await chrome.storage.session.set({ esolvWindowId: w.id })
}


async function openPanelTab() {
  await chrome.tabs.create({ url: chrome.runtime.getURL(PANEL_PATH) })
}


async function toggle(tab: chrome.tabs.Tab) {
  if (!tab.id || !injectable(tab.url)) return openPanelTab()
  try {
    await chrome.tabs.sendMessage(tab.id, { type: 'esolv:toggle' })
    return
  } catch {

  }
  try {
    await chrome.scripting.executeScript({ target: { tabId: tab.id }, files: [launcherFile] })
  } catch (error) {
    console.warn('Esolv could not open on this page:', error)
    await openPanelTab()
  }
}

async function showOnPage(tab: chrome.tabs.Tab) {
  if (!tab.id || !injectable(tab.url)) return
  try {
    await chrome.tabs.sendMessage(tab.id, { type: 'esolv:show' })
    return
  } catch {

  }
  await chrome.scripting.executeScript({ target: { tabId: tab.id }, files: [launcherFile] })
}

async function readPageContext(tabId: number) {
  const [res] = await chrome.scripting.executeScript({
    target: { tabId },
    func: () => ({
      title: document.title.slice(0, 200),
      url: location.href.slice(0, 500),
      selection: String(window.getSelection?.() ?? '').slice(0, 3000),
    }),
  })
  return res?.result ?? null
}

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  switch (msg?.type) {
    case 'esolv:open-here': {
      if (!sender.tab?.url?.startsWith('https://mcpsmd.instructure.com/')) {
        sendResponse({ ok: false })
        return false
      }
      void showOnPage(sender.tab).then(() => sendResponse({ ok: true })).catch(() => sendResponse({ ok: false }))
      return true
    }
    case 'esolv:expand': {
      void (async () => {
        const tab = await activeTab()
        if (tab) await toggle(tab)
        sendResponse({ ok: true })
      })()
      return true
    }
    case 'esolv:popout': {
      void openPopoutWindow().then(() => sendResponse({ ok: true }))
      return true
    }
    case 'esolv:page-context-active': {
      void (async () => {
        try {
          const tab = await activeTab()
          sendResponse(tab?.id && injectable(tab.url) ? await readPageContext(tab.id) : null)
        } catch {
          sendResponse(null)
        }
      })()
      return true
    }
    case 'esolv:capture': {
      void (async () => {

        const inPage = sender.tab
        const tab = inPage ?? (await activeTab())
        if (!tab?.id || tab.windowId === undefined) return sendResponse({ dataUrl: null })
        try {

          if (inPage) {
            await chrome.tabs.sendMessage(tab.id, { type: 'esolv:set-visible', visible: false })
            await new Promise((r) => setTimeout(r, 140))
          }
          sendResponse({ dataUrl: await chrome.tabs.captureVisibleTab(tab.windowId, { format: 'jpeg', quality: 82 }) })
        } catch {
          sendResponse({ dataUrl: null })
        } finally {
          if (inPage) {
            try {
              await chrome.tabs.sendMessage(tab.id, { type: 'esolv:set-visible', visible: true })
            } catch {

            }
          }
        }
      })()
      return true
    }
    case 'esolv:google-signin': {
      void (async () => {
        try {
          const session = await googleFlow(msg.cfg)
          await saveSession(session)
          sendResponse({ session })
        } catch (e) {
          sendResponse({ error: (e as Error).message })
        }
      })()
      return true
    }
  }
  return false
})

chrome.runtime.onInstalled.addListener((d) => {
  if (d.reason === 'install') void chrome.tabs.create({ url: chrome.runtime.getURL('src/pages/privacy.html') })
})



chrome.action.onClicked.addListener((tab) => { void toggle(tab) })


;(globalThis as unknown as { __esolvToggle: typeof toggle }).__esolvToggle = toggle
