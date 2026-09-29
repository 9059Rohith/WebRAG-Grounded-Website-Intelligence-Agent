function copyWithSelection(text: string): boolean {
  const active = document.activeElement as HTMLElement | null
  const selection = window.getSelection()
  const ranges = selection ? Array.from({ length: selection.rangeCount }, (_, index) => selection.getRangeAt(index).cloneRange()) : []
  const field = document.createElement('textarea')
  field.value = text
  field.readOnly = true
  field.style.cssText = 'position:fixed;left:0;top:0;opacity:0;pointer-events:none;'
  document.body.append(field)
  field.select()
  let copied = false
  try { copied = document.execCommand('copy') } catch { /* Fall through to readable failure feedback. */ }
  field.remove()
  active?.focus({ preventScroll: true })
  if (selection) { selection.removeAllRanges(); ranges.forEach(range => selection.addRange(range)) }
  return copied
}

export async function copyText(text: string) {
  if (navigator.clipboard) {
    let timer = 0
    try {
      await Promise.race([
        navigator.clipboard.writeText(text),
        new Promise<never>((_, reject) => { timer = window.setTimeout(() => reject(new Error('Clipboard unavailable')), 700) }),
      ])
      return
    } catch { /* Browser focus/permissions may block the asynchronous clipboard. */ }
    finally { window.clearTimeout(timer) }
  }
  if (!copyWithSelection(text)) throw new Error('Clipboard unavailable')
}
