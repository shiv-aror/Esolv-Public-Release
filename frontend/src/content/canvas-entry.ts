
export {}

if (!document.getElementById('esolv-canvas-entry')) {
  const host = document.createElement('div')
  host.id = 'esolv-canvas-entry'
  host.style.cssText = 'all:initial;position:fixed;right:18px;top:16px;z-index:2147483646'
  const shadow = host.attachShadow({ mode: 'closed' })
  const style = document.createElement('style')
  style.textContent = `
    :host { all: initial; }
    button { display: flex; align-items: center; gap: 8px; min-height: 38px; padding: 0 14px 0 9px;
      border: 1px solid rgba(255,255,255,.18); border-radius: 999px; background: #183c55; color: white;
      box-shadow: 0 5px 18px rgba(12,31,45,.24); cursor: pointer; font: 600 13px/1 system-ui, sans-serif; }
    button:hover { background: #235776; box-shadow: 0 7px 22px rgba(12,31,45,.3); }
    button:focus-visible { outline: 3px solid #73b7db; outline-offset: 3px; }
    img { display: block; width: 22px; height: 22px; object-fit: contain; border-radius: 5px; background: white; }
  `
  const button = document.createElement('button')
  button.type = 'button'
  button.setAttribute('aria-label', 'Open Esolv on this Canvas page')
  button.title = 'Open Esolv on this Canvas page'
  const icon = document.createElement('img')
  icon.src = chrome.runtime.getURL('src/icons/esolv-logo.png')
  icon.alt = ''
  button.append(icon, document.createTextNode('Esolv'))
  button.addEventListener('click', () => {
    void chrome.runtime.sendMessage({ type: 'esolv:open-here' })
  })
  shadow.append(style, button)
  document.documentElement.appendChild(host)
}
