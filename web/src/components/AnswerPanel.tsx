import { Check, Copy, FileText, LoaderCircle, RotateCcw, ShieldCheck } from 'lucide-react'
import { useEffect, useState } from 'react'
import type { Answer } from '../api'
import { copyText } from '../clipboard'

function AnswerText({ text, sources, onCitation }: { text: string; sources: number; onCitation: (n: number) => void }) {
  return text.split(/\n\s*\n/).map((paragraph, index) => <p key={index}>{paragraph.split(/(\[\d+\])/g).map((part, i) => {
    const match = /^\[(\d+)\]$/.exec(part)
    const n = match ? Number(match[1]) : 0
    return n > 0 && n <= sources ? <button className="citation" key={i} onClick={() => onCitation(n - 1)} aria-label={`Read supporting passage ${n}`}>[{n}]</button> : part
  })}</p>)
}

function LoadingAnswer() {
  const [elapsed, setElapsed] = useState(0)
  useEffect(() => {
    const timer = window.setInterval(() => setElapsed(n => n + 1), 1000)
    return () => window.clearInterval(timer)
  }, [])
  return <div className="loading-answer"><LoaderCircle size={20} className="spinner" /><div><p>{elapsed < 8 ? 'Finding evidence and preparing your answer…' : 'Still working on your answer…'}</p><small>{elapsed}s elapsed</small></div></div>
}

export default function AnswerPanel({ answer, busy, error, onRetry, onCitation }: { answer: Answer | null; busy: boolean; error: string; onRetry: () => void; onCitation: (n: number) => void }) {
  const [copied, setCopied] = useState(false)
  const [copyError, setCopyError] = useState(false)
  const [copiedWithSources, setCopiedWithSources] = useState(false)
  useEffect(() => { setCopied(false); setCopiedWithSources(false); setCopyError(false) }, [answer])
  useEffect(() => {
    if (!copied) return
    const timer = window.setTimeout(() => setCopied(false), 2500)
    return () => window.clearTimeout(timer)
  }, [copied])
  const copy = async () => {
    if (!answer) return
    try { await copyText(answer.answer); setCopied(true); setCopyError(false) } catch { setCopyError(true) }
  }
  const copyWithSources = async () => {
    if (!answer) return
    const sources = answer.sources.map((source, index) => `${index + 1}. ${source.title}\n${source.url}\n“${source.evidence}”`).join('\n\n')
    try {
      await copyText(`${answer.answer}${sources ? `\n\nSources\n${sources}` : ''}`)
      setCopiedWithSources(true)
      setCopyError(false)
    } catch { setCopyError(true) }
  }
  const totalMs = answer?.timings_ms.total ?? answer?.timings_ms.total_ms
  const tokens = answer ? answer.usage.input_tokens + answer.usage.output_tokens + answer.usage.embedding_tokens : 0
  const retrievedPages = answer ? new Set(answer.retrieved_urls ?? []).size : 0
  const timings = answer ? [
    ['Retrieval', answer.timings_ms.retrieval],
    ['Generation', answer.timings_ms.generation],
    ['Verification', answer.timings_ms.verification],
  ].filter((row): row is [string, number] => typeof row[1] === 'number') : []
  return <section className="answer-section" aria-labelledby="answer-title" aria-busy={busy}>
    <div className="section-heading"><h2 id="answer-title"><FileText size={25} /> Answer</h2>{answer && !busy ? <button className="copy-button" onClick={copy}>{copied ? <Check size={16} /> : <Copy size={16} />}{copied ? 'Copied' : 'Copy'}</button> : null}</div>
    <div className="answer-content" aria-live="polite">
      {busy ? <LoadingAnswer /> : error ? <div className="request-error"><p>{error}</p><button className="text-button" onClick={onRetry}><RotateCcw size={15} /> Try again</button></div> : answer ? <div className={`answer-result reveal ${!answer.answerable ? 'not-answerable' : ''}`} key={answer.request_id ?? answer.answer}><AnswerText text={answer.answer} sources={answer.sources.length} onCitation={onCitation} />{!answer.answerable ? <small className="refusal-note">Try asking about a topic covered in your website library.</small> : null}</div> : <p className="answer-empty">A clear answer. The passages that support it.<br /><span>Ask your first question to begin.</span></p>}
    </div>
    {copyError ? <small role="status">Copy is unavailable. Select the answer text to copy it.</small> : null}
    {answer && !busy && !error ? <div className="answer-meta"><span>{answer.sources.length} supporting passage{answer.sources.length === 1 ? '' : 's'}{typeof totalMs === 'number' ? ` · ${(totalMs / 1000).toFixed(1)} s` : ''}{answer.cached ? ' · Cached' : ''}</span><details><summary>Usage</summary><div>{tokens.toLocaleString()} {answer.usage.token_source?.startsWith('estimated') ? 'estimated ' : ''}tokens · ${answer.usage.estimated_usd.toFixed(6)} estimated new cost{answer.mode === 'extractive' ? <span>Extractive answer from the website</span> : null}</div></details></div> : null}
    {answer && !busy && !error ? <details className="grounding-trail"><summary><ShieldCheck size={18} /><span>Inspect the answer trail</span><small>Retrieval · evidence · decision</small></summary><div className="trail-body"><ol><li><strong>Search</strong><span>{retrievedPages ? `${retrievedPages} distinct website page${retrievedPages === 1 ? '' : 's'} retrieved` : 'No supporting website page returned'}</span></li><li><strong>Evidence</strong><span>{answer.sources.length ? `${answer.sources.length} exact passage${answer.sources.length === 1 ? '' : 's'} attached to this answer` : 'No passage cited; the answer was refused'}</span></li><li><strong>Decision</strong><span>{answer.answerable ? 'Website-supported answer' : 'Insufficient website evidence'}{typeof answer.attempts === 'number' ? ` · ${answer.attempts} attempt${answer.attempts === 1 ? '' : 's'}` : ''}</span></li></ol>{timings.length ? <div className="trail-timings" aria-label="Processing time by stage">{timings.map(([label, ms]) => <span key={label}>{label} <strong>{(ms / 1000).toFixed(1)} s</strong></span>)}</div> : null}<button className="copy-sources-button" onClick={() => void copyWithSources()} disabled={!answer.sources.length}>{copiedWithSources ? <Check size={16} /> : <Copy size={16} />}{copiedWithSources ? 'Copied with sources' : 'Copy answer with sources'}</button></div></details> : null}
  </section>
}
