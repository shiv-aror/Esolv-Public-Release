import { useCallback, useEffect, useRef, useState } from 'react'
import { getSession, onUnauthorized, saveSession } from '../lib/api'
import { extensionPage, inFrame, isExtension, isPopup, isWindowMode, openUrl, postToHost, store } from '../lib/platform'
import type { Session } from '../lib/types'
import { Composer } from './components/Composer'
import { ChatHistory } from './components/ChatHistory'
import { Empty } from './components/Empty'
import { Header } from './components/Header'
import { AssistantMessage, UserMessage } from './components/MessageView'
import { Settings } from './components/Settings'
import { SignIn } from './components/SignIn'
import { UserMenu } from './components/UserMenu'
import { useTheme } from './theme'
import { useChat } from './useChat'

type View = 'chat' | 'settings'

export function App() {
  const [session, setSession] = useState<Session | null | undefined>(undefined)
  const [view, setView] = useState<View>('chat')
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [menu, setMenu] = useState(false)
  const [docked, setDocked] = useState(false)
  const [toastText, setToast] = useState('')
  const [theme, setTheme] = useTheme()
  const [confirm, setConfirm] = useState<null | ((ok: boolean) => void)>(null)
  const chat = useChat(session?.user.email ?? null)
  const scroller = useRef<HTMLDivElement>(null)
  const stick = useRef(true)

  useEffect(() => {
    void getSession().then((s) => setSession(s))
    onUnauthorized(() => { void saveSession(null); setSession(null) })
  }, [])

  const toast = useCallback((t: string) => { setToast(t); setTimeout(() => setToast(''), 2200) }, [])
  const privacy = () => openUrl(extensionPage('src/pages/privacy.html'))
  const terms = () => openUrl(extensionPage('src/pages/terms.html'))
  const signOut = async () => { chat.stop(); chat.newChat(); await saveSession(null); setSession(null); setView('chat'); setSidebarOpen(false) }
  const popout = () => { if (isExtension) void chrome.runtime.sendMessage({ type: 'esolv:popout' }).then(() => { try { window.parent.postMessage({ source: 'esolv-panel', type: 'close' }, '*') } catch {   } }) }

  const expand = () => { if (isExtension) void chrome.runtime.sendMessage({ type: 'esolv:expand' }).then(() => window.close()) }


  useEffect(() => {
    const el = scroller.current
    if (el && stick.current) el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' })
  }, [chat.messages])
  const onScroll = () => {
    const el = scroller.current
    if (el) stick.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80
  }

  const confirmCapture = useCallback(async () => {
    if (await store.session.get<boolean>('captureAck')) return true
    const ok = await new Promise<boolean>((res) => setConfirm(() => res))
    setConfirm(null)
    if (ok) await store.session.set('captureAck', true)
    return ok
  }, [])


  useEffect(() => {
    const h = (e: MessageEvent) => { if (e.data?.source === 'esolv-host' && e.data.type === 'opened') document.querySelector<HTMLTextAreaElement>('.composer textarea')?.focus() }
    window.addEventListener('message', h)
    return () => window.removeEventListener('message', h)
  }, [])
  useEffect(() => {
    if (!inFrame) return
    void store.local.get<boolean>('esolv.docked.v2').then((v) => setDocked(!!v))
    const h = (e: MessageEvent) => { if (e.data?.source === 'esolv-host' && e.data.type === 'dock-state') setDocked(!!e.data.docked) }
    window.addEventListener('message', h)
    return () => window.removeEventListener('message', h)
  }, [])

  useEffect(() => {
    if (!sidebarOpen) return
    const closeOnEscape = (e: KeyboardEvent) => {
      if (e.key !== 'Escape') return
      setSidebarOpen(false)
      document.querySelector<HTMLButtonElement>('.sidebar-toggle')?.focus()
    }
    window.addEventListener('keydown', closeOnEscape)
    return () => window.removeEventListener('keydown', closeOnEscape)
  }, [sidebarOpen])

  if (session === undefined) return <div className="app" />

  const user = session?.user ?? null
  return (
    <div className="app" data-window={isPopup ? 'popup' : isWindowMode || !inFrame ? 'standalone' : 'floating'}>
      <Header user={user} onNewChat={() => { chat.newChat(); stick.current = true; setView('chat'); if (window.innerWidth < 700) setSidebarOpen(false) }} onHistory={() => { setView('chat'); setSidebarOpen((open) => !open); setMenu(false) }} historyOpen={sidebarOpen} onPopout={popout} onExpand={expand} onDock={() => { postToHost({ type: 'dock' }); setDocked((v) => !v) }} docked={docked} onMenu={() => setMenu((m) => !m)} menuOpen={menu} />

      {!session && <SignIn onSession={async (s) => { await saveSession(s); setSession(s) }} onPrivacy={privacy} onTerms={terms} />}

      {session && (
        <div className={`workspace${sidebarOpen ? ' sidebar-open' : ''}`}>
          <button className="sidebar-scrim" onClick={() => setSidebarOpen(false)} aria-label="Close chats" tabIndex={-1} />
          <ChatHistory open={sidebarOpen} threads={chat.threads} activeId={chat.activeId} onOpen={(id) => { chat.openChat(id); stick.current = true; setView('chat'); if (window.innerWidth < 700) setSidebarOpen(false) }} onNew={() => { chat.newChat(); stick.current = true; setView('chat'); if (window.innerWidth < 700) setSidebarOpen(false) }} onDelete={chat.deleteChat} />
          <main className="chat-main">
            {view === 'settings' && (
              <Settings user={session.user} theme={theme} onTheme={setTheme} onBack={() => setView('chat')} onClear={() => { if (chat.activeId) chat.deleteChat(chat.activeId); else chat.newChat() }} onClearAll={chat.clearAll} onSignOut={signOut} toast={toast} />
            )}
            {view === 'chat' && (
              <>
                {!chat.ready && <div className="history-empty" role="status">Loading your chats…</div>}
                {chat.ready && (
                  <>
                    {chat.messages.length > 0 && <div className="chat-context"><span className="chat-context-label">CONVERSATION</span><strong title={chat.threads.find((t) => t.id === chat.activeId)?.title}>{chat.threads.find((t) => t.id === chat.activeId)?.title ?? 'New chat'}</strong>{chat.messages.some((m) => m.streaming) && <span className="chat-context-live">Working</span>}</div>}
                    <div className="scroll" ref={scroller} onScroll={onScroll} role="log" aria-label="Conversation">
                      {chat.messages.length === 0 ? (
                        <Empty onPick={(q) => void chat.send(q)} />
                      ) : (
                        <div className="thread">
                          {chat.messages.map((m, i) =>
                            m.role === 'user' ? (
                              <UserMessage key={m.id} m={m} />
                            ) : (
                              <AssistantMessage key={m.id} m={m} isLast={i === chat.messages.length - 1} onRegenerate={() => void chat.regenerate()} onFeedback={chat.setFeedback} toast={toast} />
                            ),
                          )}
                        </div>
                      )}
                    </div>
                    <Composer
                      key={chat.activeId ?? 'new-chat'}
                      busy={chat.busy}
                      onSend={(t, o) => { stick.current = true; void chat.send(t, o) }}
                      onStop={chat.stop}
                      onExpand={expand}
                      toast={toast}
                      onPrivacy={privacy}
                      onTerms={terms}
                      confirmCapture={confirmCapture}
                    />
                  </>
                )}
              </>
            )}
          </main>
        </div>
      )}

      {menu && user && (
        <UserMenu user={user} onClose={() => setMenu(false)} onSettings={() => { setSidebarOpen(false); setView('settings') }} onPrivacy={privacy} onTerms={terms} onSignOut={signOut} />
      )}

      {confirm && (
        <div className="scrim" role="dialog" aria-modal="true" aria-labelledby="cap-h">
          <div className="modal">
            <h3 id="cap-h">Capture this page?</h3>
            <p>The screenshot is sent to the AI to read. It may contain student names or IDs, and images can’t be anonymized. Only capture what you’re comfortable sharing.</p>
            <div className="btn-row">
              <button className="btn ghost" onClick={() => confirm(false)}>Cancel</button>
              <button className="btn primary" onClick={() => confirm(true)}>Capture</button>
            </div>
          </div>
        </div>
      )}
      {toastText && <div className="toast" role="status">{toastText}</div>}
    </div>
  )
}
