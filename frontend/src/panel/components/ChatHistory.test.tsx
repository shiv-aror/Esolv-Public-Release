import { act } from 'react'
import { createRoot } from 'react-dom/client'
import { describe, expect, it, vi } from 'vitest'
import { ChatHistory } from './ChatHistory'

describe('chat sidebar', () => {
  it('opens and deletes a saved chat without replacing the conversation view', async () => {
    const host = document.createElement('div')
    document.body.append(host)
    const root = createRoot(host)
    const onOpen = vi.fn()
    const onDelete = vi.fn()
    const onNew = vi.fn()
    await act(async () => root.render(
      <ChatHistory open threads={[{ id: 'chat-1', title: 'ELD placement guidance', createdAt: Date.now(), updatedAt: Date.now(), messages: [] }]} activeId="chat-1" onOpen={onOpen} onDelete={onDelete} onNew={onNew} />,
    ))

    expect(host.querySelector('[aria-current="page"]')?.textContent).toBe('ELD placement guidance')
    await act(async () => (host.querySelector('.history-open') as HTMLButtonElement).click())
    expect(onOpen).toHaveBeenCalledWith('chat-1')
    await act(async () => (host.querySelector('.history-delete') as HTMLButtonElement).click())
    await act(async () => (host.querySelector('.history-confirm button') as HTMLButtonElement).click())
    expect(onDelete).toHaveBeenCalledWith('chat-1')
    await act(async () => (host.querySelector('.history-new') as HTMLButtonElement).click())
    expect(onNew).toHaveBeenCalledOnce()

    await act(async () => root.unmount())
    host.remove()
  })
})
