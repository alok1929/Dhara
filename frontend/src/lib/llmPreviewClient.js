import { withAuthHeaders } from './auth'
import { withLlmKeyHeaders } from './llmKey'

/**
 * Notebook-style chat entrypoint — POST /api/llm_preview/jobs/{jobId}/llm_input
 */
export async function postLlmInput(jobId, {
  userRequest,
  stage = 'preview',
  prompt = null,
  tables = null,
  confirmDelete = false,
  confirmApplyGroup = false,
  refresh = false,
  applyGroup = null,
} = {}) {
  if (!jobId) throw new Error('jobId is required')
  const body = {
    stage,
    confirm_delete: Boolean(confirmDelete),
    confirm_apply_group: Boolean(confirmApplyGroup),
    refresh: Boolean(refresh),
  }
  if (userRequest) body.user_request = userRequest
  if (prompt) body.prompt = prompt
  if (Array.isArray(tables) && tables.length) body.tables = tables
  if (applyGroup && typeof applyGroup === 'object') body.apply_group = applyGroup

  const res = await fetch(
    `/api/llm_preview/jobs/${encodeURIComponent(jobId)}/llm_input`,
    withLlmKeyHeaders(withAuthHeaders({
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })),
  )
  if (!res.ok) {
    const errBody = await res.json().catch(() => ({}))
    const detail = typeof errBody.detail === 'string' ? errBody.detail : 'Chat request failed'
    throw new Error(detail)
  }
  return res.json()
}
