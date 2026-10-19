'use client'

import { Maximize2 } from 'lucide-react'
import Button from '../../ui/Button'

/**
 * Inline stage card in the chat thread — summary + Verify (trust) + Expand (inspect).
 */
export default function ChatStageArtifact({
  title,
  subtitle,
  summary,
  bullets,
  onExpand,
  expandLabel = 'Expand',
  onVerify,
  verifyLabel = 'Verify & proceed',
  verifyDisabled,
  extra,
}) {
  return (
    <article className="rounded-2xl border border-line/90 bg-white p-4 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="text-[11px] font-bold uppercase tracking-wide text-teal">{title}</div>
          {subtitle ? (
            <div className="mt-0.5 truncate text-[13px] font-medium text-ink" title={subtitle}>
              {subtitle}
            </div>
          ) : null}
        </div>
        {onExpand && (
          <button
            type="button"
            className="inline-flex h-8 flex-none items-center gap-1.5 rounded-lg border border-line bg-white px-2.5 text-[12px] font-semibold text-ink-soft transition-colors hover:border-teal/40 hover:bg-sage hover:text-teal-deep"
            onClick={onExpand}
            title={expandLabel}
          >
            <Maximize2 className="h-3.5 w-3.5" strokeWidth={2} aria-hidden />
            {expandLabel}
          </button>
        )}
      </div>
      <p className="mt-2 text-[14px] leading-relaxed text-ink">{summary}</p>
      {bullets?.length > 0 && (
        <ul className="mt-2 list-disc space-y-1 pl-5 text-[13px] text-ink-soft">
          {bullets.map((b) => (
            <li key={b}>{b}</li>
          ))}
        </ul>
      )}
      {extra}
      {onVerify && (
        <div className="mt-4 flex flex-wrap gap-2">
          <Button size="sm" disabled={verifyDisabled} onClick={onVerify}>
            {verifyLabel}
          </Button>
        </div>
      )}
    </article>
  )
}
