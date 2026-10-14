import { withAuthHeaders } from './auth'

export async function createConsoleChatSession({ batchId, pdfJobId } = {}) {
  const res = await fetch(
    '/api/console/chat/sessions',
    withAuthHeaders({
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        batch_id: batchId || null,
        pdf_job_id: pdfJobId || null,
      }),
    }),
  )
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(typeof body.detail === 'string' ? body.detail : 'Could not create chat session')
  }
  return res.json()
}

export async function fetchConsoleChatSession(sessionId) {
  const res = await fetch(
    `/api/console/chat/sessions/${encodeURIComponent(sessionId)}`,
    withAuthHeaders(),
  )
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(typeof body.detail === 'string' ? body.detail : 'Could not load chat session')
  }
  return res.json()
}

export async function saveConsoleChatMessages(sessionId, messages) {
  const res = await fetch(
    `/api/console/chat/sessions/${encodeURIComponent(sessionId)}/messages`,
    withAuthHeaders({
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ messages }),
    }),
  )
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(typeof body.detail === 'string' ? body.detail : 'Could not save chat messages')
  }
  return res.json()
}

export async function linkConsoleChatSession(sessionId, { batchId, pdfJobId } = {}) {
  const res = await fetch(
    `/api/console/chat/sessions/${encodeURIComponent(sessionId)}`,
    withAuthHeaders({
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        batch_id: batchId ?? undefined,
        pdf_job_id: pdfJobId ?? undefined,
      }),
    }),
  )
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(typeof body.detail === 'string' ? body.detail : 'Could not update chat session')
  }
  return res.json()
}
