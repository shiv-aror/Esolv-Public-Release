import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiError, DEFAULT_BACKEND, backendUrl, canvasDisconnect, canvasOAuthUrl, canvasSetToken, canvasStatus } from '../../lib/api'
import { isExtension, openUrl, store } from '../../lib/platform'
import type { CanvasStatus, ThemePref, User } from '../../lib/types'
import { displayName } from '../../lib/user'
import { IconArrowLeft } from './Icons'

interface Props {
  user: User
  theme: ThemePref
  onTheme: (t: ThemePref) => void
  onBack: () => void
  onClear: () => void
  onClearAll: () => void
  onSignOut: () => void
  toast: (t: string) => void
}

export function Settings({ user, theme, onTheme, onBack, onClear, onClearAll, onSignOut, toast }: Props) {
  const [status, setStatus] = useState<CanvasStatus | null>(null)
  const [token, setToken] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const [confirmClearAll, setConfirmClearAll] = useState(false)
  const [url, setUrl] = useState(DEFAULT_BACKEND)
  const poll = useRef<number | null>(null)

  const refresh = useCallback(() => canvasStatus().then(setStatus).catch((e) => setErr(e.message)), [])
  useEffect(() => { void refresh(); void backendUrl().then(setUrl); return () => { if (poll.current) clearInterval(poll.current) } }, [refresh])

  const saveToken = async () => {
    setBusy(true); setErr('')
    try { const r = await canvasSetToken(token.trim()); setToken(''); toast(`Canvas connected${r.canvas_name ? ` as ${r.canvas_name}` : ''}`); await refresh() }
    catch (e) { setErr((e as ApiError).message) } finally { setBusy(false) }
  }
  const oauth = async () => {
    setErr('')
    try {
      const { url: u } = await canvasOAuthUrl()
      openUrl(u)
      let tries = 0
      poll.current = window.setInterval(async () => {
        tries++
        const s = await canvasStatus().catch(() => null)
        if (s?.kind === 'oauth' || tries > 48) { if (poll.current) clearInterval(poll.current); if (s) setStatus(s); if (s?.kind === 'oauth') toast('Canvas connected') }
      }, 2500)
    } catch (e) { setErr((e as ApiError).message) }
  }
  const disconnect = async () => { await canvasDisconnect().catch(() => {}); toast('Canvas disconnected'); void refresh() }

  const saveUrl = async () => {
    const clean = url.trim().replace(/\/+$/, '')
    try {
      const u = new URL(clean)
      if (isExtension && u.protocol === 'https:' && !['localhost', '127.0.0.1'].includes(u.hostname)) {
        const ok = await chrome.permissions.request({ origins: [`${u.origin}/*`] })
        if (!ok) { toast('Permission to reach that server was declined'); return }
      } else if (u.protocol !== 'https:' && !['localhost', '127.0.0.1'].includes(u.hostname)) {
        toast('Use an https:// address for non-local servers'); return
      }
      await store.local.set('backendUrl', clean)
      toast('Server address saved')
    } catch { toast('That address is not valid') }
  }

  const realConnected = status?.connected && status.kind !== 'mock'
  return (
    <div className="settings">
      <button className="chip-toggle" onClick={onBack} style={{ marginBottom: 8 }}><IconArrowLeft size={14} />Back to chat</button>
      <h2>Settings</h2>

      <section className="card">
        <div className="row" style={{ justifyContent: 'space-between' }}>
          <div><h4>Canvas</h4><p style={{ margin: 0 }}>Read-only access to the courses you teach.</p></div>
          {status && <span className={`pill ${realConnected ? 'on' : status.kind === 'mock' ? 'demo' : 'off'}`}>{realConnected ? 'Connected' : status.kind === 'mock' ? 'Demo data' : 'Not connected'}</span>}
        </div>
        {status?.kind === 'mock' && <p style={{ marginTop: 10 }}>You’re seeing sample Canvas data. Connect your account to use your real classes.</p>}
        {realConnected ? (
          <div style={{ marginTop: 12 }}><button className="btn ghost" onClick={disconnect}>Disconnect Canvas</button></div>
        ) : (
          <div style={{ marginTop: 12, display: 'grid', gap: 10 }}>
            {status?.oauth_available && <button className="btn primary" onClick={oauth}>Sign in with Canvas</button>}
            <div>
              <label htmlFor="pat" style={{ fontSize: 12, color: 'var(--muted)' }}>Or paste a Canvas access token</label>
              <div className="row" style={{ marginTop: 5 }}>
                <input id="pat" className="field" type="password" autoComplete="off" spellCheck={false} placeholder="1234~abcd…" value={token} onChange={(e) => setToken(e.target.value)} />
                <button className="btn primary" disabled={busy || token.trim().length < 10} onClick={saveToken}>{busy ? '…' : 'Save'}</button>
              </div>
              <p style={{ margin: '6px 0 0', fontSize: 11.5 }}>In Canvas: Account → Settings → “+ New Access Token”. It’s stored encrypted and only used to read your courses.</p>
            </div>
          </div>
        )}
        {err && <div className="error-text" role="alert">{err}</div>}
      </section>

      <section className="card">
        <h4>Appearance</h4>
        <p>Match your device or pick a theme.</p>
        <div className="seg" role="group" aria-label="Theme">
          {(['system', 'light', 'dark'] as ThemePref[]).map((t) => (
            <button key={t} aria-pressed={theme === t} onClick={() => onTheme(t)}>{t[0].toUpperCase() + t.slice(1)}</button>
          ))}
        </div>
      </section>

      <section className="card">
        <h4>Conversation</h4>
        <p>Chats are saved on this browser for your account. Screenshots and attachment contents are excluded.</p>
        <div className="row" style={{ flexWrap: 'wrap' }}>
          <button className="btn ghost" onClick={() => { onClear(); toast('Conversation deleted') }}>Delete current chat</button>
          {confirmClearAll ? <><button className="btn ghost" onClick={() => { onClearAll(); setConfirmClearAll(false); toast('All chats deleted') }}>Confirm delete all</button><button className="btn ghost" onClick={() => setConfirmClearAll(false)}>Cancel</button></> : <button className="btn ghost" onClick={() => setConfirmClearAll(true)}>Delete all chats</button>}
        </div>
      </section>

      <section className="card">
        <h4>Server</h4>
        <p>Where Esolv’s backend runs. Use the default for local development.</p>
        <div className="row">
          <input className="field" value={url} onChange={(e) => setUrl(e.target.value)} aria-label="Server address" spellCheck={false} />
          <button className="btn ghost" onClick={saveUrl}>Save</button>
        </div>
      </section>

      <section className="card">
        <h4>Account</h4>
        <p>Signed in as {displayName(user)}</p>
        <button className="btn ghost" onClick={onSignOut}>Sign out</button>
      </section>
    </div>
  )
}
