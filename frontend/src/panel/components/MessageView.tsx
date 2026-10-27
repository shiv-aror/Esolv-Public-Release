import { useMemo, useRef, useState } from 'react'
import Markdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { sendFeedback } from '../../lib/api'
import { isSafeUrl, linkifyCitations } from '../../lib/citations'
import { openUrl } from '../../lib/platform'
import type { Citation, Message } from '../../lib/types'
import { IconAlert, IconCanvas, IconCheck, IconCopy, IconDoc, IconExternal, IconFile, IconRefresh, IconShield, IconShieldCheck, IconThumbDown, IconThumbUp } from './Icons'
import { formatSize } from './Composer'

function Verification({ m }: { m: Message }) {
  const [open, setOpen] = useState(false)
  const v = m.verification
  if (!v || m.streaming) return null
  const notes = v.notes ?? []
  if (v.status === 'verified')
    return <div className="badges"><span className="badge ok"><IconShieldCheck size={14} />Checked against sources</span></div>
  if (v.status === 'partial')
    return (
      <>
        <div className="badges">
          <button className="badge muted" onClick={() => setOpen((o) => !o)} aria-expanded={open}><IconShield size={14} />Double-check with the sources{notes.length ? ' · details' : ''}</button>
        </div>
        {open && notes.length > 0 && <div className="notes"><b>What I couldn’t fully confirm</b><ul>{notes.map((n, i) => <li key={i}>{n}</li>)}</ul></div>}
      </>
    )
  if (v.status === 'unchecked')
    return <div className="badges"><span className="badge muted"><IconShield size={14} />Not fact-checked</span></div>
  if (v.status === 'unsupported' || v.status === 'not_found')
    return <div className="badges"><span className="badge muted"><IconShield size={14} />No matching MCPS source</span></div>
  return null
}

function SourceRow({ c, n, flash }: { c: Citation; n: number; flash: boolean }) {
  const leaf = c.section.split('>').pop()?.trim() ?? ''
  const detail = c.kind === 'canvas' ? 'Record from Canvas' : c.kind === 'file' ? 'Your attachment' : [leaf, c.page ? `p. ${c.page}` : ''].filter(Boolean).join(' · ') || c.snippet.slice(0, 80)
  const safe = isSafeUrl(c.url)
  const body = (
    <>
      <span className="n">{n}</span>
      <span className="t">
        <b>{c.title}</b>
        <span>{detail}</span>
      </span>
      <span className="go">{safe ? <IconExternal size={15} /> : c.kind === 'canvas' ? <IconCanvas size={15} /> : c.kind === 'file' ? <IconFile size={15} /> : <IconDoc size={15} />}</span>
    </>
  )
  return safe ? (
    <a className={`source${flash ? ' flash' : ''}`} id={`src-${c.id}`} href={c.url} onClick={(e) => { e.preventDefault(); openUrl(c.url) }} title={c.snippet}>{body}</a>
  ) : (
    <div className={`source${flash ? ' flash' : ''}`} id={`src-${c.id}`} title={c.snippet}>{body}</div>
  )
}

function WorkingSources({ m }: { m: Message }) {
  if (!m.streaming || !m.reviewSources?.length) return null
  const checking = m.reviewStage === 'checking'
  return (
    <details className="working-sources">
      <summary>{checking ? 'Sources being checked' : 'Sources found'} <span>{m.reviewSources.length}</span></summary>
      <p>{checking ? 'These passages are being compared with the draft answer.' : 'These are preliminary matches; the answer has not been checked yet.'}</p>
      <div className="working-source-list">
        {m.reviewSources.map((c, i) => <SourceRow key={`${c.id}-${i}`} c={c} n={i + 1} flash={false} />)}
      </div>
    </details>
  )
}

interface Props {
  m: Message
  isLast: boolean
  onRegenerate: () => void
  onFeedback: (id: string, f: 'up' | 'down') => void
  toast: (t: string) => void
}

export function AssistantMessage({ m, isLast, onRegenerate, onFeedback, toast }: Props) {
  const [copied, setCopied] = useState(false)
  const [flash, setFlash] = useState<string | null>(null)
  const root = useRef<HTMLDivElement>(null)
  const { text, order } = useMemo(() => linkifyCitations(m.content, m.citations ?? []), [m.content, m.citations])
  const byId = useMemo(() => new Map(order.map((c, i) => [c.id, { c, n: i + 1 }])), [order])

  const copy = async () => {
    const plain = m.content.replace(/\[S\d+\]/g, '').replace(/ +([.,;:])/g, '$1')
    try { await navigator.clipboard.writeText(plain); setCopied(true); setTimeout(() => setCopied(false), 1400) } catch { toast('Copy failed') }
  }
  const rate = (r: 'up' | 'down') => {
    onFeedback(m.id, r)
    void sendFeedback(r).catch(() => {})
    toast('Thanks for the feedback')
  }
  const clickCite = (id: string) => {
    const hit = byId.get(id)
    if (hit && isSafeUrl(hit.c.url)) { openUrl(hit.c.url); return }
    root.current?.querySelector(`#src-${id}`)?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
    setFlash(id); setTimeout(() => setFlash(null), 1200)
  }

  return (
    <div className="msg msg-ai" ref={root}>
      <span className="assistant-label">Esolv</span>
      <div>
        {m.error ? (
          <div className="err" role="alert"><IconAlert size={17} /><span>{m.error}</span></div>
        ) : (
          <>
            {m.status && m.streaming && (
              <div className="status-line"><span>{m.status}</span><span className="dots"><i /><i /><i /></span></div>
            )}
            <WorkingSources m={m} />
            {m.content && (
              <div className="prose" aria-live="polite">
                <Markdown
                  remarkPlugins={[remarkGfm]}
                  urlTransform={(u) => (u.startsWith('esolv-cite:') || isSafeUrl(u) ? u : '')}
                  components={{
                    a: ({ href, children }) => {
                      if (href?.startsWith('esolv-cite:')) {
                        const id = href.slice(11)
                        const hit = byId.get(id)
                        return <button className="cite" onClick={() => clickCite(id)} title={hit ? `${hit.c.title}${hit.c.section ? ' — ' + hit.c.section : ''}` : 'Source'} aria-label={`Source ${children}`}>{children}</button>
                      }
                      return <a href={href} onClick={(e) => { e.preventDefault(); if (href) openUrl(href) }}>{children}</a>
                    },
                  }}
                >{text}</Markdown>
                {m.streaming && <span className="caret" />}
              </div>
            )}
            {!m.streaming && order.length > 0 && (
              <div className="sources">
                <div className="sources-label">Sources</div>
                {order.map((c, i) => <SourceRow key={c.id} c={c} n={i + 1} flash={flash === c.id} />)}
              </div>
            )}
            <Verification m={m} />
            {!m.streaming && (m.flags?.length ?? 0) > 0 && (
              <div className="notes" style={{ background: 'var(--surface-3)', color: 'var(--muted)' }}><IconShield size={13} style={{ verticalAlign: -2 }} /> {m.flags![0]}</div>
            )}
            {!m.streaming && m.content && (
              <div className={`actions${m.feedback ? ' keep' : ''}`}>
                <button className="icon-btn" onClick={copy} title="Copy answer" aria-label="Copy answer">{copied ? <IconCheck size={16} /> : <IconCopy size={16} />}</button>
                <button className={`icon-btn${m.feedback === 'up' ? ' on' : ''}`} onClick={() => rate('up')} title="Helpful" aria-label="Helpful" aria-pressed={m.feedback === 'up'}><IconThumbUp size={16} /></button>
                <button className={`icon-btn${m.feedback === 'down' ? ' on' : ''}`} onClick={() => rate('down')} title="Not helpful" aria-label="Not helpful" aria-pressed={m.feedback === 'down'}><IconThumbDown size={16} /></button>
                {isLast && <button className="icon-btn" onClick={onRegenerate} title="Try again" aria-label="Try again"><IconRefresh size={16} /></button>}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}

export function UserMessage({ m }: { m: Message }) {
  return (
    <div className="msg msg-user">
      {m.pageTitle && <div className="page-tag" style={{ justifyContent: 'flex-end' }}><IconDoc size={13} /><span>{m.pageTitle}</span></div>}
      {m.files && m.files.length > 0 && (
        <div className="attach-row">{m.files.map((f, i) => (
          <div className="chip-file sent" key={i}><span className="ft">{(f.name.split('.').pop() ?? '').toUpperCase().slice(0, 4)}</span><span className="fn"><b>{f.name}</b><span>{formatSize(f.size)}</span></span></div>
        ))}</div>
      )}
      {m.images && m.images.length > 0 && (
        <div className="attach-row">{m.images.map((src, i) => <img key={i} src={src} alt={`Attached image ${i + 1}`} />)}</div>
      )}
      <div className="bubble">{m.content}</div>
    </div>
  )
}
