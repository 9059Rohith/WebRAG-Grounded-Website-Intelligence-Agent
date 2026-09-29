import { ArrowRight, Link2, LoaderCircle } from 'lucide-react'
import type { RefObject } from 'react'

const suggestions = [
  { label: 'Lists & tuples', question: 'How do Python lists and tuples differ?' },
  { label: 'String formatting', question: 'How does string formatting work in Python?' },
  { label: 'A question the site can’t answer', question: 'What is the weather in Paris today?' },
]
type Props = {
  question: string; busy: boolean; inputRef: RefObject<HTMLTextAreaElement | null>
  onChange: (question: string) => void; onSubmit: () => void
}
export default function Composer({ question, busy, inputRef, onChange, onSubmit }: Props) {
  return <>
    <form className={`composer ${busy ? 'is-busy' : ''}`} onSubmit={event => { event.preventDefault(); onSubmit() }}>
      <label className="sr-only" htmlFor="question">Ask a question about your website library</label>
      <textarea id="question" ref={inputRef} value={question} maxLength={500} onChange={event => onChange(event.target.value)} placeholder="What would you like to understand?" rows={2} onKeyDown={event => { if (event.key === 'Enter' && (event.metaKey || event.ctrlKey)) { event.preventDefault(); onSubmit() } }} aria-describedby="question-hint" />
      <div className="composer-bottom"><span id="question-hint"><Link2 size={21} /> Website sources only</span><div className="composer-actions">{question.length > 400 ? <small>{question.length}/500</small> : null}<button className="ask-button" type="submit" disabled={busy || !question.trim()}>{busy ? 'Working…' : 'Ask question'}{busy ? <LoaderCircle size={18} className="spinner" /> : <ArrowRight size={20} />}</button></div></div>
    </form>
    <div className="suggestions" aria-label="Suggested questions">{suggestions.map(item => <button key={item.label} disabled={busy} onClick={() => { onChange(item.question); inputRef.current?.focus() }}>{item.label}</button>)}</div>
  </>
}
