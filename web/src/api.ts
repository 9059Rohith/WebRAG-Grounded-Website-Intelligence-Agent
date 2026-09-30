export type Source = { url: string; title: string; evidence: string; chunk_id: string }
export type Answer = {
  answer: string
  answerable: boolean
  sources: Source[]
  usage: { input_tokens: number; output_tokens: number; embedding_tokens: number; estimated_usd: number; token_source?: string; provider?: string }
  timings_ms: Record<string, number>
  cached: boolean
  mode: string
  request_id?: string
  retrieved_urls?: string[]
  attempts?: number
  retrieval_score?: number
}
export type Stats = {
  pages: number
  chunks: number
  start_url: string
  provider: string
  mode: string
}

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init)
  let data
  try { data = await response.json() } catch {
    throw new Error('The service did not return a response. Please try again.')
  }
  if (!response.ok) {
    throw new Error(data.error?.message ?? 'The request could not be completed. Please try again.')
  }
  return data as T
}

export function safeUrl(value: string): string | undefined {
  try {
    const url = new URL(value)
    return ['https:', 'http:'].includes(url.protocol) ? url.href : undefined
  } catch { return undefined }
}
