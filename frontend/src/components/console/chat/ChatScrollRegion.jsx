'use client'

/**
 * Fixed-height scroll container for chat split layout.
 * Keeps the message column independently scrollable when the right workspace is open.
 */
export default function ChatScrollRegion({ height, className = '', children }) {
  return (
    <div
      className={`min-h-0 flex-1 overflow-y-auto overscroll-contain ${className}`}
      style={{
        height: height || undefined,
        maxHeight: height || '100%',
        flex: height ? 'none' : '1 1 auto',
      }}
    >
      {children}
    </div>
  )
}
