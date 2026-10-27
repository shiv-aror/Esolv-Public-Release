import { useEffect } from 'react'
import type { User } from '../../lib/types'
import { displayName } from '../../lib/user'
import { Avatar } from './Header'
import { IconFile, IconGear, IconLogout, IconShield } from './Icons'

interface Props {
  user: User
  onClose: () => void
  onSettings: () => void
  onPrivacy: () => void
  onTerms: () => void
  onSignOut: () => void
}

export function UserMenu({ user, onClose, onSettings, onPrivacy, onTerms, onSignOut }: Props) {
  useEffect(() => {
    const k = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', k)
    return () => window.removeEventListener('keydown', k)
  }, [onClose])
  const item = (fn: () => void) => () => { onClose(); fn() }
  return (
    <div className="menu-layer" onPointerDown={onClose}>
      <div className="menu" role="menu" onPointerDown={(e) => e.stopPropagation()}>
        <div className="menu-head">
          <Avatar user={user} />
          <div className="who"><b>{displayName(user)}</b></div>
        </div>
        <button className="menu-item" role="menuitem" onClick={item(onSettings)}><IconGear size={17} />Settings &amp; Canvas</button>
        <button className="menu-item" role="menuitem" onClick={item(onPrivacy)}><IconShield size={17} />Privacy Policy</button>
        <button className="menu-item" role="menuitem" onClick={item(onTerms)}><IconFile size={17} />Terms of Service</button>
        <div className="menu-sep" />
        <button className="menu-item danger" role="menuitem" onClick={item(onSignOut)}><IconLogout size={17} />Sign out</button>
      </div>
    </div>
  )
}
