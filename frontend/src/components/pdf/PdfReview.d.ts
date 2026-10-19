import type { ForwardRefExoticComponent, RefAttributes } from 'react'

export interface PreviewAiFindFilter {
  intent: 'find'
  tableIds: string[]
  rationale?: string
  prompt?: string
}

export interface PdfReviewProps {
  jobId: string
  filename?: string | null
  onDone?: () => void
  embedded?: boolean
  compact?: boolean
  previewAiFilter?: PreviewAiFindFilter | null
  onPreviewAiFilterChange?: (filter: PreviewAiFindFilter | null) => void
  onContinueToGrouping?: ((
    jobId: string,
    persistResponse?: { grouping?: Record<string, unknown>; filename?: string },
  ) => void | Promise<void>) | null
  deferContinueProgress?: boolean
  onContinueProgressStart?: ((jobId: string) => void) | null
  onContinueProgressError?: ((message: string) => void) | null
}

export interface PdfReviewHandle {
  continueToGrouping: () => Promise<void>
  getTablesForPersist: () => Array<Record<string, unknown>>
}

declare const PdfReview: ForwardRefExoticComponent<PdfReviewProps & RefAttributes<PdfReviewHandle>>
export default PdfReview

export function PdfTableEditorPage(props: {
  jobId: string
  tableId: string
}): JSX.Element
