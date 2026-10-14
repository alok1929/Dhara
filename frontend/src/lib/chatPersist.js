/** Ephemeral chat UI keys (processing jobs). Message history lives in Postgres per chat session UUID. */

export const CHAT_ACTIVE_JOB_KEY = 'dhara_chat_active_job_v1'
export const CHAT_REVIEW_JOB_KEY = 'dhara_chat_review_job_v1'
export const CHAT_REVIEW_FILENAME_KEY = 'dhara_chat_review_filename_v1'
/** @deprecated legacy global messages — cleared on new upload */
export const CHAT_MESSAGES_KEY = 'dhara_chat_messages_v1'

export function clearLegacyChatMessages() {
  try {
    sessionStorage.removeItem(CHAT_MESSAGES_KEY)
  } catch {
    // best-effort
  }
}

export function loadChatActiveJob() {
  try {
    return sessionStorage.getItem(CHAT_ACTIVE_JOB_KEY) || null
  } catch {
    return null
  }
}

export function saveChatActiveJob(jobId) {
  try {
    if (jobId) sessionStorage.setItem(CHAT_ACTIVE_JOB_KEY, jobId)
    else sessionStorage.removeItem(CHAT_ACTIVE_JOB_KEY)
  } catch {
    // best-effort
  }
}

export function loadChatReviewJob() {
  try {
    return sessionStorage.getItem(CHAT_REVIEW_JOB_KEY) || null
  } catch {
    return null
  }
}

export function loadChatReviewFilename() {
  try {
    return sessionStorage.getItem(CHAT_REVIEW_FILENAME_KEY) || null
  } catch {
    return null
  }
}

export function saveChatReviewJob(jobId, filename = null) {
  try {
    if (jobId) {
      sessionStorage.setItem(CHAT_REVIEW_JOB_KEY, jobId)
      if (filename) sessionStorage.setItem(CHAT_REVIEW_FILENAME_KEY, filename)
    } else {
      sessionStorage.removeItem(CHAT_REVIEW_JOB_KEY)
      sessionStorage.removeItem(CHAT_REVIEW_FILENAME_KEY)
    }
  } catch {
    // best-effort
  }
}

export function clearChatEphemeralKeys() {
  saveChatActiveJob(null)
  saveChatReviewJob(null)
  clearLegacyChatMessages()
}
