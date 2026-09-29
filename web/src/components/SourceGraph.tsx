import { useEffect, useRef } from 'react'

export default function SourceGraph({ motion }: { motion: boolean }) {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!motion) return
    let frame = 0
    const move = (event: PointerEvent) => {
      if (event.pointerType === 'touch') return
      cancelAnimationFrame(frame)
      frame = requestAnimationFrame(() => {
        ref.current?.style.setProperty('--graph-x', `${(event.clientX / window.innerWidth - .5) * 12}px`)
        ref.current?.style.setProperty('--graph-y', `${(event.clientY / window.innerHeight - .5) * 8}px`)
      })
    }
    window.addEventListener('pointermove', move, { passive: true })
    return () => {
      cancelAnimationFrame(frame)
      window.removeEventListener('pointermove', move)
      ref.current?.style.removeProperty('--graph-x')
      ref.current?.style.removeProperty('--graph-y')
    }
  }, [motion])
  return <div className="source-graph" ref={ref} aria-hidden="true">
    <svg viewBox="0 0 620 160" fill="none">
      <g stroke="#b9d9c5" strokeWidth=".8"><path d="m44 69 157 33 162-80 141 34 101 86"/><path d="m201 102 210 7 93-53M363 22l48 87"/></g>
      <g fill="#97cfa9"><circle cx="44" cy="69" r="6" opacity=".6"/><circle cx="201" cy="102" r="8" opacity=".65"/><circle cx="363" cy="22" r="6.5"/><circle cx="411" cy="109" r="5" opacity=".5"/><circle cx="504" cy="56" r="6"/><circle cx="605" cy="142" r="8" opacity=".7"/></g>
    </svg>
  </div>
}
