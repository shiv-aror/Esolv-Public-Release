import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import type { User } from '../../lib/types'
import { Header } from './Header'
import { Settings } from './Settings'
import { SignIn } from './SignIn'
import { UserMenu } from './UserMenu'

const user: User = { name: 'Shivum Arora', email: 'arorashivum@gmail.com', picture: '', is_admin: false }
const noop = () => {}

describe('account identity display', () => {
  it('shows the account name without rendering the email address', () => {
    const menu = renderToStaticMarkup(<UserMenu user={user} onClose={noop} onSettings={noop} onPrivacy={noop} onTerms={noop} onSignOut={noop} />)
    const settings = renderToStaticMarkup(<Settings user={user} theme="system" onTheme={noop} onBack={noop} onClear={noop} onClearAll={noop} onSignOut={noop} toast={noop} />)
    const header = renderToStaticMarkup(<Header user={user} onNewChat={noop} onHistory={noop} historyOpen={false} onPopout={noop} onExpand={noop} onMenu={noop} menuOpen={false} onDock={noop} docked={false} />)
    for (const html of [menu, settings, header]) {
      expect(html).toContain('Shivum Arora')
      expect(html).not.toContain('arorashivum@gmail.com')
    }
  })

  it('labels the MCPS domain on the Google sign-in screen', () => {
    const html = renderToStaticMarkup(<SignIn onSession={noop} onPrivacy={noop} onTerms={noop} />)
    expect(html).toContain('@mcpsmd.org')
    expect(html).toContain('Individually approved Google accounts')
  })
})
