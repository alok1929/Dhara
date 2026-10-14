export const CONSOLE_UI_MODE_KEY = 'dhara_console_ui_mode_v1'

export const UI_MODES = {
  guided: 'guided',
  chat: 'chat',
}

export function loadConsoleUiMode() {
  try {
    const raw = sessionStorage.getItem(CONSOLE_UI_MODE_KEY)
    if (raw === UI_MODES.chat) return UI_MODES.chat
  } catch {
    // ignore
  }
  return UI_MODES.guided
}

export function saveConsoleUiMode(mode) {
  try {
    sessionStorage.setItem(CONSOLE_UI_MODE_KEY, mode === UI_MODES.chat ? UI_MODES.chat : UI_MODES.guided)
  } catch {
    // ignore
  }
}
