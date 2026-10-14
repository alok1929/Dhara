'use client'

import { X } from 'lucide-react'
import Button from '../../ui/Button'
import { CHAT_SPLIT_HEIGHT } from './chatLayout'

/**
 * Rounded workspace shell — fixed split height, scrollable body.
 */
export default function ChatRightPanel({
  title,
  onClose,
  onVerify,
  verifyLabel = 'Verify & proceed',
  panelHeight = CHAT_SPLIT_HEIGHT,
  contentClassName = '',
  compact = false,
  children,
}) {
  const headerPad = compact ? 'px-3 py-2' : 'px-4 py-3'
  const footerPad = compact ? 'px-3 py-2' : 'px-4 py-3'
  const titleClass = compact
    ? 'min-w-0 truncate text-[14px] font-semibold tracking-tight text-ink'
    : 'text-[15px] font-semibold tracking-tight text-ink'

  return (
    <div
      className={`flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden border border-line/90 bg-white ${compact ? 'rounded-xl shadow-none' : 'rounded-2xl shadow-sm'}`}
      style={{ height: panelHeight, maxHeight: panelHeight }}
    >
      <div className={`flex flex-none items-center justify-between gap-2 border-b border-line/80 bg-surface/80 ${headerPad}`}>
        <div className={titleClass} title={typeof title === 'string' ? title : undefined}>{title}</div>
        <button
          type="button"
          className={`flex items-center justify-center rounded-lg text-ink-soft transition-colors hover:bg-sage hover:text-teal-deep ${compact ? 'h-7 w-7' : 'h-8 w-8'}`}
          onClick={onClose}
          aria-label="Close workspace"
        >
          <X className="h-4 w-4" strokeWidth={2} />
        </button>
      </div>
      <div className={`min-h-0 flex-1 overflow-y-auto overscroll-contain bg-white ${contentClassName}`}>
        {children}
      </div>
      <div className={`flex flex-none justify-end gap-2 border-t border-line/80 bg-surface/80 ${footerPad}`}>
        {!compact && (
          <Button variant="secondary" size="sm" onClick={onClose}>Close</Button>
        )}
        {onVerify && (
          <Button size="sm" onClick={onVerify}>{verifyLabel}</Button>
        )}
      </div>
    </div>
  )
}
