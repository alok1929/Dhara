/** Fixed commands for the small-model chat tier. Labels match the backend. */

export const STAGE_COMMANDS = {
  1: [
    'What should I upload?',
    'What happens after upload?',
  ],
  2: [
    'How many tables?',
    'List the table titles',
    'Which tables need review?',
    'Which tables have no title?',
  ],
  3: [
    'How many groups?',
    'List the group names',
    'Which groups have one table?',
    'Which tables are not grouped?',
  ],
  4: [
    'Which tables are missing a description?',
    'Which tables have no title?',
    'How many tables have a description?',
  ],
  5: [
    'How many tables are in this release?',
    'How many groups?',
    'Is classification complete?',
  ],
  6: [
    'Is classification complete?',
    'How many groups?',
    'What should I check before harmonising?',
  ],
  7: [
    'How many tables will be published?',
    'Is classification complete?',
    'What is still required before publish?',
  ],
}

const KNOWN = new Set(Object.values(STAGE_COMMANDS).flat())

export function commandsForStep(step) {
  return STAGE_COMMANDS[Number(step)] || STAGE_COMMANDS[2]
}

/** Chat chips. Preview, Grouping, and Metadata can advance without asking the model. */
export function composerCommandsForStep(step) {
  const commands = commandsForStep(step)
  const stage = Number(step) || 1
  if (stage < 2 || stage > 4) return commands
  return [...commands, 'Save and proceed']
}

export function isStageCommand(text) {
  return KNOWN.has(String(text || '').trim())
}

const PROCEED_PHRASES = new Set([
  'save and proceed',
  'verify and proceed',
  'proceed',
  'proceed to grouping',
  'proceed to metadata',
  'proceed to classification',
  'proceed to next step',
  'proceed to the next step',
  'move to next step',
  'move to the next step',
  'go to next step',
  'go to the next step',
  'next step',
  'continue',
  'continue to next step',
  'continue to the next step',
  'move on',
  'move ahead',
  'go ahead',
])

/** Same action as the Preview / Grouping "Save and proceed" button. */
export function isSaveAndProceedPhrase(text) {
  const normalized = String(text || '')
    .trim()
    .toLowerCase()
    .replace(/&/g, ' and ')
    .replace(/[?.!,]+/g, '')
    .replace(/\s+/g, ' ')
  return PROCEED_PHRASES.has(normalized)
}

function tableId(table) {
  return String(table?.table_id ?? table?._uid ?? table?.id ?? '').trim()
}

function tableTitle(table) {
  return String(table?.title || table?.name || table?.banner_table_id || 'Untitled').trim() || 'Untitled'
}

function tableLine(table, kind) {
  const id = tableId(table)
  if (!id) return ''
  const review = table?.human_review_needed ? 'yes' : 'no'
  const description = (table?.short_description || table?.description || table?.summary) ? 'yes' : 'no'
  return `${kind} | ${id} | ${tableTitle(table)} | review=${review} | description=${description}`
}

/**
 * Short fact lines for one command. Whole lines only — the command itself
 * is added on the server and is never trimmed.
 */
export function buildStageCommandLines(step, {
  tables = [],
  matchResult = null,
  classificationComplete = false,
  fileCount = 0,
} = {}) {
  const stage = Number(step) || 1
  const lines = [`stage=${stage}`, `files=${Number(fileCount) || 0}`]
  const groups = matchResult?.groups || []
  const grouped = new Set()

  if (stage >= 3) {
    groups.forEach((group, index) => {
      const nested = group?.matched_tables || []
      const ids = nested.map((row) => tableId(row?.table || row)).filter(Boolean)
      ids.forEach((id) => grouped.add(id))
      const name = group?.file_name || group?.name || `Group ${index + 1}`
      lines.push(`group ${index + 1} | ${name} | tables=${nested.length || ids.length}`)
    })
    ;(matchResult?.unmatched_tables || []).forEach((row) => {
      const line = tableLine(row?.table || row, 'ungrouped')
      if (line) lines.push(line)
    })
  }

  const releaseTables = (tables || []).filter((table) => {
    const id = tableId(table)
    return id && !grouped.has(id)
  })
  if (stage === 2 || stage === 4) {
    releaseTables.forEach((table) => {
      const line = tableLine(table, 'table')
      if (line) lines.push(line)
    })
  }

  const tableCount = (tables || []).length || groups.reduce(
    (sum, group) => sum + (group?.matched_tables?.length || 0),
    0,
  ) + (matchResult?.unmatched_tables?.length || 0)
  lines.push(`release_tables=${tableCount}`)
  lines.push(`classification_complete=${classificationComplete ? 'yes' : 'no'}`)
  lines.push(`groups=${groups.length}`)
  return lines
}
