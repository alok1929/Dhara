/**
 * Shared AI "find" filter for chat-controlled preview (PDF job + batch tables).
 */

/** @typedef {{ intent: 'find', tableIds: string[], rationale?: string, prompt?: string }} PreviewAiFindFilter */

/** @returns {PreviewAiFindFilter} */
export function createPreviewAiFindFilter({ tableIds, rationale = '', prompt = '' }) {
  const ids = [...new Set((tableIds || []).map((id) => String(id)).filter(Boolean))]
  return {
    intent: 'find',
    tableIds: ids,
    rationale: String(rationale || '').trim(),
    prompt: String(prompt || '').trim(),
  }
}

/** @param {PreviewAiFindFilter | null | undefined} filter */
export function isPreviewAiFindActive(filter) {
  return filter?.intent === 'find' && (filter.tableIds?.length ?? 0) > 0
}

/**
 * @param {Array<Record<string, unknown>>} tables
 * @param {PreviewAiFindFilter | null | undefined} filter
 * @param {(row: Record<string, unknown>) => string} getTableId
 */
export function applyPreviewAiFindFilter(tables, filter, getTableId) {
  if (!isPreviewAiFindActive(filter)) return tables || []
  const idSet = new Set(filter.tableIds.map(String))
  return (tables || []).filter((t) => idSet.has(String(getTableId(t))))
}

/** Catalog rows for ai-search / ai-chat APIs. */
export function catalogRowsForAiSearch(tables, { pdfJob = false } = {}) {
  return (tables || []).map((t) => {
    if (pdfJob) {
      return {
        table_id: t.table_id,
        title: t.title ?? null,
        banner_table_id: t.banner_table_id ?? null,
        page: t.page,
        short_description: t.short_description ?? t.description ?? null,
      }
    }
    return {
      table_id: String(t._uid ?? t.table_id),
      title: t.title || t.id || t.filename || 'Table',
      page: t.page ?? null,
      short_description: t.short_description ?? null,
      filename: t.filename ?? null,
    }
  })
}
