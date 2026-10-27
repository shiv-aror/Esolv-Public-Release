import { useCallback, useEffect, useRef, useState } from 'react'
import { uploadFile } from '../../lib/api'
import { captureTab, inFrame, isExtension, isPopup, isWindowMode, store } from '../../lib/platform'
import type { Attachment } from '../../lib/types'
import { IconArrowUp, IconCamera, IconClose, IconDoc, IconFile, IconImage, IconPaperclip, IconStop } from './Icons'

const MAX_ATTACHMENTS = 4
const MAX_CHARS = 6000
const FILE_EXT = /\.(pdf|docx|txt|md|csv|html?)$/i
const uid = () => crypto.randomUUID()


export async function fileToDataUrl(file: File): Promise<string> {
  const bmp = await createImageBitmap(file)
  const scale = Math.min(1, 1568 / Math.max(bmp.width, bmp.height))
  const c = document.createElement('canvas')
  c.width = Math.round(bmp.width * scale)
  c.height = Math.round(bmp.height * scale)
  c.getContext('2d')!.drawImage(bmp, 0, 0, c.width, c.height)
  return c.toDataURL(file.type === 'image/png' ? 'image/png' : 'image/jpeg', 0.85)
}

export function formatSize(n: number): string {
  return n < 1024 * 1024 ? `${Math.max(1, Math.round(n / 1024))} KB` : `${(n / 1024 / 1024).toFixed(1)} MB`
}

function ext(name: string): string {
  return (name.split('.').pop() ?? '').toUpperCase().slice(0, 4)
}

interface Props {
  busy: boolean
  onSend: (text: string, opts: { images: string[]; files: { name: string; size: number; text: string }[]; usePage: boolean }) => void
  onStop: () => void
  onExpand: () => void
  toast: (t: string) => void
  onPrivacy: () => void
  onTerms: () => void
  confirmCapture: () => Promise<boolean>
}

export function Composer({ busy, onSend, onStop, onExpand, toast, onPrivacy, onTerms, confirmCapture }: Props) {
  const [text, setText] = useState('')
  const [items, setItems] = useState<Attachment[]>([])
  const [usePage, setUsePage] = useState(false)
  const [menu, setMenu] = useState(false)
  const [dragging, setDragging] = useState(false)
  const ta = useRef<HTMLTextAreaElement>(null)
  const picker = useRef<HTMLInputElement>(null)
  const itemsRef = useRef<Attachment[]>([])
  itemsRef.current = items
  const dragDepth = useRef(0)
  const canPage = isExtension ? isPopup || (inFrame && !isWindowMode) : true

  useEffect(() => { void store.local.get<boolean>('usePage').then((v) => setUsePage(!!v)) }, [])
  useEffect(() => {
    const el = ta.current
    if (!el) return
    el.style.height = '0px'
    el.style.height = `${Math.min(el.scrollHeight, 168)}px`
  }, [text])
  useEffect(() => { ta.current?.focus() }, [])

  const patch = useCallback((id: string, p: Partial<Attachment>) => setItems((a) => a.map((x) => (x.id === id ? { ...x, ...p } : x))), [])


  const addFiles = useCallback((files: File[]) => {
    const room = MAX_ATTACHMENTS - itemsRef.current.length
    if (room <= 0) { toast(`You can attach up to ${MAX_ATTACHMENTS} files.`); return }
    if (files.length > room) toast(`Only the first ${room} could be added (limit ${MAX_ATTACHMENTS}).`)
    for (const f of files.slice(0, room)) {
      const id = uid()
      if (/^image\/(png|jpe?g|webp)$/.test(f.type)) {
        setItems((a) => [...a, { id, kind: 'image', name: f.name || 'image', size: f.size, status: 'reading' }])
        fileToDataUrl(f).then((dataUrl) => patch(id, { dataUrl, status: 'ready' })).catch(() => patch(id, { status: 'error', error: "That image couldn't be read." }))
      } else if (FILE_EXT.test(f.name)) {
        setItems((a) => [...a, { id, kind: 'file', name: f.name, size: f.size, status: 'reading' }])
        uploadFile(f)
          .then((r) => patch(id, { text: r.text, truncated: r.truncated, status: 'ready' }))
          .catch((e) => patch(id, { status: 'error', error: (e as Error).message }))
      } else {
        toast(`“${f.name}” isn’t supported. Use PDF, Word, text, CSV, or an image.`)
      }
    }
  }, [patch, toast])


  useEffect(() => {
    const hasFiles = (e: DragEvent) => !!e.dataTransfer?.types.includes('Files')
    const enter = (e: DragEvent) => { if (hasFiles(e)) { e.preventDefault(); dragDepth.current++; setDragging(true) } }
    const over = (e: DragEvent) => { if (hasFiles(e)) e.preventDefault() }
    const leave = (e: DragEvent) => { if (hasFiles(e) && --dragDepth.current <= 0) { dragDepth.current = 0; setDragging(false) } }
    const drop = (e: DragEvent) => {
      if (!hasFiles(e)) return
      e.preventDefault()
      dragDepth.current = 0
      setDragging(false)
      const fs = Array.from(e.dataTransfer?.files ?? [])
      if (fs.length) addFiles(fs)
      ta.current?.focus()
    }
    window.addEventListener('dragenter', enter)
    window.addEventListener('dragover', over)
    window.addEventListener('dragleave', leave)
    window.addEventListener('drop', drop)
    return () => { window.removeEventListener('dragenter', enter); window.removeEventListener('dragover', over); window.removeEventListener('dragleave', leave); window.removeEventListener('drop', drop) }
  }, [addFiles])

  const capture = async () => {
    setMenu(false)
    if (!(await confirmCapture())) return
    if (itemsRef.current.length >= MAX_ATTACHMENTS) { toast(`You can attach up to ${MAX_ATTACHMENTS} files.`); return }
    const url = await captureTab()
    if (!url) { toast(isExtension ? 'Couldn’t capture this page. Close Esolv, click the toolbar icon again on this tab, and retry.' : 'Screenshots work in the installed extension.'); return }
    setItems((a) => [...a, { id: uid(), kind: 'image', name: 'Page screenshot', size: Math.round((url.length * 3) / 4), dataUrl: url, status: 'ready' }])
  }

  const reading = items.some((i) => i.status === 'reading')
  const ready = items.filter((i) => i.status === 'ready')
  const over = text.length > MAX_CHARS
  const canSend = !busy && !reading && !over && (!!text.trim() || ready.length > 0)

  const submit = () => {
    if (!canSend) return
    const t = text.trim()
    const images = ready.filter((i) => i.kind === 'image').map((i) => i.dataUrl!)
    const files = ready.filter((i) => i.kind === 'file').map((i) => ({ name: i.name, size: i.size, text: i.text! }))
    onSend(t || (files.length ? 'Please summarize the attached file and tell me what matters for ESOL/ELD at MCPS.' : 'What does this image show, and how does it relate to ESOL/ELD at MCPS?'), { images, files, usePage: usePage && canPage })
    setText(''); setItems([])
  }

  const togglePage = () => { const v = !usePage; setUsePage(v); void store.local.set('usePage', v) }

  return (
    <div className="dock">
      {dragging && (
        <div className="dropzone" aria-hidden="true">
          <div><IconPaperclip size={22} /><b>Drop files to attach</b><span>PDF, Word, text, CSV or images. Nothing is sent until you press Enter.</span></div>
        </div>
      )}
      {menu && (
        <>
          <div className="menu-layer" style={{ zIndex: 19 }} onPointerDown={() => setMenu(false)} />
          <div className="pop-menu" role="menu">
            {isPopup ? (
              <button className="menu-item" role="menuitem" onClick={() => { setMenu(false); onExpand() }}><IconFile size={17} />Attach files (opens larger window)</button>
            ) : (
              <button className="menu-item" role="menuitem" onClick={() => { setMenu(false); picker.current?.click() }}><IconFile size={17} />Attach files or images</button>
            )}
            <button className="menu-item" role="menuitem" onClick={capture}><IconCamera size={17} />Capture this page</button>
          </div>
        </>
      )}
      <div className="composer">
        {items.length > 0 && (
          <div className="chips" aria-label="Attachments">
            {items.map((a) => (
              <div className={`chip-file${a.status === 'error' ? ' bad' : ''}`} key={a.id} title={a.error || a.name}>
                {a.kind === 'image' && a.dataUrl ? <img src={a.dataUrl} alt="" /> : <span className="ft">{a.status === 'reading' ? <span className="spinner" /> : a.kind === 'image' ? <IconImage size={16} /> : ext(a.name)}</span>}
                <span className="fn"><b>{a.name}</b><span>{a.status === 'error' ? a.error : a.status === 'reading' ? 'Reading…' : a.truncated ? `${formatSize(a.size)} · long, first part used` : formatSize(a.size)}</span></span>
                <button onClick={() => setItems((x) => x.filter((i) => i.id !== a.id))} aria-label={`Remove ${a.name}`}><IconClose size={13} /></button>
              </div>
            ))}
          </div>
        )}
        <textarea
          ref={ta}
          rows={1}
          value={text}
          placeholder="Ask about ELD or Canvas…"
          aria-label="Message Esolv"
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); submit() } }}
          onPaste={(e) => {
            const fs = Array.from(e.clipboardData.files)
            if (fs.length) { e.preventDefault(); addFiles(fs) }
          }}
        />
        <div className="composer-row">
          <button className="icon-btn" onClick={() => setMenu((m) => !m)} title="Attach" aria-label="Attach a file or capture the page" aria-haspopup="menu"><IconPaperclip /></button>
          {canPage && (
            <button className="chip-toggle" aria-pressed={usePage} onClick={togglePage} title="Share this page's title and any selected text with Esolv">
              <IconDoc size={14} />This page
            </button>
          )}
          <span className="spacer" />
          {text.length > MAX_CHARS * 0.8 && <span className={`char-count${over ? ' over' : ''}`}>{text.length}/{MAX_CHARS}</span>}
          {busy ? (
            <button className="send" onClick={onStop} aria-label="Stop generating" title="Stop"><IconStop size={18} /></button>
          ) : (
            <button className="send" onClick={submit} disabled={!canSend} aria-label="Send message" title={reading ? 'Waiting for files to finish reading' : 'Send (Enter)'}><IconArrowUp size={18} /></button>
          )}
        </div>
        <input ref={picker} type="file" accept=".pdf,.docx,.txt,.md,.csv,.html,.htm,image/png,image/jpeg,image/webp" multiple hidden
          onChange={(e) => { addFiles(Array.from(e.target.files ?? [])); e.target.value = '' }} />
      </div>
      <p className="fine">Check the cited sources for student decisions · <button onClick={onPrivacy}>Privacy</button> · <button onClick={onTerms}>Terms</button></p>
    </div>
  )
}
