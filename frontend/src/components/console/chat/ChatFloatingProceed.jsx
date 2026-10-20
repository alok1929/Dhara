'use client'

import Button from '../../ui/Button'

/**
 * Floating primary CTA in the left chat column (Preview → Grouping).
 */
export default function ChatFloatingProceed({
  onClick,
  disabled = false,
  loading = false,
  label = 'Proceed to grouping',
}) {
  return (
    <div className="pointer-events-none absolute bottom-[5.75rem] right-3 z-20">
      <div className="pointer-events-auto">
        <Button
          size="sm"
          disabled={disabled || loading}
          onClick={onClick}
          className="shadow-md"
        >
          {loading ? 'Saving…' : label}
        </Button>
      </div>
    </div>
  )
}
