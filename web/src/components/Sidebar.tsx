import { ArrowUpRight, ChevronRight, Clock3, FileText, Plus, X } from 'lucide-react'
import { useEffect, useRef } from 'react'
import type { Stats } from '../api'
import { safeUrl } from '../api'
import type { HistoryItem } from '../history'
import { relativeTime } from '../history'

type Props = {
  stats: Stats | null; statsError: string; history: HistoryItem[]; active: string | null; open: boolean
  onSelect: (item: HistoryItem) => void; onNew: () => void; onClose: () => void; onRetry: () => void
}
export default function Sidebar({ stats, statsError, history, active, open, onSelect, onNew, onClose, onRetry }: Props) {
  const panel = useRef<HTMLElement>(null)
  useEffect(() => {
    if (!open) return
    panel.current?.querySelector('button')?.focus()
    const keydown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') { event.preventDefault(); onClose(); return }
      if (event.key !== 'Tab') return
      const nodes = panel.current?.querySelectorAll<HTMLElement>('a[href], button:not(:disabled)')
      if (!nodes?.length) return
      const first = nodes[0], last = nodes[nodes.length - 1]
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus() }
      if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus() }
    }
    document.addEventListener('keydown', keydown)
    return () => document.removeEventListener('keydown', keydown)
  }, [open, onClose])
  const url = stats ? safeUrl(stats.start_url) : undefined
  const parsedUrl = url ? new URL(url) : null
  const siteLabel = parsedUrl ? parsedUrl.host + (parsedUrl.host === 'docs.python.org' ? '/3/' : parsedUrl.pathname.replace(/\/$/, '')) : 'Connecting to the index…'
  return <>
    {open ? <button className="rail-backdrop" aria-label="Close library" onClick={onClose} /> : null}
    <aside ref={panel} className={`library-rail ${open ? 'is-open' : ''}`} role={open ? 'dialog' : undefined} aria-modal={open ? true : undefined} aria-label="Your library">
      <div className="rail-title"><h2>Your library</h2><button className="icon-button mobile-close" aria-label="Close library" onClick={onClose}><X size={20} /></button></div>
      <a className="library-source" href={url} target="_blank" rel="noreferrer">
        <FileText size={21} /><div><strong>{parsedUrl?.host === 'docs.python.org' ? 'Python documentation' : stats ? 'Website documentation' : 'Website library'}</strong><span>{siteLabel}</span></div><ChevronRight size={14} />
      </a>
      <div className="library-stats" aria-live="polite">{stats ? <><span>{stats.pages.toLocaleString()} pages</span><i /><span>{stats.chunks.toLocaleString()} passages</span></> : statsError ? <button className="text-button" onClick={onRetry}>Index unavailable · Retry <ArrowUpRight size={14} /></button> : <span>Loading library details…</span>}</div>
      <div className="rail-divider" />
      <h2 className="recent-title"><Clock3 size={20} /> Recent questions</h2>
      <div className="history-list">{history.length ? history.map(item => <button className={`history-item ${active === item.id ? 'active' : ''}`} key={item.id} onClick={() => onSelect(item)}><span>{item.question}</span><small>{relativeTime(item.at)}</small></button>) : <p className="history-empty">Your questions will appear here.</p>}</div>
      <button className="new-conversation" onClick={onNew}><Plus size={22} /><span>New conversation</span></button>
    </aside>
  </>
}
