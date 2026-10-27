import { defineManifest } from '@crxjs/vite-plugin'

export default defineManifest({
  manifest_version: 3,
  name: 'Esolv',
  short_name: 'Esolv',
  version: '0.1.0',
  description: 'A closed-domain AI helper for MCPS ESOL teachers: ELD paperwork, accountability, instructional materials and Canvas, with sources.',
  minimum_chrome_version: '116',
  icons: { '16': 'src/icons/icon-16.png', '32': 'src/icons/icon-32.png', '48': 'src/icons/icon-48.png', '128': 'src/icons/icon-128.png' },
  action: { default_title: 'Open Esolv', default_icon: { '16': 'src/icons/icon-16.png', '32': 'src/icons/icon-32.png' } },
  background: { service_worker: 'src/background/service-worker.ts', type: 'module' },

  permissions: ['storage', 'activeTab', 'scripting', 'tabs', 'identity'],
  host_permissions: [
    'https://mcpsmd.instructure.com/*',
    'http://localhost:8000/*',
    'http://127.0.0.1:8000/*',

    ...(process.env.ESOLV_E2E ? ['<all_urls>'] : []),
  ],
  content_scripts: [{ matches: ['https://mcpsmd.instructure.com/*'], js: ['src/content/canvas-entry.ts'], run_at: 'document_idle' }],

  optional_host_permissions: ['https://*/*'],
  web_accessible_resources: [{ resources: ['src/panel/index.html', 'assets/*', 'src/icons/*'], matches: ['<all_urls>'] }],
  commands: {
    _execute_action: { suggested_key: { default: 'Ctrl+Shift+E', mac: 'Command+Shift+E' }, description: 'Open or close Esolv' },
  },
  content_security_policy: {
    extension_pages: "script-src 'self'; object-src 'self'; base-uri 'none'",
  },
})
