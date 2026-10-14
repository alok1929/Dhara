import { withAuthHeaders } from './auth'
import { withLlmKeyHeaders } from './llmKey'

function detailFromErrorResponse(err, fallback) {
  const detail = typeof err.detail === 'string'
    ? err.detail
    : Array.isArray(err.detail)
      ? err.detail.map((d) => d?.msg || JSON.stringify(d)).join('; ')
      : ''
  return detail || fallback
}

/** Excel workbooks → extract + metadata match (same as BatchUpload.runMatch). */
export async function runBatchExtractMatch(datasetFiles, metadataFiles = []) {
  const extractFd = new FormData()
  datasetFiles.forEach((f) => extractFd.append('files', f))
  const extractRes = await fetch(
    '/api/catalogue/batch-extract',
    withAuthHeaders(withLlmKeyHeaders({ method: 'POST', body: extractFd })),
  )
  if (!extractRes.ok) {
    const err = await extractRes.json().catch(() => ({}))
    if (extractRes.status >= 500 && !err.detail) {
      throw new Error('Extraction timed out or the server closed the connection. Try again with a smaller workbook.')
    }
    throw new Error(detailFromErrorResponse(err, `Extraction failed (HTTP ${extractRes.status})`))
  }
  const extractData = await extractRes.json()

  const matchFd = new FormData()
  matchFd.append('tables_json', JSON.stringify(extractData.tables || []))
  metadataFiles.forEach((f) => matchFd.append('metadata_files', f))
  datasetFiles.forEach((f) => matchFd.append('dataset_files', f))
  const matchRes = await fetch(
    '/api/catalogue/batch-match',
    withAuthHeaders(withLlmKeyHeaders({ method: 'POST', body: matchFd })),
  )
  if (!matchRes.ok) {
    const err = await matchRes.json().catch(() => ({}))
    throw new Error(detailFromErrorResponse(err, `Matching failed (HTTP ${matchRes.status})`))
  }
  const matchData = await matchRes.json()

  return {
    ...matchData,
    batch_id: extractData.batch_id || null,
    metadataFiles,
    perFile: extractData.per_file,
  }
}

export function filesUseInlineExcelMatch(files) {
  if (!files?.length) return false
  return files.every((f) => /\.(xlsx|xls)$/i.test(f.name || ''))
}
