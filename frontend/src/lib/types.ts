export interface Citation {
  id: string
  title: string
  section: string
  page: number | null
  url: string
  kind: 'knowledge' | 'canvas' | 'file'
  snippet: string
}

export type VerificationStatus = 'verified' | 'partial' | 'unsupported' | 'unchecked' | 'not_found' | 'n/a'

export interface Verification {
  status: VerificationStatus
  notes: string[]
}

export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  images?: string[]
  files?: { name: string; size: number; text?: string }[]
  pageTitle?: string
  citations?: Citation[]
  verification?: Verification
  flags?: string[]

  status?: string
  reviewSources?: Citation[]
  reviewStage?: 'retrieved' | 'checking'
  streaming?: boolean
  error?: string
  feedback?: 'up' | 'down'
}

export interface User {
  email: string
  name: string
  picture: string
  is_admin: boolean
}

export interface Session {
  token: string
  expires_at: number
  user: User
}

export interface ServerConfig {
  google_client_id: string
  allowed_domains: string[]
  dev_login: boolean
  model: string
  canvas_oauth: boolean
  canvas_base_url: string
}

export interface CanvasStatus {
  connected: boolean
  kind: 'pat' | 'oauth' | 'mock' | null
  oauth_available: boolean
  canvas_base_url: string
}

export type ThemePref = 'system' | 'light' | 'dark'


export interface Attachment {
  id: string
  kind: 'image' | 'file'
  name: string
  size: number
  dataUrl?: string
  text?: string
  truncated?: boolean
  status: 'reading' | 'ready' | 'error'
  error?: string
}
