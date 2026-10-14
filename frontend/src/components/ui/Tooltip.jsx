'use client'

/**
 * Hover / focus tooltip for icon controls. Wraps a single focusable child.
 */
export default function Tooltip({ label, children, placement = 'top' }) {
  const positionClass =
    placement === 'bottom'
      ? 'top-full mt-2'
      : 'bottom-full mb-2'

  return (
    <span className="group/tooltip relative inline-flex">
      {children}
      <span
        role="tooltip"
        className={`pointer-events-none absolute left-1/2 z-50 ${positionClass} -translate-x-1/2 whitespace-nowrap rounded-lg border border-line/90 bg-teal-deep px-2.5 py-1.5 text-[12px] font-medium text-cream opacity-0 shadow-md transition-opacity duration-150 ease-dhara group-hover/tooltip:opacity-100 group-focus-within/tooltip:opacity-100 motion-reduce:transition-none`}
      >
        {label}
      </span>
    </span>
  )
}
