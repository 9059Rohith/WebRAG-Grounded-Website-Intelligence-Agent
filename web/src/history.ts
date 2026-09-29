export type HistoryItem = { id: string; question: string; at: number }
const key = 'webrag.questions.v1'

export function readHistory(): HistoryItem[] {
  try {
    const value: unknown = JSON.parse(localStorage.getItem(key) ?? '[]')
    if (!Array.isArray(value)) return []
    return value.filter((item): item is HistoryItem =>
      typeof item?.id === 'string' && typeof item?.question === 'string' && item.question.length <= 500 && typeof item?.at === 'number',
    ).slice(0, 12)
  } catch { return [] }
}

export function saveHistory(items: HistoryItem[]) {
  try { localStorage.setItem(key, JSON.stringify(items)) } catch { /* Private browsing can disable storage. */ }
}

export function relativeTime(at: number) {
  const minutes = Math.max(0, Math.floor((Date.now() - at) / 60_000))
  if (minutes < 1) return 'Just now'
  if (minutes < 60) return `${minutes} minute${minutes === 1 ? '' : 's'} ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours} hour${hours === 1 ? '' : 's'} ago`
  const days = Math.floor(hours / 24)
  return `${days} day${days === 1 ? '' : 's'} ago`
}
