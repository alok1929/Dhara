import { withAuthHeaders } from './auth'
import { withLlmKeyHeaders } from './llmKey'

export async function runConsoleTableAiSearch(prompt, tables) {
  const res = await fetch(
    '/api/console/tables/ai-search',
    withLlmKeyHeaders(withAuthHeaders({
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt, tables }),
    })),
  )
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    const detail = typeof body.detail === 'string' ? body.detail : 'AI search failed'
    throw new Error(detail)
  }
  return res.json()
}

export async function runPdfJobTableAiSearch(jobId, prompt, tables) {
  const res = await fetch(
    `/api/pdf/jobs/${encodeURIComponent(jobId)}/tables/ai-search`,
    withLlmKeyHeaders(withAuthHeaders({
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt, tables }),
    })),
  )
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    const detail = typeof body.detail === 'string' ? body.detail : 'AI search failed'
    throw new Error(detail)
  }
  return res.json()
}
