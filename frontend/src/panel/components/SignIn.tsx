import { useEffect, useState } from 'react'
import { getConfig } from '../../lib/api'
import { signInWithGoogle } from '../../lib/auth'
import type { ServerConfig, Session } from '../../lib/types'
import { GoogleG } from './Icons'
import { Logo } from './Logo'

interface Props {
  onSession: (s: Session) => void
  onPrivacy: () => void
  onTerms: () => void
}

export function SignIn({ onSession, onPrivacy, onTerms }: Props) {
  const [cfg, setCfg] = useState<ServerConfig | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const load = () => getConfig().then((c) => { setCfg(c); setError('') }).catch((e) => setError(e.message))
  useEffect(() => { void load() }, [])

  const google = async () => {
    if (!cfg) return
    setBusy(true); setError('')
    try { onSession(await signInWithGoogle(cfg)) } catch (e) { setError((e as Error).message) } finally { setBusy(false) }
  }

  return (
    <div className="center">
      <div className="signin">
        <span className="mark"><Logo size={56} /></span>
        <h1>Sign in to Esolv</h1>
        <p>MCPS ELD guidance and your Canvas courses, with sources.</p>
        <button className="google-btn" onClick={google} disabled={!!busy || !cfg?.google_client_id}>
          {busy ? <span className="spinner" /> : <GoogleG />}
          Continue with Google
        </button>
        <div className="hint">{cfg && !cfg.google_client_id ? 'Google sign-in needs a Google OAuth client ID in the server configuration.' : <><span className="domain-hint">MCPS account <b>@mcpsmd.org</b></span><span className="approved-hint">Individually approved Google accounts can also sign in.</span></>}</div>
        {error && <div className="error-text" role="alert">{error} {!cfg && <button className="fine-link" style={{ textDecoration: 'underline' }} onClick={load}>Retry</button>}</div>}
        <p className="fine" style={{ marginTop: 22 }}>
          By continuing you agree to the <button onClick={onTerms}>Terms</button> and <button onClick={onPrivacy}>Privacy Policy</button>.
        </p>
      </div>
    </div>
  )
}
