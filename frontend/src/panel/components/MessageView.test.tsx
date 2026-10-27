import { describe, expect, it } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import { AssistantMessage } from './MessageView'
import type { Message } from '../../lib/types'

describe('working source list', () => {
  it('shows the retrieved PDF page as a clickable link during fact checking', () => {
    const message: Message = {
      id: 'a1', role: 'assistant', content: '', streaming: true,
      status: 'Checking each claim against the source passages…', reviewStage: 'checking',
      reviewSources: [{ id: 'S1', title: 'MCPS Regulation IOD-RA', section: 'Accommodations', page: 2,
        url: 'https://ww2.montgomeryschoolsmd.org/departments/policy/pdf/iodra.pdf#page=2', kind: 'knowledge', snippet: 'Students should receive identified accommodations.' }],
    }
    const html = renderToStaticMarkup(<AssistantMessage m={message} isLast onRegenerate={() => {}} onFeedback={() => {}} toast={() => {}} />)
    expect(html).toContain('Sources being checked')
    expect(html).toContain('iodra.pdf#page=2')
    expect(html).toContain('p. 2')
  })
})
