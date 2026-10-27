import { SseParser } from './sse'
import { store } from './platform'
import type { CanvasStatus, Citation, ServerConfig, Session, Verification } from './types'

export const DEFAULT_BACKEND = 'http://localhost:8000'

export async function backendUrl(): Promise<string> {
  return ((await store.local.get<string>('backendUrl')) || DEFAULT_BACKEND).replace(/\/+$/, '')
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message)
  }
}

let unauthorizedHandler: (() => void) | null = null
export function onUnauthorized(fn: () => void) {
  unauthorizedHandler = fn
}

export async function getSession(): Promise<Session | null> {
  const s = await store.session.get<Session>('session')
  if (!s) return null
  if (s.expires_at * 1000 < Date.now()) {
    await store.session.remove('session')
    return null
  }
  return s
}

export async function saveSession(s: Session | null) {
  if (s) await store.session.set('session', s)
  else await store.session.remove('session')
}

async function errorMessage(r: Response): Promise<string> {
  try {
    const j = await r.json()
    if (typeof j.detail === 'string') return j.detail
    if (Array.isArray(j.detail)) return 'That request was not valid.'
  } catch {

  }
  return `Request failed (${r.status})`
}

async function authHeaders(): Promise<Record<string, string>> {
  const s = await getSession()
  return s ? { Authorization: `Bearer ${s.token}` } : {}
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  let r: Response
  try {
    r = await fetch(`${await backendUrl()}${path}`, {
      ...init,
      headers: { 'Content-Type': 'application/json', ...(await authHeaders()), ...(init.headers as Record<string, string>) },
    })
  } catch {
    throw new ApiError(0, "Can't reach the Esolv server. Is it running?")
  }
  if (r.status === 401 && path !== '/auth/google' && path !== '/auth/dev') {
    unauthorizedHandler?.()
    throw new ApiError(401, 'Your session expired. Please sign in again.')
  }
  if (!r.ok) throw new ApiError(r.status, await errorMessage(r))
  return (await r.json()) as T
}

export const getConfig = () => api<ServerConfig>('/config')
export const loginGoogle = (id_token: string) => api<Session>('/auth/google', { method: 'POST', body: JSON.stringify({ id_token }) })
export const canvasStatus = () => api<CanvasStatus>('/canvas/status')
export const canvasSetToken = (token: string) => api<{ connected: boolean; canvas_name: string }>('/canvas/token', { method: 'POST', body: JSON.stringify({ token }) })
export const canvasDisconnect = () => api<{ connected: boolean }>('/canvas/token', { method: 'DELETE' })
export const canvasOAuthUrl = () => api<{ url: string }>('/canvas/oauth/start')
export const sendFeedback = (rating: 'up' | 'down', comment = '') => api('/feedback', { method: 'POST', body: JSON.stringify({ rating, comment }) })
export const titleChat = (question: string) => api<{ title: string }>('/chat/title', { method: 'POST', body: JSON.stringify({ question }) })

export interface ChatDone {
  answer: string
  citations: Citation[]
  verification: Verification
  flags: string[]
}

export interface ChatHandlers {
  onStatus: (text: string) => void
  onSources: (sources: Citation[], stage: 'retrieved' | 'checking') => void
  onDelta: (text: string) => void
  onDone: (d: ChatDone) => void
  onError: (message: string) => void
}

export interface ExtractedFile {
  name: string
  text: string
  chars: number
  truncated: boolean
  pages: number
}


export async function uploadFile(file: File): Promise<ExtractedFile> {
  const body = new FormData()
  body.append('file', file)
  let r: Response
  try {
    r = await fetch(`${await backendUrl()}/uploads/file`, { method: 'POST', headers: await authHeaders(), body })
  } catch {
    throw new ApiError(0, "Can't reach the Esolv server. Is it running?")
  }
  if (r.status === 401) {
    unauthorizedHandler?.()
    throw new ApiError(401, 'Your session expired. Please sign in again.')
  }
  if (!r.ok) throw new ApiError(r.status, await errorMessage(r))
  return (await r.json()) as ExtractedFile
}

export interface ChatRequest {
  messages: { role: 'user' | 'assistant'; content: string }[]
  page_context?: { title: string; url: string; selection: string } | null
  images?: string[]
  files?: { name: string; text: string }[]
}

export async function streamChat(req: ChatRequest, h: ChatHandlers, signal: AbortSignal): Promise<void> {
  let r: Response
  try {
    r = await fetch(`${await backendUrl()}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...(await authHeaders()) },
      body: JSON.stringify(req),
      signal,
    })
  } catch (e) {
    if ((e as Error).name === 'AbortError') return
    h.onError("Can't reach the Esolv server. Is it running?")
    return
  }
  if (r.status === 401) {
    unauthorizedHandler?.()
    h.onError('Your session expired. Please sign in again.')
    return
  }
  if (!r.ok || !r.body) {
    h.onError(r.status === 429 ? "You're sending messages very quickly. Please wait a moment." : await errorMessage(r))
    return
  }
  const reader = r.body.getReader()
  const dec = new TextDecoder()
  const parser = new SseParser()
  let finished = false
  try {
    for (;;) {
      const { done, value } = await reader.read()
      if (done) break
      for (const ev of parser.push(dec.decode(value, { stream: true }))) {
        if (ev.event === 'status') h.onStatus(ev.data.text)
        else if (ev.event === 'sources') h.onSources(ev.data.sources ?? [], ev.data.stage === 'checking' ? 'checking' : 'retrieved')
        else if (ev.event === 'delta') h.onDelta(ev.data.text)
        else if (ev.event === 'done') { finished = true; h.onDone(ev.data as ChatDone) }
        else if (ev.event === 'error') { finished = true; h.onError(ev.data.message || 'Something went wrong.') }
      }
    }
    if (!finished && !signal.aborted) h.onError('The answer was interrupted before it finished. Try again.')
  } catch (e) {
    if ((e as Error).name !== 'AbortError') h.onError('The connection was interrupted. Please try again.')
  }
}
