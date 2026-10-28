import { withAuthHeaders } from './auth'
import { withLlmKeyHeaders } from './llmKey'

export async function postStageCommand(command, lines) {
  const res = await fetch(
    '/api/console/stage-command',
    withLlmKeyHeaders(withAuthHeaders({
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ command, lines: lines || [] }),
    })),
  )
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    const detail = typeof body.detail === 'string' ? body.detail : 'Chat request failed'
    throw new Error(detail)
  }
  return res.json()
}
