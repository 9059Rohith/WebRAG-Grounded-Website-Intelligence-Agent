import { useEffect, useRef, useState } from 'react'
import { Github, Menu } from 'lucide-react'
import { request } from './api'
import type { Answer, Stats } from './api'
import { readHistory, saveHistory } from './history'
import type { HistoryItem } from './history'
import Sidebar from './components/Sidebar'
import Composer from './components/Composer'
import AnswerPanel from './components/AnswerPanel'
import EvidencePanel from './components/EvidencePanel'
import SourceGraph from './components/SourceGraph'
import HowItWorks from './components/HowItWorks'

function readMotionPreference() {
  try { return localStorage.getItem('webrag.motion.v1') !== 'off' } catch { return true }
}
function Brand() {
  return <span className="brand"><svg width="34" height="34" viewBox="0 0 34 34" fill="none" aria-hidden="true"><path d="m17 6-10 19h20L17 6Z" stroke="#64ad83" strokeWidth="1.3" /><g fill="#4bac7a"><circle cx="17" cy="6" r="5"/><circle cx="7" cy="25" r="5"/><circle cx="27" cy="25" r="5"/></g></svg>WebRAG</span>
}

export default function App() {
  const [stats, setStats] = useState<Stats | null>(null)
  const [statsError, setStatsError] = useState('')
  const [question, setQuestion] = useState('')
  const [answer, setAnswer] = useState<Answer | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [history, setHistory] = useState(readHistory)
  const [active, setActive] = useState<string | null>(null)
  const [selected, setSelected] = useState<number | null>(null)
  const [railOpen, setRailOpen] = useState(false)
  const [evidenceOpen, setEvidenceOpen] = useState(false)
  const [howOpen, setHowOpen] = useState(false)
  const [motionEnabled, setMotionEnabled] = useState(readMotionPreference)
  const [reducedMotion, setReducedMotion] = useState(() => window.matchMedia('(prefers-reduced-motion: reduce)').matches)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const controller = useRef<AbortController | null>(null)
  const sessionAnswers = useRef(new Map<string, Answer>())
  const motion = motionEnabled && !reducedMotion

  const loadStats = async (signal?: AbortSignal) => {
    setStatsError('')
    try { setStats(await request<Stats>('/v1/stats', { signal })) } catch (err) { if (!signal?.aborted) setStatsError(err instanceof Error ? err.message : 'Unable to load the library.') }
  }
  useEffect(() => {
    const statsController = new AbortController()
    void loadStats(statsController.signal)
    const preference = window.matchMedia('(prefers-reduced-motion: reduce)')
    const change = () => setReducedMotion(preference.matches)
    preference.addEventListener('change', change)
    return () => { statsController.abort(); controller.current?.abort(); preference.removeEventListener('change', change) }
  }, [])
  useEffect(() => { saveHistory(history) }, [history])

  const cancel = () => { controller.current?.abort(); controller.current = null; setBusy(false) }
  const newConversation = () => {
    cancel(); setQuestion(''); setAnswer(null); setError(''); setActive(null); setSelected(null); setRailOpen(false); setEvidenceOpen(false); inputRef.current?.focus()
  }
  const selectHistory = (item: HistoryItem) => {
    cancel(); setQuestion(item.question); setAnswer(sessionAnswers.current.get(item.id) ?? null); setError(''); setActive(item.id); setSelected(null); setRailOpen(false); inputRef.current?.focus()
  }
  const ask = async () => {
    const value = question.trim()
    if (busy || !value) return
    if (value.length > 500) { setError('Keep your question within 500 characters.'); return }
    const current = new AbortController()
    controller.current = current
    setBusy(true); setError(''); setAnswer(null); setSelected(null)
    let timedOut = false
    const timer = window.setTimeout(() => { timedOut = true; current.abort() }, 120_000)
    try {
      const result = await request<Answer>('/v1/ask', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ question: value }), signal: current.signal })
      if (current.signal.aborted) return
      const item = { id: crypto.randomUUID(), question: value, at: Date.now() }
      sessionAnswers.current.set(item.id, result)
      setHistory(previous => [item, ...previous.filter(entry => entry.question !== value)].slice(0, 12))
      setActive(item.id); setAnswer(result)
    } catch (err) {
      if (!current.signal.aborted || timedOut) setError(timedOut ? 'This request took too long. Please try again.' : err instanceof Error ? err.message : 'Unable to connect. Please try again.')
    } finally {
      window.clearTimeout(timer)
      if (controller.current === current) { controller.current = null; setBusy(false) }
    }
  }
  const selectCitation = (index: number) => {
    setSelected(index); setEvidenceOpen(true)
    requestAnimationFrame(() => {
      const node = document.getElementById(`evidence-${index}`)
      node?.scrollIntoView({ block: 'nearest', behavior: motion ? 'smooth' : 'instant' })
      node?.focus({ preventScroll: true })
    })
  }
  const toggleMotion = () => {
    const next = !motionEnabled
    setMotionEnabled(next)
    try { localStorage.setItem('webrag.motion.v1', next ? 'on' : 'off') } catch { /* Storage is optional. */ }
  }
  return <div className={`app-shell ${motion ? 'motion-on' : 'motion-off'}`}>
    <a className="skip-link" href="#workspace">Skip to workspace</a>
    <header className="app-header"><div className="brand-area"><button className="icon-button menu-button" onClick={() => setRailOpen(true)} aria-label="Open library" aria-expanded={railOpen}><Menu size={21} /></button><Brand /></div><nav className="primary-nav" aria-label="Main navigation"><button className="nav-item active" onClick={() => { setHowOpen(false); inputRef.current?.focus() }}>Workspace</button><button className={`nav-item ${howOpen ? 'dialog-active' : ''}`} onClick={() => setHowOpen(true)}>How it works</button></nav><div className="header-utilities"><a className="github-link" href="https://github.com/9059Rohith/WebRAG-Grounded-Website-Intelligence-Agent" target="_blank" rel="noreferrer"><Github size={22} /><span>GitHub</span></a><i /><button className="motion-toggle" onClick={toggleMotion} aria-pressed={motion} title={reducedMotion ? 'Your device prefers reduced motion' : 'Toggle interface motion'}><span className={`status-dot ${motion ? '' : 'off'}`} />Motion {motion ? 'on' : 'off'}</button></div></header>
    <div className="workspace-grid"><Sidebar stats={stats} statsError={statsError} history={history} active={active} open={railOpen} onSelect={selectHistory} onNew={newConversation} onClose={() => setRailOpen(false)} onRetry={() => void loadStats()} /><main className="workspace-main" id="workspace"><div className="intro"><SourceGraph motion={motion} /><h1 className="intro-title"><span>Every answer,</span><span>rooted in a source.</span></h1><p className="intro-subtitle">Ask naturally. Explore the exact website evidence behind every answer.</p></div><div className="workspace-content"><Composer question={question} busy={busy} inputRef={inputRef} onChange={setQuestion} onSubmit={() => void ask()} /><AnswerPanel answer={answer} busy={busy} error={error} onRetry={() => void ask()} onCitation={selectCitation} /></div></main><EvidencePanel answer={answer} busy={busy} selected={selected} open={evidenceOpen} onToggle={() => setEvidenceOpen(value => !value)} /></div>
    {howOpen ? <HowItWorks onClose={() => setHowOpen(false)} /> : null}
  </div>
}
