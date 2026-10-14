import { withAuthHeaders } from './auth'
import { withLlmKeyHeaders } from './llmKey'

export async function runConsoleTableAiChat(prompt, tables, { conversation } = {}) {
  const body = { prompt, tables }
  if (conversation?.length) body.conversation = conversation
  const res = await fetch(
    '/api/console/tables/ai-chat',
    withLlmKeyHeaders(withAuthHeaders({
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })),
  )
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    const detail = typeof body.detail === 'string' ? body.detail : 'Chat request failed'
    throw new Error(detail)
  }
  return res.json()
}

export async function runPdfJobTableAiChat(jobId, prompt, tables, { conversation } = {}) {
  const body = { prompt, tables }
  if (conversation?.length) body.conversation = conversation
  const res = await fetch(
    `/api/pdf/jobs/${encodeURIComponent(jobId)}/tables/ai-chat`,
    withLlmKeyHeaders(withAuthHeaders({
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })),
  )
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    const detail = typeof body.detail === 'string' ? body.detail : 'Chat request failed'
    throw new Error(detail)
  }
  return res.json()
}
