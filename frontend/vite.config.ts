import { crx } from '@crxjs/vite-plugin'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'
import manifest from './manifest.config'

export default defineConfig({
  plugins: [react(), crx({ manifest })],
  build: {
    outDir: process.env.ESOLV_E2E ? 'dist-test' : 'dist',
    rollupOptions: {
      input: {
        privacy: 'src/pages/privacy.html',
        terms: 'src/pages/terms.html',
        panel: 'src/panel/index.html',
      },
    },
  },
  server: { port: 5173, strictPort: true, cors: true, hmr: { port: 5173 } },
  test: { environment: 'jsdom' },
})
