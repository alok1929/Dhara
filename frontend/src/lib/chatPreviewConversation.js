/** Utterances that should filter the preview (same family as AI search / action find). */
export function isPreviewShowFindIntent(text) {
  const t = String(text || '').trim().toLowerCase()
  if (!t) return false
  if (/^(show them|show those|show these|display them|display those)[.!?]*$/.test(t)) return true
  if (/^(show|display|highlight|filter|open)[.!?]*$/.test(t)) return true
  if (/^(them|those)[.!?]*$/.test(t)) return true
  return (
    /\b(show|display|highlight|filter\s+(to|down)?|open)\b/i.test(t)
    || /\bshow\s+me\b/i.test(t)
  )
}

/** Recent user/assistant turns for preview ai-chat follow-ups ("show them"). */
export function buildPreviewChatConversation(messages, { maxTurns = 10 } = {}) {
  return (messages || [])
    .filter((m) => m.kind === 'user' || m.kind === 'assistant')
    .slice(-maxTurns)
    .map((m) => ({
      role: m.kind === 'user' ? 'user' : 'assistant',
      content: String(m.text || '').trim(),
    }))
    .filter((t) => t.content)
}
