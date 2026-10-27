




const FRAME_KEY = 'esolv.frame.v2'
const DOCK_KEY = 'esolv.docked.v2'
const MIN_W = 290
const MIN_H = 340
const DEFAULT = { w: 344, h: 470, top: 64, right: 16 }

interface Frame { w: number; h: number; top: number; right: number }

const w = window as unknown as { __esolv?: { toggle: () => void } }

function clamp(f: Frame): Frame {
  const vw = window.innerWidth
  const vh = window.innerHeight
  const width = Math.min(Math.max(f.w, MIN_W), Math.max(MIN_W, Math.min(960, vw - 24)))
  const height = Math.min(Math.max(f.h, MIN_H), Math.max(MIN_H, vh - 24))
  return {
    w: width,
    h: height,
    top: Math.min(Math.max(f.top, 8), Math.max(8, vh - height - 8)),
    right: Math.min(Math.max(f.right, 8), Math.max(8, vw - width - 8)),
  }
}

const STYLES = `
:host { all: initial; }
.win {
  position: fixed; z-index: 2147483647; overflow: hidden; border-radius: 18px;
  background: #f8fafb; box-shadow: 0 0 0 1px rgba(31,29,26,.08), 0 24px 60px -12px rgba(20,18,15,.35), 0 8px 20px -8px rgba(20,18,15,.2);
  opacity: 0; transform: translateY(-6px) scale(.985); pointer-events: none;
  transition: opacity .16s ease, transform .2s cubic-bezier(.2,.8,.2,1);
}
.win.open { opacity: 1; transform: none; pointer-events: auto; }
.win.hidden { visibility: hidden; }
.win.docked {
  top: 0 !important; right: 0 !important; width: min(420px, 42vw) !important;
  height: 100vh !important; border-radius: 0;
  box-shadow: -1px 0 0 rgba(31,29,26,.12), -12px 0 34px rgba(20,18,15,.16);
}
.win.docked .grip { display: none; }
iframe { width: 100%; height: 100%; border: 0; display: block; background: transparent; color-scheme: light dark; }
.grip {
  position: absolute; left: 0; bottom: 0; width: 22px; height: 22px; cursor: nesw-resize; z-index: 2;
  touch-action: none; border-bottom-left-radius: 18px;
}
.grip::after {
  content: ""; position: absolute; left: 5px; bottom: 5px; width: 9px; height: 9px; opacity: .0; transition: opacity .15s;
  background: linear-gradient(45deg, transparent 45%, #9a9489 45%, #9a9489 52%, transparent 52%, transparent 70%, #9a9489 70%, #9a9489 77%, transparent 77%);
}
.win:hover .grip::after { opacity: .75; }
.grip:hover::after { opacity: 1; }
@media (prefers-color-scheme: dark) { .win { background: #161718; } }
@media (prefers-reduced-motion: reduce) { .win { transition: none; } }
`

function create() {
  const host = document.createElement('div')
  host.id = 'esolv-root'
  host.style.cssText = 'all:initial;position:fixed;top:0;left:0;width:0;height:0;z-index:2147483647'
  const shadow = host.attachShadow({ mode: 'closed' })
  const style = document.createElement('style')
  style.textContent = STYLES
  const win = document.createElement('div')
  win.className = 'win'
  win.setAttribute('role', 'dialog')
  win.setAttribute('aria-label', 'Esolv assistant')
  const iframe = document.createElement('iframe')
  iframe.src = chrome.runtime.getURL('src/panel/index.html')
  iframe.title = 'Esolv'
  iframe.allow = 'clipboard-write'
  const grip = document.createElement('div')
  grip.className = 'grip'
  grip.title = 'Drag to resize'
  win.append(iframe, grip)
  shadow.append(style, win)
  document.documentElement.appendChild(host)

  let frame: Frame = clamp(DEFAULT)
  let open = false
  let docked = false

  const apply = () => {
    win.style.width = `${frame.w}px`
    win.style.height = `${frame.h}px`
    win.style.top = `${frame.top}px`
    win.style.right = `${frame.right}px`
  }
  const persist = () => void chrome.storage.local.set({ [FRAME_KEY]: frame }).catch(() => {})
  apply()
  chrome.storage.local.get(FRAME_KEY).then((r) => {
    if (r[FRAME_KEY]) { frame = clamp(r[FRAME_KEY] as Frame); apply() }
  }).catch(() => {})
  chrome.storage.local.get(DOCK_KEY).then((r) => {
    docked = !!r[DOCK_KEY]
    win.classList.toggle('docked', docked)
  }).catch(() => {})

  const setOpen = (v: boolean) => {
    open = v
    win.classList.toggle('open', v)
    if (v) iframe.contentWindow?.postMessage({ source: 'esolv-host', type: 'opened' }, '*')
  }


  grip.addEventListener('pointerdown', (e) => {
    e.preventDefault()
    grip.setPointerCapture(e.pointerId)
    iframe.style.pointerEvents = 'none'
    const start = { x: e.clientX, y: e.clientY, f: { ...frame } }
    const move = (ev: PointerEvent) => {
      frame = clamp({ ...start.f, w: start.f.w + (start.x - ev.clientX), h: start.f.h + (ev.clientY - start.y) })
      apply()
    }
    const up = () => {
      grip.removeEventListener('pointermove', move)
      grip.removeEventListener('pointerup', up)
      grip.removeEventListener('pointercancel', up)
      iframe.style.pointerEvents = ''
      persist()
    }
    grip.addEventListener('pointermove', move)
    grip.addEventListener('pointerup', up)
    grip.addEventListener('pointercancel', up)
  })


  window.addEventListener('message', (e) => {
    if (e.source !== iframe.contentWindow || e.data?.source !== 'esolv-panel') return
    const m = e.data
    if (m.type === 'drag' && Number.isFinite(m.dx) && Number.isFinite(m.dy)) {
      frame = clamp({ ...frame, top: frame.top + m.dy, right: frame.right - m.dx })
      apply()
    } else if (m.type === 'drag-end') {
      persist()
    } else if (m.type === 'close') {
      setOpen(false)
    } else if (m.type === 'dock') {
      docked = !docked
      win.classList.toggle('docked', docked)
      void chrome.storage.local.set({ [DOCK_KEY]: docked })
      iframe.contentWindow?.postMessage({ source: 'esolv-host', type: 'dock-state', docked }, '*')
    }
  })
  window.addEventListener('resize', () => { frame = clamp(frame); apply() })

  return {
    toggle: () => setOpen(!open),
    show: () => setOpen(true),
    setVisible: (v: boolean) => win.classList.toggle('hidden', !v),
  }
}

if (!w.__esolv) {
  const ui = create()
  w.__esolv = ui
  requestAnimationFrame(() => ui.show())

  chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
    if (msg?.type === 'esolv:toggle') { ui.toggle(); sendResponse({ ok: true }) }
    else if (msg?.type === 'esolv:show') { ui.show(); sendResponse({ ok: true }) }
    else if (msg?.type === 'esolv:set-visible') { ui.setVisible(!!msg.visible); sendResponse({ ok: true }) }
    else if (msg?.type === 'esolv:page-context') {
      const sel = String(window.getSelection?.() ?? '').slice(0, 3000)
      sendResponse({ title: document.title.slice(0, 200), url: location.href.slice(0, 500), selection: sel })
    }
    return false
  })
}
