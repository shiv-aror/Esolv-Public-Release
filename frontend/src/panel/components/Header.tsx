import { useRef, useState } from 'react'
import { inFrame, isExtension, isPopup, isWindowMode, postToHost } from '../../lib/platform'
import type { User } from '../../lib/types'
import { displayName } from '../../lib/user'
import { IconClose, IconDock, IconExpand, IconFloating, IconNewChat, IconPopout, IconSidebar } from './Icons'
import { Logo } from './Logo'

export function initials(u: User): string {
  const parts = displayName(u).split(/\s+/).filter(Boolean)
  return ((parts[0]?.[0] ?? '?') + (parts.length > 1 ? parts[1][0] : '')).toUpperCase()
}

export function Avatar({ user }: { user: User }) {
  return <span className="avatar">{user.picture ? <img src={user.picture} alt="" referrerPolicy="no-referrer" /> : initials(user)}</span>
}

interface Props {
  user: User | null
  onNewChat: () => void
  onHistory: () => void
  historyOpen: boolean
  onPopout: () => void
  onExpand: () => void
  onMenu: () => void
  menuOpen: boolean
  onDock: () => void
  docked: boolean
}

export function Header({ user, onNewChat, onHistory, historyOpen, onPopout, onExpand, onMenu, menuOpen, onDock, docked }: Props) {
  const draggable = inFrame && !isWindowMode
  const [dragging, setDragging] = useState(false)
  const last = useRef({ x: 0, y: 0 })


  const down = (e: React.PointerEvent) => {
    if (!draggable || (e.target as HTMLElement).closest('button')) return
    ;(e.currentTarget as HTMLElement).setPointerCapture(e.pointerId)
    last.current = { x: e.screenX, y: e.screenY }
    setDragging(true)
  }
  const move = (e: React.PointerEvent) => {
    if (!dragging) return
    const dx = e.screenX - last.current.x
    const dy = e.screenY - last.current.y
    last.current = { x: e.screenX, y: e.screenY }
    if (dx || dy) postToHost({ type: 'drag', dx, dy })
  }
  const up = () => {
    if (dragging) { setDragging(false); postToHost({ type: 'drag-end' }) }
  }

  return (
    <header className={`header${draggable ? ' draggable' : ''}${dragging ? ' dragging' : ''}`} onPointerDown={down} onPointerMove={move} onPointerUp={up} onPointerCancel={up}>
      {user && (
        <button className={`icon-btn sidebar-toggle${historyOpen ? ' selected' : ''}`} onClick={onHistory} title={historyOpen ? 'Hide chats' : 'Show chats'} aria-label={historyOpen ? 'Hide chats' : 'Show chats'} aria-expanded={historyOpen} aria-controls="esolv-sidebar"><IconSidebar size={18} /></button>
      )}
      <div className="brand">
        <Logo size={26} />
        <span className="brand-name">Esolv</span>
      </div>
      {user && (
        <button className="icon-btn" onClick={onNewChat} title="New chat" aria-label="New chat"><IconNewChat /></button>
      )}
      {isPopup && (
        <button className="icon-btn" onClick={onExpand} title="Open larger, resizable window" aria-label="Open larger, resizable window"><IconExpand size={17} /></button>
      )}
      {draggable && (
        <button className="icon-btn" onClick={onDock} title={docked ? 'Floating window' : 'Dock on this page'} aria-label={docked ? 'Floating window' : 'Dock on this page'}>{docked ? <IconFloating size={17} /> : <IconDock size={17} />}</button>
      )}
      {isExtension && !isWindowMode && !isPopup && (
        <button className="icon-btn" onClick={onPopout} title="Open in its own window" aria-label="Open in its own window"><IconPopout size={17} /></button>
      )}
      {user && (
        <button className="avatar-btn" onClick={onMenu} aria-haspopup="menu" aria-expanded={menuOpen} aria-label="Account menu" title={displayName(user)}>
          <Avatar user={user} />
        </button>
      )}
      {draggable && (
        <button className="icon-btn" onClick={() => postToHost({ type: 'close' })} title="Close" aria-label="Close Esolv"><IconClose /></button>
      )}
    </header>
  )
}
