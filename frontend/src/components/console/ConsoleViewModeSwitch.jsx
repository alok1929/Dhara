'use client'

import { LayoutList, MessageSquare } from 'lucide-react'
import Tooltip from '../ui/Tooltip'
import { UI_MODES } from '../../lib/consoleUiMode'

export default function ConsoleViewModeSwitch({ mode, onChange }) {
  const tabClass = (active) =>
    `inline-flex items-center justify-center rounded-lg p-2 transition-colors duration-dhara ease-dhara ${
      active
        ? 'bg-teal-deep text-cream shadow-[0_0_0_1px_rgba(18,64,62,0.12)]'
        : 'text-ink-soft hover:bg-sage hover:text-teal-deep'
    }`

  return (
    <div
      className="inline-flex flex-none items-center gap-0.5 rounded-xl border border-line/90 bg-surface p-1"
      role="tablist"
      aria-label="Console view mode"
    >
      <Tooltip label="Guided view">
        <button
          type="button"
          role="tab"
          aria-selected={mode === UI_MODES.guided}
          aria-label="Guided view"
          className={tabClass(mode === UI_MODES.guided)}
          onClick={() => onChange(UI_MODES.guided)}
        >
          <LayoutList className="h-4 w-4" strokeWidth={2} aria-hidden />
        </button>
      </Tooltip>
      <Tooltip label="Chat view">
        <button
          type="button"
          role="tab"
          aria-selected={mode === UI_MODES.chat}
          aria-label="Chat view"
          className={tabClass(mode === UI_MODES.chat)}
          onClick={() => onChange(UI_MODES.chat)}
        >
          <MessageSquare className="h-4 w-4" strokeWidth={2} aria-hidden />
        </button>
      </Tooltip>
    </div>
  )
}
