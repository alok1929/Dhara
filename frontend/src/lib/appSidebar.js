/** AppShell primary nav collapse preference + chat-split auto-collapse signal. */

export const APP_SIDEBAR_COLLAPSED_KEY = 'dhara_app_sidebar_collapsed_v1'
export const APP_SIDEBAR_COLLAPSE_EVENT = 'dhara:app-sidebar-collapse'

export function loadAppSidebarCollapsed() {
  try {
    return localStorage.getItem(APP_SIDEBAR_COLLAPSED_KEY) === '1'
  } catch {
    return false
  }
}

export function saveAppSidebarCollapsed(collapsed) {
  try {
    localStorage.setItem(APP_SIDEBAR_COLLAPSED_KEY, collapsed ? '1' : '0')
  } catch {
    // best-effort
  }
}

/** Ask AppShell to collapse the nav (e.g. when chat workspace split opens). */
export function requestAppSidebarCollapse() {
  try {
    window.dispatchEvent(new CustomEvent(APP_SIDEBAR_COLLAPSE_EVENT))
  } catch {
    // best-effort
  }
}
