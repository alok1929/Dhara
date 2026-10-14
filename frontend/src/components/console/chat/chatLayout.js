/** Shared heights for chat split panes (AppShell + stepper + gaps ≈ 12rem). */
export const CHAT_SPLIT_HEIGHT = 'calc(100vh - 12rem)'
export const CHAT_COMPOSER_HEIGHT = '5.25rem'
export const CHAT_MESSAGES_SCROLL_HEIGHT = `calc(${CHAT_SPLIT_HEIGHT} - ${CHAT_COMPOSER_HEIGHT})`
