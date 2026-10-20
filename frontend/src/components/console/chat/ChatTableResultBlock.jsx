'use client'

import { Maximize2 } from 'lucide-react'
import Button from '../../ui/Button'

const VARIANT_TITLE = {
  find: 'Matching tables',
  review: 'Tables that need review',
  delete: 'Tables to delete',
  group: 'Tables for proposed group',
}

/**
 * Inline chat result: scannable table rows with Open / Expand to view / Confirm delete.
 */
export default function ChatTableResultBlock({
  variant = 'find',
  rationale,
  rows = [],
  confirmed = false,
  confirming = false,
  onOpen,
  onExpand,
  onConfirmDelete,
  onConfirmGroup,
  groupName,
}) {
  const title = VARIANT_TITLE[variant] || VARIANT_TITLE.find
  const showReason = variant === 'review' || variant === 'delete'
  const isDelete = variant === 'delete'
  const isGroup = variant === 'group'

  return (
    <article className="rounded-2xl border border-line/90 bg-white p-4 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="text-[15px] font-semibold text-ink">
            {rows.length} {title.toLowerCase()}
          </div>
          {rationale ? (
            <p className="mt-1.5 text-[13px] text-ink-soft">{rationale}</p>
          ) : null}
        </div>
        {onExpand && rows.length > 0 && !confirmed && (
          <button
            type="button"
            className="inline-flex h-8 flex-none items-center gap-1.5 rounded-lg border border-line bg-white px-2.5 text-[12px] font-semibold text-ink-soft transition-colors hover:border-teal/40 hover:bg-sage hover:text-teal-deep"
            onClick={onExpand}
            title="Expand to view tables in Preview"
          >
            <Maximize2 className="h-3.5 w-3.5" strokeWidth={2} aria-hidden />
            Expand to view
          </button>
        )}
      </div>

      {rows.length === 0 ? (
        <p className="mt-3 text-[13px] text-ink-soft">No tables matched.</p>
      ) : (
        <div className="mt-3 max-h-56 overflow-auto rounded-xl border border-line/70">
          <table className="w-full border-collapse text-left text-[12.5px]">
            <thead className="sticky top-0 bg-surface/95 text-[11px] font-semibold uppercase tracking-wide text-ink-soft">
              <tr>
                <th className="px-3 py-2">Table</th>
                <th className="px-3 py-2">Page / ID</th>
                {showReason && <th className="px-3 py-2">Reason</th>}
                <th className="px-3 py-2 text-right">Action</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id} className="border-t border-line/60">
                  <td className="max-w-[14rem] px-3 py-2 font-medium text-ink" title={row.title}>
                    <span className="line-clamp-2 break-words">{row.title}</span>
                  </td>
                  <td className="whitespace-nowrap px-3 py-2 text-ink-soft">
                    {row.page != null ? `p.${row.page}` : '—'}
                    <span className="mx-1 text-line">·</span>
                    <span className="font-mono text-[11px]">{row.id}</span>
                  </td>
                  {showReason && (
                    <td className="max-w-[8rem] truncate px-3 py-2 text-ink-soft" title={row.reason || ''}>
                      {row.reason || '—'}
                    </td>
                  )}
                  <td className="px-3 py-2 text-right">
                    {onOpen && (
                      <Button variant="secondary" size="sm" onClick={() => onOpen(row)}>
                        Open
                      </Button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {isDelete && !confirmed && rows.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-2">
          {onExpand && (
            <Button variant="secondary" size="sm" onClick={onExpand}>
              Expand to view
            </Button>
          )}
          <Button
            size="sm"
            disabled={confirming}
            onClick={onConfirmDelete}
          >
            {confirming ? 'Deleting…' : 'Confirm delete'}
          </Button>
        </div>
      )}
      {isGroup && !confirmed && rows.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-2">
          {onExpand && (
            <Button variant="secondary" size="sm" onClick={onExpand}>
              Expand to view
            </Button>
          )}
          <Button size="sm" disabled={confirming} onClick={onConfirmGroup}>
            {confirming ? 'Applying…' : `Apply group${groupName ? ` “${groupName}”` : ''}`}
          </Button>
        </div>
      )}
      {isDelete && confirmed && (
        <p className="mt-3 text-[12.5px] font-medium text-green">Deleted from this preview.</p>
      )}
      {isGroup && confirmed && (
        <p className="mt-3 text-[12.5px] font-medium text-green">
          Group{groupName ? ` “${groupName}”` : ''} applied.
        </p>
      )}
    </article>
  )
}
