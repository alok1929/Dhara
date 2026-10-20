'use client'

import { Check, ChevronRight, Loader2 } from 'lucide-react'

export default function ChatTaskBlock({ task, onToggleCollapsed, children }) {
  const running = task.status === 'running'
  const errored = task.status === 'error'
  /** Running tasks stay open (Cursor-style “thinking”) until they finish. */
  const expanded = running || !task.collapsed
  const headerLabel = task.title
    || (running ? 'Working…' : 'Done')

  return (
    <div className="overflow-hidden rounded-2xl border border-line/90 bg-white shadow-sm">
      <button
        type="button"
        className="flex w-full items-center gap-2.5 px-4 py-3 text-left transition-colors hover:bg-sage/40"
        aria-expanded={expanded}
        onClick={() => onToggleCollapsed?.(task.id, task)}
      >
        {running ? (
          <Loader2 className="h-4 w-4 flex-none animate-spin text-teal" strokeWidth={2} aria-hidden />
        ) : errored ? (
          <span className="flex h-4 w-4 flex-none items-center justify-center rounded-full bg-[#fde8e8] text-[10px] font-bold text-[#b42318]">!</span>
        ) : (
          <Check className="h-4 w-4 flex-none text-green" strokeWidth={2.5} aria-hidden />
        )}
        <span className="min-w-0 flex-1 truncate text-[14px] font-medium text-ink">
          {headerLabel}
        </span>
        <ChevronRight
          className={`h-4 w-4 flex-none text-ink-soft transition-transform duration-dhara ${expanded ? 'rotate-90' : ''}`}
          strokeWidth={2}
          aria-hidden
        />
      </button>
      {expanded && (
        <div className="border-t border-line/70 bg-sage/35 px-4 py-3 text-[13px] font-normal leading-relaxed text-ink-soft">
          {task.lines?.length > 0 && (
            <ul className="mb-3 space-y-1.5">
              {task.lines.map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
          )}
          {children}
        </div>
      )}
    </div>
  )
}
