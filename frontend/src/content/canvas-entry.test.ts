import { describe, expect, it, vi } from 'vitest'

describe('Canvas entry button', () => {
  it('opens the in-page Esolv panel and uses the extension logo URL', async () => {
    const getURL = vi.fn((path: string) => `chrome-extension://test/${path}`)
    const sendMessage = vi.fn().mockResolvedValue({ ok: true })
    vi.stubGlobal('chrome', { runtime: { getURL, sendMessage } })
    const originalAttach = Element.prototype.attachShadow
    const shadow = vi.spyOn(Element.prototype, 'attachShadow').mockImplementation(function (this: Element, options) {
      return originalAttach.call(this, { ...options, mode: 'open' })
    })
    try {
      await import('./canvas-entry')
      const host = document.getElementById('esolv-canvas-entry')
      const button = host?.shadowRoot?.querySelector('button')
      expect(button).toBeTruthy()
      expect(host?.shadowRoot?.querySelector('img')?.src).toContain('chrome-extension://test/src/icons/esolv-logo.png')
      button?.click()
      expect(sendMessage).toHaveBeenCalledWith({ type: 'esolv:open-here' })
    } finally {
      document.getElementById('esolv-canvas-entry')?.remove()
      shadow.mockRestore()
      vi.unstubAllGlobals()
    }
  })
})
