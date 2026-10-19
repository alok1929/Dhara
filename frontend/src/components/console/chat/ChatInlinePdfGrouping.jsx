'use client'

import ProcessingStepper from '../ProcessingStepper'
import {
  buildPdfGroupingProgressSteps,
  PDF_GROUPING_PROGRESS_SUBTITLE,
} from '../../../lib/pdfPreviewGroupingProgress'

/**
 * Inline chat task body for PDF preview → grouping progress.
 */
export default function ChatInlinePdfGrouping({
  filename,
  phase = 'persist',
  subtitle = PDF_GROUPING_PROGRESS_SUBTITLE,
}) {
  const steps = buildPdfGroupingProgressSteps(phase)

  return (
    <div className="flex flex-col gap-3">
      {filename ? (
        <div className="text-[13px] font-semibold text-ink">{filename}</div>
      ) : null}
      <div className="text-[12.5px] text-ink-soft">{subtitle}</div>
      <ProcessingStepper steps={steps} />
    </div>
  )
}
