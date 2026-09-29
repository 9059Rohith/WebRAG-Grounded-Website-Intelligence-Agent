import { ArrowRight, ExternalLink, FileText, Link2 } from 'lucide-react'
import type { Answer } from '../api'
import { safeUrl } from '../api'

export default function EvidencePanel({ answer, busy, selected, open, onToggle }: { answer: Answer | null; busy: boolean; selected: number | null; open: boolean; onToggle: () => void }) {
  return <aside className={`evidence-rail ${open ? 'is-open' : ''}`} aria-labelledby="evidence-title">
    <div className="evidence-title-row"><h2 id="evidence-title"><FileText size={27} /> Website evidence</h2><button className="evidence-toggle" onClick={onToggle} aria-expanded={open} aria-controls="evidence-list">{open ? 'Hide' : 'Show'}{answer?.sources.length ? ` (${answer.sources.length})` : ''}</button></div>
    <div className="evidence-list" id="evidence-list">{answer?.sources.length && !busy ? answer.sources.map((source, index) => {
      const href = safeUrl(source.url)
      return <article className={`evidence-item reveal ${selected === index ? 'selected' : ''}`} key={`${source.chunk_id}-${index}`} id={`evidence-${index}`} tabIndex={-1}>
        <div className="evidence-source-heading"><span className="source-number">[{index + 1}]</span><h3>{source.title}</h3></div>
        <a className="source-url" href={href} target="_blank" rel="noreferrer">{source.url}<ExternalLink size={15} /></a>
        <blockquote>“{source.evidence}”</blockquote>
        {href ? <a className="view-source" href={href} target="_blank" rel="noreferrer">View source <ArrowRight size={17} /></a> : null}
      </article>
    }) : <div className="evidence-empty"><div className="evidence-empty-mark"><FileText size={35} strokeWidth={1.2} /><Link2 size={18} /></div><h3>{busy ? 'Looking for supporting passages' : answer && !answer.answerable ? 'No supporting evidence' : 'The source, alongside the answer.'}</h3><p>{busy ? 'Matching your question with the indexed website.' : answer && !answer.answerable ? 'The indexed website does not support an answer to this question.' : 'When you ask a question, the exact website passages will appear here for you to explore.'}</p></div>}</div>
  </aside>
}
