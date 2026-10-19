'use client'

// Persistent app shell: logo, tri-color accent bar, primary nav, user card.
// Wraps every in-app screen (Dashboard / Console / Catalogue / Settings).
// Served from public/ (root-relative path) rather than imported as a module
// -- Next's bundler wraps imported image modules in a {src,width,height}
// object for next/image, which would break a plain <img src=...>.
import { useEffect, useState } from 'react'
import {
  LayoutDashboard,
  Library,
  LogOut,
  PanelLeft,
  PanelLeftClose,
  Settings,
  TerminalSquare,
} from 'lucide-react'
import {
  APP_SIDEBAR_COLLAPSE_EVENT,
  loadAppSidebarCollapsed,
  saveAppSidebarCollapsed,
} from '../lib/appSidebar'

// variant="light" is for dark backgrounds (the Auth screen's dark panel):
// dhara-logo-light.png is the same wordmark PNG (same font, same icon
// colors, still fully transparent) with only the near-black "DATA"/"DHARA"
// glyph pixels recolored to cream -- pixel-for-pixel the original type, just
// legible on a dark panel with no background patch behind it.
export function DharaLogo({ compact, variant = 'default' }) {
  if (variant === 'light') {
    return (
      <img
        className={compact ? 'block h-auto w-[170px]' : 'block h-auto w-[240px]'}
        src="/dhara-logo-light.png"
        alt="Data Dhara"
      />
    )
  }
  return (
    <img
      className={compact ? 'block h-auto w-[132px]' : 'block h-auto w-[168px]'}
      src="/dhara-logo.png"
      alt="Data Dhara"
    />
  )
}

export function TriBar({ className = '' }) {
  return (
    <div className={`flex h-1 gap-1 ${className}`}>
      <div className="flex-1 bg-yellow" />
      <div className="flex-1 bg-green" />
      <div className="flex-1 bg-coral" />
    </div>
  )
}

const NAV_ITEMS = [
  { key: 'dashboard', label: 'Dashboard', Icon: LayoutDashboard },
  { key: 'console', label: 'Console', Icon: TerminalSquare },
  { key: 'catalogue', label: 'Catalogue', Icon: Library },
]

function navClass(active, collapsed) {
  const base = collapsed
    ? 'dhara-tab flex cursor-pointer items-center justify-center rounded-xl p-2.5'
    : 'dhara-tab flex cursor-pointer items-center gap-2.5 rounded-xl px-3.5 py-2.5 text-[14.5px] tracking-tight'
  return `${base} ${
    active
      ? 'border-transparent bg-teal-deep font-semibold text-cream'
      : 'border-transparent font-medium text-ink-soft hover:bg-sage hover:text-teal-deep'
  }`
}

export default function AppShell({ screen, user, onNavigate, onSignOut, children }) {
  const [collapsed, setCollapsed] = useState(false)
  const [hydrated, setHydrated] = useState(false)

  useEffect(() => {
    setCollapsed(loadAppSidebarCollapsed())
    setHydrated(true)
  }, [])

  useEffect(() => {
    if (!hydrated) return
    saveAppSidebarCollapsed(collapsed)
  }, [collapsed, hydrated])

  useEffect(() => {
    const onRequestCollapse = () => setCollapsed(true)
    window.addEventListener(APP_SIDEBAR_COLLAPSE_EVENT, onRequestCollapse)
    return () => window.removeEventListener(APP_SIDEBAR_COLLAPSE_EVENT, onRequestCollapse)
  }, [])

  const initials = (user?.name || '')
    .split(/\s+/)
    .filter(Boolean)
    .map((w) => w[0])
    .join('')
    .slice(0, 2)
    .toUpperCase()

  const toggleCollapsed = () => setCollapsed((c) => !c)

  return (
    <div className="flex h-screen w-full bg-outer-bg">
      <nav
        className={`flex flex-none flex-col border-r border-line/80 bg-surface py-6 transition-[width] duration-dhara ease-dhara ${
          collapsed ? 'w-16' : 'w-[220px]'
        }`}
        aria-expanded={!collapsed}
      >
        <div className={`flex items-center pb-2 ${collapsed ? 'flex-col gap-2 px-2' : 'justify-between gap-2 px-3'}`}>
          {!collapsed && (
            <div className="min-w-0 px-2">
              <DharaLogo compact />
            </div>
          )}
          <button
            type="button"
            className="flex h-8 w-8 flex-none items-center justify-center rounded-lg text-ink-soft transition-colors duration-dhara ease-dhara hover:bg-sage hover:text-teal-deep"
            onClick={toggleCollapsed}
            aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          >
            {collapsed ? (
              <PanelLeft className="h-4 w-4" strokeWidth={1.75} aria-hidden />
            ) : (
              <PanelLeftClose className="h-4 w-4" strokeWidth={1.75} aria-hidden />
            )}
          </button>
        </div>
        {!collapsed && (
          <TriBar className="mx-5 mb-5 mt-3 overflow-hidden rounded-full" />
        )}
        {collapsed && <div className="mb-3 mt-1 h-px w-8 self-center bg-line/80" />}
        <div className={`flex flex-col gap-0.5 ${collapsed ? 'px-2' : 'px-3'}`}>
          {NAV_ITEMS.map((item) => (
            <div
              key={item.key}
              className={navClass(screen === item.key, collapsed)}
              onClick={() => onNavigate(item.key)}
              title={collapsed ? item.label : undefined}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault()
                  onNavigate(item.key)
                }
              }}
            >
              <item.Icon className="h-4 w-4 flex-none" strokeWidth={1.75} aria-hidden />
              {!collapsed && item.label}
            </div>
          ))}
        </div>
        <div className={`mt-auto flex flex-col gap-3 ${collapsed ? 'px-2' : ''}`}>
          <div className={`flex flex-col gap-0.5 ${collapsed ? '' : 'px-3'}`}>
            <div
              className={navClass(screen === 'settings', collapsed)}
              onClick={() => onNavigate('settings')}
              title={collapsed ? 'Settings' : undefined}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault()
                  onNavigate('settings')
                }
              }}
            >
              <Settings className="h-4 w-4 flex-none" strokeWidth={1.75} aria-hidden />
              {!collapsed && 'Settings'}
            </div>
          </div>
          {collapsed ? (
            <div className="flex flex-col items-center gap-2 border-t border-line/80 pt-4">
              <div
                className="flex h-8 w-8 flex-none items-center justify-center rounded-full bg-teal-deep text-[12px] font-semibold text-cream"
                title={user?.name || 'User'}
              >
                {initials || 'U'}
              </div>
              <button
                type="button"
                className="flex h-8 w-8 items-center justify-center rounded-lg text-ink-soft transition-colors duration-dhara ease-dhara hover:bg-sage hover:text-teal"
                onClick={onSignOut}
                title="Sign out"
                aria-label="Sign out"
              >
                <LogOut className="h-4 w-4" strokeWidth={1.75} aria-hidden />
              </button>
            </div>
          ) : (
            <>
              <div className="mx-5 mt-1 flex items-center gap-2.5 border-t border-line/80 pt-4">
                <div className="flex h-8 w-8 flex-none items-center justify-center rounded-full bg-teal-deep text-[12px] font-semibold text-cream">
                  {initials || 'U'}
                </div>
                <div className="flex min-w-0 flex-col">
                  <div className="truncate text-[13.5px] font-semibold text-ink" title={user?.name}>{user?.name}</div>
                  <div className="text-[11.5px] text-ink-soft">{user?.role}</div>
                </div>
              </div>
              <div className="cursor-pointer px-5 pb-1 text-[13px] text-ink-soft transition-colors duration-dhara ease-dhara hover:text-teal" onClick={onSignOut}>Sign out</div>
            </>
          )}
        </div>
      </nav>

      <div className="flex min-w-0 flex-1 flex-col">
        {/* Padding lives on an inner wrapper (not the scrollport) so position:sticky
            children can stick flush to the top with no padding gap above them.
            has-[.cat-screen]: Catalogue.jsx manages its own internal scroll. */}
        <div className="min-h-0 flex-1 overflow-y-auto has-[.cat-screen]:flex has-[.cat-screen]:flex-col has-[.cat-screen]:overflow-hidden">
          <div
            key={screen}
            className="dhara-page-enter p-8 px-9 has-[.cat-screen]:flex has-[.cat-screen]:min-h-0 has-[.cat-screen]:flex-1 has-[.cat-screen]:flex-col has-[.cat-screen]:overflow-hidden"
          >
            {children}
          </div>
        </div>
      </div>
    </div>
  )
}
