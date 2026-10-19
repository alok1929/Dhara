/** Shared heights for chat split panes (AppShell + stepper + gaps ≈ 12rem). */
export const CHAT_SPLIT_HEIGHT = 'calc(100vh - 12rem)'
export const CHAT_COMPOSER_HEIGHT = '5.25rem'
export const CHAT_MESSAGES_SCROLL_HEIGHT = `calc(${CHAT_SPLIT_HEIGHT} - ${CHAT_COMPOSER_HEIGHT})`

/** Inspect path: chat column left, larger workspace right. */
export const CHAT_SPLIT_CHAT_WIDTH = 'min(380px, 36vw)'
export const CHAT_SPLIT_WORKSPACE_CLASS = 'flex min-h-0 min-w-0 flex-1 flex-col'
