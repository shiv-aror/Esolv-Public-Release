import { loginGoogle } from './api'
import { isExtension } from './platform'
import type { ServerConfig, Session } from './types'

function b64urlJson(part: string): any {
  const s = part.replace(/-/g, '+').replace(/_/g, '/')
  return JSON.parse(decodeURIComponent(escape(atob(s))))
}





export async function googleFlow(cfg: ServerConfig): Promise<Session> {
  if (!cfg.google_client_id) throw new Error('Google sign-in is not configured on the server yet.')
  const nonce = crypto.randomUUID()
  const params = new URLSearchParams({
    client_id: cfg.google_client_id,
    response_type: 'id_token',
    redirect_uri: chrome.identity.getRedirectURL(),
    scope: 'openid email profile',
    nonce,
    prompt: 'select_account',
  })
  const redirect = await chrome.identity.launchWebAuthFlow({
    url: `https://accounts.google.com/o/oauth2/v2/auth?${params}`,
    interactive: true,
  })
  if (!redirect) throw new Error('Sign-in was cancelled.')
  const idToken = new URLSearchParams(new URL(redirect).hash.slice(1)).get('id_token')
  if (!idToken) throw new Error('Google did not return a sign-in token.')
  if (b64urlJson(idToken.split('.')[1]).nonce !== nonce) throw new Error('Sign-in could not be verified. Please try again.')
  return loginGoogle(idToken)
}


export async function signInWithGoogle(cfg: ServerConfig): Promise<Session> {
  if (!isExtension) throw new Error('Google sign-in only works inside the installed extension.')
  const r = await chrome.runtime.sendMessage({ type: 'esolv:google-signin', cfg })
  if (!r?.session) throw new Error(r?.error || 'Sign-in did not finish. Reopen Esolv; if you completed Google sign-in you will be signed in.')
  return r.session as Session
}
