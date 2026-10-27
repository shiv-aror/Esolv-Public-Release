import type { Citation } from './types'

const TAG = /\[S(\d+)\]/g


export function citedOrder(text: string): string[] {
  const seen: string[] = []
  for (const m of text.matchAll(TAG)) {
    const id = `S${m[1]}`
    if (!seen.includes(id)) seen.push(id)
  }
  return seen
}





export function linkifyCitations(text: string, citations: Citation[]): { text: string; order: Citation[] } {
  const known = new Map(citations.map((c) => [c.id, c]))
  const order = citedOrder(text)
    .map((id) => known.get(id))
    .filter((c): c is Citation => !!c)
  const num = new Map(order.map((c, i) => [c.id, i + 1]))
  const out = text.replace(TAG, (_m, n) => {
    const id = `S${n}`
    return num.has(id) ? `[${num.get(id)}](esolv-cite:${id})` : ''
  })
  return { text: out.replace(/ +([.,;:])/g, '$1'), order }
}


export function hidePartialTag(text: string): string {
  return text.replace(/\[S?\d*$/, '')
}

export function isSafeUrl(url: string): boolean {
  try {
    const u = new URL(url)
    return u.protocol === 'https:' || u.protocol === 'http:'
  } catch {
    return false
  }
}
