import { ArrowUpRight, FileText, Link2, Search, X } from 'lucide-react'
import { useEffect, useRef } from 'react'

export default function HowItWorks({ onClose }: { onClose: () => void }) {
  const ref = useRef<HTMLDialogElement>(null)
  useEffect(() => { ref.current?.showModal() }, [])
  return <dialog className="how-dialog" ref={ref} onCancel={onClose} onClick={event => { if (event.target === event.currentTarget) onClose() }}>
    <button className="icon-button dialog-close" onClick={onClose} aria-label="Close how it works"><X size={20} /></button>
    <h2>Follow the answer<br />back to its source.</h2>
    <div className="how-step"><Search size={22} /><div><h3>Ask naturally</h3><p>Ask a question about the indexed website. WebRAG searches its passages for relevant evidence.</p></div></div>
    <div className="how-step"><FileText size={22} /><div><h3>Read a grounded answer</h3><p>Each supported statement cites a passage. If the website cannot support an answer, WebRAG says so.</p></div></div>
    <div className="how-step"><Link2 size={22} /><div><h3>Explore the original</h3><p>Select a citation to read the exact evidence, or follow the source link to the website.</p></div></div>
    <p className="how-note">Recent questions are saved on this device. Answers stay in this session. Use Ctrl / ⌘ + Enter to ask.</p>
    <a className="view-source" href="https://github.com/9059Rohith/WebRAG-Grounded-Website-Intelligence-Agent" target="_blank" rel="noreferrer">Explore the project <ArrowUpRight size={16} /></a>
  </dialog>
}
