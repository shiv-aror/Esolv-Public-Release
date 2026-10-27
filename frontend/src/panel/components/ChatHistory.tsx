import { useEffect, useMemo, useRef, useState } from 'react'
import type { ChatThread } from '../chatHistory'
import { IconNewChat, IconTrash } from './Icons'

function group(time: number): string {
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const yesterday = new Date(today)
  yesterday.setDate(yesterday.getDate() - 1)
  const lastWeek = new Date(today)
  lastWeek.setDate(lastWeek.getDate() - 7)
  if (time >= today.getTime()) return 'Today'
  if (time >= yesterday.getTime()) return 'Yesterday'
  if (time >= lastWeek.getTime()) return 'Previous 7 days'
  return 'Older'
}

interface Props {
  open: boolean
  threads: ChatThread[]
  activeId: string | null
  onOpen: (id: string) => void
  onNew: () => void
  onDelete: (id: string) => void
}

export function ChatHistory({ open, threads, activeId, onOpen, onNew, onDelete }: Props) {
  const [query, setQuery] = useState('')
  const [confirmId, setConfirmId] = useState<string | null>(null)
  const search = useRef<HTMLInputElement>(null)
  useEffect(() => { if (open) search.current?.focus() }, [open])
  const filtered = useMemo(() => threads
    .filter((t) => t.title.toLowerCase().includes(query.trim().toLowerCase()))
    .sort((a, b) => b.updatedAt - a.updatedAt), [threads, query])
  let previousGroup = ''

  return (
    <aside className="history-sidebar" id="esolv-sidebar" aria-label="Chats" aria-hidden={!open} inert={!open}>
      <div className="history-top">
        <div><span className="eyebrow">WORKSPACE</span><h2>Chats</h2></div>
      </div>
      <button className="history-new" onClick={onNew}><IconNewChat size={17} />New chat</button>
      <label className="history-search">
        <span className="sr-only">Search previous chats</span>
        <input ref={search} value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search chats" />
      </label>
      <div className="history-list">
        {filtered.length ? filtered.map((thread) => {
          const section = group(thread.updatedAt)
          const showGroup = section !== previousGroup
          previousGroup = section
          return (
            <div key={thread.id}>
              {showGroup && <div className="history-group">{section}</div>}
              <div className={`history-item${thread.id === activeId ? ' active' : ''}`}>
                <button className="history-open" onClick={() => onOpen(thread.id)} aria-current={thread.id === activeId ? 'page' : undefined} title={thread.title}>
                  <span>{thread.title}</span>
                </button>
                {confirmId === thread.id ? (
                  <span className="history-confirm"><button onClick={() => { onDelete(thread.id); setConfirmId(null) }}>Delete</button><button onClick={() => setConfirmId(null)}>Cancel</button></span>
                ) : (
                  <button className="icon-btn history-delete" onClick={() => setConfirmId(thread.id)} title={`Delete ${thread.title}`} aria-label={`Delete ${thread.title}`}><IconTrash size={14} /></button>
                )}
              </div>
            </div>
          )
        }) : <div className="history-empty">{threads.length ? 'No matching chats.' : 'Your chats will appear here.'}</div>}
      </div>
      <p className="history-foot">Saved on this browser · Attachments excluded</p>
    </aside>
  )
}
