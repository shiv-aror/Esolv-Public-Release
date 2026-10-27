
export const isExtension = typeof chrome !== 'undefined' && !!chrome.runtime?.id
export const inFrame = typeof window !== 'undefined' && window.parent !== window
export const isPopup = location.pathname.includes('/popup/')
export const isWindowMode = new URLSearchParams(location.search).get('mode') === 'window'

type Area = 'local' | 'session'

function fallbackStore(area: Area): Storage {
  return area === 'local' ? localStorage : sessionStorage
}

async function get<T>(area: Area, key: string): Promise<T | undefined> {
  try {
    if (isExtension && chrome.storage?.[area]) {
      const r = await chrome.storage[area].get(key)
      return r[key] as T | undefined
    }
    const raw = fallbackStore(area).getItem(`esolv:${key}`)
    return raw ? (JSON.parse(raw) as T) : undefined
  } catch {
    return undefined
  }
}

async function set(area: Area, key: string, value: unknown): Promise<void> {
  try {
    if (isExtension && chrome.storage?.[area]) await chrome.storage[area].set({ [key]: value })
    else fallbackStore(area).setItem(`esolv:${key}`, JSON.stringify(value))
  } catch {

  }
}

async function remove(area: Area, key: string): Promise<void> {
  try {
    if (isExtension && chrome.storage?.[area]) await chrome.storage[area].remove(key)
    else fallbackStore(area).removeItem(`esolv:${key}`)
  } catch {

  }
}

export const store = {
  local: {
    get: <T,>(k: string) => get<T>('local', k),
    set: (k: string, v: unknown) => set('local', k, v),
    remove: (k: string) => remove('local', k),
  },
  session: {
    get: <T,>(k: string) => get<T>('session', k),
    set: (k: string, v: unknown) => set('session', k, v),
    remove: (k: string) => remove('session', k),
  },
}

export function openUrl(url: string): void {
  if (isExtension && chrome.tabs?.create) void chrome.tabs.create({ url })
  else window.open(url, '_blank', 'noopener,noreferrer')
}

export function extensionPage(path: string): string {
  return isExtension ? chrome.runtime.getURL(path) : `/${path}`
}


export function postToHost(msg: Record<string, unknown>): void {
  if (inFrame) window.parent.postMessage({ source: 'esolv-panel', ...msg }, '*')
}

export async function activeTabContext(): Promise<{ title: string; url: string; selection: string } | null> {
  if (!isExtension) return { title: 'Sample page (dev preview)', url: 'https://example.com', selection: '' }
  if (isPopup) {
    try {
      return (await chrome.runtime.sendMessage({ type: 'esolv:page-context-active' })) ?? null
    } catch {
      return null
    }
  }
  if (isWindowMode || !inFrame) return null
  try {
    const [tab] = await chrome.tabs.query({ active: true, lastFocusedWindow: true })
    if (!tab?.id) return null
    return (await chrome.tabs.sendMessage(tab.id, { type: 'esolv:page-context' })) ?? null
  } catch {
    return null
  }
}

export async function captureTab(): Promise<string | null> {
  if (!isExtension) return null
  const r = await chrome.runtime.sendMessage({ type: 'esolv:capture' })
  return r?.dataUrl ?? null
}
