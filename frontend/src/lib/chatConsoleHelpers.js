import { withAuthHeaders } from './auth'
import { withLlmKeyHeaders } from './llmKey'
import { pdfGroupingToMatchResult, previewReviewStatus } from './postPreview'
export { excludeTablesFromMatchResult } from './chatTableExclusions'

/** Uploaded workbook / PDF name stored on an extracted table. */
export function datasetNameOf(table) {
  return table?.filename || table?.source_file || table?.source_filename || null
}

export function datasetNamesFromTables(tables) {
  const names = []
  const seen = new Set()
  ;(tables || []).forEach((table) => {
    const name = datasetNameOf(table)
    if (!name || seen.has(name)) return
    seen.add(name)
    names.push(name)
  })
  return names
}

export function previewStageSummary(tables, savedIds) {
  const list = tables || []
  const needsFix = list.filter((t) => previewReviewStatus(t, savedIds) === 'fix').length
  const aiReview = list.filter((t) => previewReviewStatus(t, savedIds) === 'ai').length
  const ok = list.filter((t) => previewReviewStatus(t, savedIds) === 'ok').length
  return {
    total: list.length,
    ok,
    needsFix,
    aiReview,
  }
}

export function groupingStageSummary(matchResult) {
  if (!matchResult) {
    return { groups: 0, tables: 0, unmatched: 0 }
  }
  const groups = matchResult.groups?.length || 0
  const inGroups = (matchResult.groups || []).reduce(
    (n, g) => n + (g.matched_tables?.length || 0),
    0,
  )
  const unmatched = matchResult.unmatched_tables?.length || 0
  return { groups, tables: inGroups + unmatched, unmatched }
}

export function catalogFromBatchTables(tables) {
  return (tables || []).map((t) => ({
    table_id: String(t._uid),
    title: t.title || t.id || t.filename || 'Table',
    page: t.page ?? null,
    short_description: t.short_description ?? null,
    filename: t.filename ?? null,
  }))
}

export function catalogFromPdfResultTables(tables) {
  return (tables || []).map((t) => ({
    table_id: String(t.table_id),
    title: t.title || t.banner_table_id || 'Table',
    page: t.page ?? null,
    short_description: t.short_description ?? t.description ?? null,
    filename: t.filename ?? null,
  }))
}

export async function fetchPdfJobResultTables(jobId) {
  const res = await fetch(`/api/pdf/jobs/${encodeURIComponent(jobId)}/result`, withAuthHeaders())
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(typeof body.detail === 'string' ? body.detail : 'Could not load extracted tables')
  }
  const data = await res.json()
  return data.tables || []
}

function pdfClientGrouping(data) {
  return {
    groups: (data.groups || []).map((g) => ({
      group_id: g.group_id,
      name: g.name,
      tables: g.tables || [],
    })),
    unmatched: data.unmatched_tables || data.unmatched || [],
    method: data.method,
  }
}

/** Build matchResult from persist-approved JSON (includes grouping — no second persist). */
export function matchResultFromPdfPersistResponse(persistData, jobId, sourceFile) {
  const grouping = persistData?.grouping
  if (!grouping?.groups) return null
  const client = pdfClientGrouping({
    groups: grouping.groups,
    unmatched_tables: grouping.unmatched_tables,
    method: grouping.method,
    filename: persistData.filename,
  })
  return pdfGroupingToMatchResult(
    { groups: client.groups, unmatched: client.unmatched, method: client.method },
    sourceFile || persistData.filename || 'pdf',
    jobId,
  )
}

/** Persist approved PDF tables and load grouping into console matchResult shape. */
export async function continuePdfJobFromPreview(jobId, { tables, sourceFile } = {}) {
  const body = tables?.length
    ? {
      tables: tables.map((t) => ({
        table_id: t.table_id,
        title: t.title ?? null,
        rows: t.rows,
        columns: t.columns,
        classification: t.classification,
        human_review_needed: t.human_review_needed,
        human_review_reason: t.human_review_reason,
        semantic_status: t.semantic_status,
      })),
    }
    : undefined

  const persistInit = withLlmKeyHeaders(withAuthHeaders({ method: 'POST' }))
  if (body) {
    persistInit.headers = { ...persistInit.headers, 'Content-Type': 'application/json' }
    persistInit.body = JSON.stringify(body)
  }
  const persistRes = await fetch(
    `/api/pdf/jobs/${encodeURIComponent(jobId)}/persist-approved`,
    persistInit,
  )
  if (!persistRes.ok) {
    const errBody = await persistRes.json().catch(() => ({}))
    throw new Error(typeof errBody.detail === 'string' ? errBody.detail : 'Could not save tables for grouping')
  }

  const persistData = await persistRes.json()
  const fromPersist = matchResultFromPdfPersistResponse(persistData, jobId, sourceFile)
  if (fromPersist) return fromPersist

  const groupingRes = await fetch(`/api/pdf/jobs/${encodeURIComponent(jobId)}/grouping`, withAuthHeaders())
  if (!groupingRes.ok) {
    const errBody = await groupingRes.json().catch(() => ({}))
    throw new Error(typeof errBody.detail === 'string' ? errBody.detail : 'Could not load grouping')
  }
  const groupingData = await groupingRes.json()
  const client = pdfClientGrouping(groupingData)
  return pdfGroupingToMatchResult(
    { groups: client.groups, unmatched: client.unmatched, method: client.method },
    sourceFile || groupingData.filename || 'pdf',
    jobId,
  )
}

export async function downloadPdfJobTablesZip(jobId, fallbackName = 'tables.zip') {
  const res = await fetch(
    `/api/pdf/jobs/${jobId}/tables/download-zip`,
    withAuthHeaders(),
  )
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(typeof body.detail === 'string' ? body.detail : 'Download failed')
  }
  const blob = await res.blob()
  const cd = res.headers.get('Content-Disposition') || ''
  const match = /filename="?([^";]+)"?/i.exec(cd)
  const name = match?.[1] || fallbackName
  const objectUrl = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = objectUrl
  a.download = name
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(objectUrl)
}

export function formatFileSize(bytes) {
  if (bytes == null || Number.isNaN(bytes)) return ''
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}
