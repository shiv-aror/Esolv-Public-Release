import { useCallback, useEffect, useRef, useState } from 'react'
import { streamChat, titleChat } from '../lib/api'
import { hidePartialTag } from '../lib/citations'
import { activeTabContext, store } from '../lib/platform'
import type { Message } from '../lib/types'
import { type ChatThread, storedThread, titleFromQuestion } from './chatHistory'

const uid = () => crypto.randomUUID()
const keyFor = (email: string) => `chats:v1:${email.toLowerCase()}`
const activeKeyFor = (email: string) => `active-chat:v1:${email.toLowerCase()}`

export interface SendOpts {
  images?: string[]
  files?: { name: string; size: number; text: string }[]
  usePage?: boolean
}


export function useChat(userEmail: string | null) {
  const [threads, setThreads] = useState<ChatThread[]>([])
  const [activeId, setActiveId] = useState<string | null>(null)
  const [loadedFor, setLoadedFor] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const abort = useRef<AbortController | null>(null)
  const threadsRef = useRef(threads)
  const activeRef = useRef(activeId)
  threadsRef.current = threads
  activeRef.current = activeId

  useEffect(() => {
    let cancelled = false
    setLoadedFor(null)
    setThreads([])
    setActiveId(null)
    if (!userEmail) return
    void Promise.all([
      store.local.get<ChatThread[]>(keyFor(userEmail)),
      store.local.get<string>(activeKeyFor(userEmail)),
    ]).then(([saved, selected]) => {
      if (cancelled) return
      const valid = (saved ?? []).filter((t) => t?.id && Array.isArray(t.messages)).slice(0, 30)
      setThreads(valid)
      setActiveId(valid.some((t) => t.id === selected) ? selected! : valid[0]?.id ?? null)
      setLoadedFor(userEmail)
    })
    return () => { cancelled = true }
  }, [userEmail])

  useEffect(() => {
    if (!userEmail || loadedFor !== userEmail) return
    const timer = window.setTimeout(() => {
      void store.local.set(keyFor(userEmail), threads.slice(0, 30).map(storedThread))
      if (activeId) void store.local.set(activeKeyFor(userEmail), activeId)
      else void store.local.remove(activeKeyFor(userEmail))
    }, 300)
    return () => window.clearTimeout(timer)
  }, [threads, activeId, loadedFor, userEmail])

  const active = threads.find((t) => t.id === activeId)
  const messages = active?.messages ?? []

  const patch = useCallback((threadId: string, messageId: string, f: (m: Message) => Message) => {
    setThreads((ts) => ts.map((t) => t.id === threadId
      ? { ...t, updatedAt: Date.now(), messages: t.messages.map((m) => m.id === messageId ? f(m) : m) }
      : t))
  }, [])

  const send = useCallback(async (text: string, opts: SendOpts = {}, historyOverride?: Message[]) => {
    const content = text.trim()
    if (!content || abort.current || !userEmail || loadedFor !== userEmail) return
    const ctx = opts.usePage ? await activeTabContext() : null
    if (abort.current) return
    const old = historyOverride ?? threadsRef.current.find((t) => t.id === activeRef.current)?.messages ?? []
    const firstTurn = !old.some((m) => m.role === 'user')
    const threadId = activeRef.current ?? uid()
    const now = Date.now()
    const userMsg: Message = { id: uid(), role: 'user', content, images: opts.images, files: opts.files, pageTitle: ctx?.title }
    const aiId = uid()
    const aiMsg: Message = { id: aiId, role: 'assistant', content: '', streaming: true, status: 'Searching sources…' }
    const nextMessages = [...old, userMsg, aiMsg]
    setThreads((ts) => {
      const existing = ts.find((t) => t.id === threadId)
      const next: ChatThread = existing
        ? { ...existing, title: old.some((m) => m.role === 'user') ? existing.title : titleFromQuestion(content), updatedAt: now, messages: nextMessages }
        : { id: threadId, title: titleFromQuestion(content), createdAt: now, updatedAt: now, messages: nextMessages }
      return [next, ...ts.filter((t) => t.id !== threadId)].slice(0, 30)
    })
    activeRef.current = threadId
    setActiveId(threadId)
    setBusy(true)
    const ac = new AbortController()
    abort.current = ac
    let acc = ''
    const history = old.filter((m) => !m.error && m.content).slice(-58).map((m) => ({ role: m.role, content: m.content }))
    try {
      await streamChat(
        { messages: [...history, { role: 'user', content }], page_context: ctx, images: opts.images, files: opts.files?.map(({ name, text: fileText }) => ({ name, text: fileText })) },
        {
          onStatus: (status) => patch(threadId, aiId, (m) => ({ ...m, status })),
          onSources: (reviewSources, reviewStage) => patch(threadId, aiId, (m) => ({ ...m, reviewSources, reviewStage })),
          onDelta: (delta) => {
            acc += delta
            patch(threadId, aiId, (m) => ({ ...m, content: hidePartialTag(acc), status: undefined }))
          },
          onDone: (result) => {
            patch(threadId, aiId, (m) => ({ ...m, content: result.answer, citations: result.citations, verification: result.verification, flags: result.flags, streaming: false, status: undefined, reviewSources: undefined, reviewStage: undefined }))
            if (firstTurn) {
              void titleChat(content).then(({ title }) => {
                if (title) setThreads((ts) => ts.map((t) => t.id === threadId ? { ...t, title } : t))
              }).catch(() => {   })
            }
          },
          onError: (error) => patch(threadId, aiId, (m) => ({ ...m, error, streaming: false, status: undefined, reviewSources: undefined, reviewStage: undefined })),
        },
        ac.signal,
      )
    } finally {
      if (abort.current === ac) abort.current = null
      setBusy(false)
      patch(threadId, aiId, (m) => ({ ...m, streaming: false, status: undefined, reviewSources: undefined, reviewStage: undefined }))
    }
  }, [loadedFor, patch, userEmail])

  const stop = useCallback(() => {
    abort.current?.abort()
    abort.current = null
    setBusy(false)
    setThreads((ts) => ts.map((t) => ({ ...t, messages: t.messages.map((m) => m.streaming ? { ...m, streaming: false, status: undefined, reviewSources: undefined, reviewStage: undefined, error: m.content ? undefined : 'Stopped.' } : m) })))
  }, [])

  const newChat = useCallback(() => { activeRef.current = null; setActiveId(null) }, [])
  const openChat = useCallback((id: string) => { activeRef.current = id; setActiveId(id) }, [])
  const deleteChat = useCallback((id: string) => {
    if (activeRef.current === id && abort.current) stop()
    setThreads((ts) => ts.filter((t) => t.id !== id))
    if (activeRef.current === id) { activeRef.current = null; setActiveId(null) }
  }, [stop])
  const clearAll = useCallback(() => { stop(); setThreads([]); newChat() }, [newChat, stop])

  const regenerate = useCallback(async () => {
    if (abort.current) return
    const current = threadsRef.current.find((t) => t.id === activeRef.current)
    if (!current) return
    const lastUser = [...current.messages].reverse().find((m) => m.role === 'user')
    if (!lastUser) return
    const prior = current.messages.slice(0, current.messages.lastIndexOf(lastUser))
    await send(lastUser.content, { images: lastUser.images, files: lastUser.files?.filter((f): f is { name: string; size: number; text: string } => !!f.text) }, prior)
  }, [send])

  const setFeedback = useCallback((messageId: string, feedback: 'up' | 'down') => {
    if (activeRef.current) patch(activeRef.current, messageId, (m) => ({ ...m, feedback }))
  }, [patch])

  return { threads, activeId, messages, busy, ready: loadedFor === userEmail && !!userEmail, send, stop, newChat, openChat, deleteChat, clearAll, regenerate, setFeedback }
}
