'use client'

/**
 * Fixed-height scroll container for chat split layout.
 */
export default function ChatScrollRegion({ height, className = '', children }) {
  return (
    <div
      className={`min-h-0 overflow-y-auto overscroll-contain ${className}`}
      style={{ height: height || '100%', maxHeight: height || '100%' }}
    >
      {children}
    </div>
  )
}
