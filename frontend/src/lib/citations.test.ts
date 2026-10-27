import { describe, expect, it } from 'vitest'
import { hidePartialTag, isSafeUrl, linkifyCitations } from './citations'
import { SseParser } from './sse'
import type { Citation } from './types'

const c = (id: string): Citation => ({ id, title: id, section: '', page: null, url: 'https://x.test', kind: 'knowledge', snippet: '' })

describe('citations', () => {
  it('numbers by first appearance and drops unknown tags', () => {
    const { text, order } = linkifyCitations('A [S7]. B [S2][S7]. C [S9].', [c('S2'), c('S7')])
    expect(order.map((o) => o.id)).toEqual(['S7', 'S2'])
    expect(text).toBe('A [1](esolv-cite:S7). B [2](esolv-cite:S2)[1](esolv-cite:S7). C.')
  })
  it('hides partial tags while streaming', () => {
    expect(hidePartialTag('hello [S')).toBe('hello ')
    expect(hidePartialTag('hello [S12')).toBe('hello ')
    expect(hidePartialTag('hello [S1]')).toBe('hello [S1]')
  })
  it('only allows http(s) urls', () => {
    expect(isSafeUrl('https://a.test/x')).toBe(true)
    expect(isSafeUrl('javascript:alert(1)')).toBe(false)
    expect(isSafeUrl('')).toBe(false)
  })
})

describe('SseParser', () => {
  it('handles events split across chunks', () => {
    const p = new SseParser()
    expect(p.push('event: delta\ndata: {"text":"he')).toEqual([])
    const ev = p.push('llo"}\n\nevent: done\ndata: {"a":1}\n\n')
    expect(ev).toEqual([{ event: 'delta', data: { text: 'hello' } }, { event: 'done', data: { a: 1 } }])
  })
})
