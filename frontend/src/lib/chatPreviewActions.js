import { withAuthHeaders } from './auth'

/** User asked to list tables that need human review. */
export function isReviewNeededIntent(text) {
  const t = String(text || '').trim().toLowerCase()
  if (!t) return false
  return (
    /\b(need(s)?\s+(a\s+)?(human\s+)?review|review\s+needed|needs?\s+review)\b/i.test(t)
    || /\b(human\s+review|tables?\s+to\s+review|uncertain\s+tables?)\b/i.test(t)
    || /\b(which|show|list|find)\b.*\b(review|uncertain|flagged)\b/i.test(t)
  )
}

export function normalizePreviewTableRow(table, { pdfJob = false } = {}) {
  if (!table || typeof table !== 'object') return null
  const id = String(
    pdfJob
      ? (table.table_id ?? table._uid ?? '')
      : (table._uid ?? table.table_id ?? ''),
  )
  if (!id) return null
  const title = String(
    table.title
    || table.banner_table_id
    || table.id
    || `Table ${id}`,
  ).trim()
  return {
    id,
    title,
    page: table.page ?? null,
    reason: String(table.human_review_reason || table.review_reason || '').trim() || null,
    filename: table.filename || null,
    human_review_needed: Boolean(table.human_review_needed),
  }
}

export function filterReviewNeededTables(tables, { pdfJob = false } = {}) {
  return (tables || [])
    .filter((t) => {
      if (t?.human_review_needed) return true
      const status = String(t?.semantic_status || '').toLowerCase()
      return status === 'needs_review' || status === 'uncertain' || status === 'uncertain_title'
    })
    .map((t) => normalizePreviewTableRow(t, { pdfJob }))
    .filter(Boolean)
}

export function rowsFromMatchedTables(tables, ids, { pdfJob = false } = {}) {
  const idSet = new Set((ids || []).map(String))
  return (tables || [])
    .filter((t) => {
      const candidates = pdfJob
        ? [t?.table_id, t?._uid, t?.id]
        : [t?._uid, t?.table_id, t?.id]
      return candidates.some((value) => value != null && value !== '' && idSet.has(String(value)))
    })
    .map((t) => normalizePreviewTableRow(t, { pdfJob }))
    .filter(Boolean)
}

export async function deletePdfJobTables(jobId, tableIds) {
  const ids = [...new Set((tableIds || []).map(String).filter(Boolean))]
  if (!jobId || !ids.length) {
    throw new Error('No tables selected to delete')
  }
  const res = await fetch(`/api/pdf/jobs/${encodeURIComponent(jobId)}/tables/delete`, withAuthHeaders({
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ table_ids: ids }),
  }))
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(typeof body.detail === 'string' ? body.detail : 'Could not delete tables')
  }
  return ids
}
