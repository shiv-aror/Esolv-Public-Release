import { describe, expect, it } from 'vitest'
import { storedThread, titleFromQuestion } from './chatHistory'

describe('chat history', () => {
  it('names a chat from its first question', () => {
    expect(titleFromQuestion('  What does IOD-RA say?  ')).toBe('What does IOD-RA say')
    expect(titleFromQuestion('a'.repeat(80))).toHaveLength(52)
  })

  it('keeps text and citations but excludes attachment contents and images', () => {
    const saved = storedThread({ id: '1', title: 'Test', createdAt: 1, updatedAt: 2, messages: [{
      id: 'm', role: 'user', content: 'Question', images: ['data:image/png;base64,secret'],
      files: [{ name: 'plan.pdf', size: 20, text: 'private file text' }], streaming: true,
    }] })
    expect(saved.messages[0].images).toBeUndefined()
    expect(saved.messages[0].files).toEqual([{ name: 'plan.pdf', size: 20 }])
    expect(saved.messages[0].streaming).toBe(false)
  })
})
