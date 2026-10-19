/** Shared PDF preview → grouping progress copy and persist helper (chat + guided). */

import { withAuthHeaders } from './auth'
import { withLlmKeyHeaders } from './llmKey'
import {
  continuePdfJobFromPreview,
  matchResultFromPdfPersistResponse,
} from './chatConsoleHelpers'

export const PDF_GROUPING_PROGRESS_SUBTITLE =
  'Saving your tables and running grouping — this may take a moment.'

/** Build ProcessingStepper steps for persist → group phases. */
export function buildPdfGroupingProgressSteps(phase = 'persist') {
  const persistDone = phase === 'group' || phase === 'done'
  return [
    {
      key: 'persist',
      label: 'Saving approved tables',
      status: persistDone ? 'done' : 'active',
      message: persistDone ? undefined : 'Writing reviewed tables so grouping can use them…',
    },
    {
      key: 'group',
      label: 'Grouping similar tables',
      status: phase === 'done' ? 'done' : persistDone ? 'active' : 'pending',
      message: persistDone && phase !== 'done'
        ? 'Building embeddings and proposing groups…'
        : undefined,
    },
  ]
}

function tablesPersistBody(tables) {
  if (!tables?.length) return undefined
  return {
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
}

/**
 * Persist approved PDF tables and return console matchResult.
 * @param {string} jobId
 * @param {{ tables?: object[], sourceFile?: string, onPhase?: (phase: 'persist'|'group') => void }} opts
 */
export async function persistPdfApprovedAndLoadGrouping(jobId, {
  tables,
  sourceFile,
  onPhase,
} = {}) {
  if (!jobId) throw new Error('Missing PDF job id')

  try {
    sessionStorage.removeItem(`dhara_pdf_pipeline_v1_${jobId}`)
  } catch {
    /* best-effort */
  }

  onPhase?.('persist')
  const phaseTimer = setTimeout(() => onPhase?.('group'), 900)

  try {
    const body = tablesPersistBody(tables)
    const persistInit = withLlmKeyHeaders(withAuthHeaders({ method: 'POST' }))
    if (body) {
      persistInit.headers = { ...persistInit.headers, 'Content-Type': 'application/json' }
      persistInit.body = JSON.stringify(body)
    }

    const persistRes = await fetch(
      `/api/pdf/jobs/${encodeURIComponent(jobId)}/persist-approved`,
      persistInit,
    )
    const persistData = await persistRes.json().catch(() => ({}))
    if (!persistRes.ok) {
      throw new Error(
        typeof persistData.detail === 'string'
          ? persistData.detail
          : 'Could not save tables for grouping',
      )
    }

    clearTimeout(phaseTimer)
    onPhase?.('group')

    const fromPersist = matchResultFromPdfPersistResponse(persistData, jobId, sourceFile)
    if (fromPersist) return { matchResult: fromPersist, persistData }

    // Fallback: continuePdfJobFromPreview without re-sending tables (grouping endpoint).
    const matchResult = await continuePdfJobFromPreview(jobId, { sourceFile })
    return { matchResult, persistData }
  } catch (e) {
    clearTimeout(phaseTimer)
    throw e
  }
}
