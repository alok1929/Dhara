/** Chat workflow pills — map to existing Console `step` numbers (1–7). */

export const CHAT_STAGE_PILLS = [
  { id: 'upload', label: 'Upload', steps: [1] },
  { id: 'preview', label: 'Preview', steps: [2] },
  { id: 'grouping', label: 'Grouping', steps: [3, 4] },
  { id: 'classification', label: 'Classification', steps: [5] },
  { id: 'harmonisation', label: 'Harmonisation', steps: [6] },
  { id: 'publish', label: 'Publish', steps: [7] },
]

export function chatPillIndexForStep(step) {
  const s = Number(step) || 1
  const idx = CHAT_STAGE_PILLS.findIndex((p) => p.steps.includes(s))
  return idx < 0 ? 0 : idx
}

export function chatPillIdForStep(step) {
  return CHAT_STAGE_PILLS[chatPillIndexForStep(step)]?.id || 'upload'
}

/**
 * Pill visual state from pipeline progress (does not roll back processing).
 */
export function chatPillStatus(pillIndex, currentStep, maxStepReached) {
  const pill = CHAT_STAGE_PILLS[pillIndex]
  if (!pill) return 'upcoming'
  if (pill.steps.includes(currentStep)) return 'current'
  const maxOnPill = Math.max(...pill.steps)
  if (maxStepReached > maxOnPill) return 'completed'
  if (maxStepReached >= maxOnPill && currentStep > maxOnPill) return 'completed'
  return 'upcoming'
}

export function stepForChatPillId(pillId) {
  const pill = CHAT_STAGE_PILLS.find((p) => p.id === pillId)
  return pill?.steps?.[0] ?? 1
}
