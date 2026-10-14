'use client'

import { ArrowLeft } from 'lucide-react'
import KydsSummaryCard from '../KydsSummaryCard'
import ConsoleWorkflowPanels from './ConsoleWorkflowPanels'
import { withinStageBack } from './ConsoleStages'
import ClassifyBreadcrumb from './classify/ClassifyBreadcrumb'
import ConsoleViewHeader from './ConsoleViewHeader'
import PdfReview from '../pdf/PdfReview'

export default function ConsoleGuidedView({
  uiMode,
  onUiModeChange,
  pipeline,
  hasLlmKey,
  hasKey,
  onGoSettings,
  onGoDashboard,
  onGoCatalogue,
  onUploadAnother,
  classificationComplete,
  setClassificationComplete,
  goToHarmRef,
  requestHarmonisation,
}) {
  const {
    expandedStage,
    goToStep,
    info,
    maxStepReached,
    setExpandedStage,
    setStep,
    stageIdx,
    statusPage,
    step,
    pdfReviewJobId,
    pdfReviewFilename,
    setPdfReviewJob,
    continueFromPdfPreview,
  } = pipeline

  const stageBack = withinStageBack(step)
  const showPdfPreview = Boolean(pdfReviewJobId && step === 2 && !statusPage)

  const goToStepGuarded = (targetStep) => {
    if (targetStep === 6) {
      requestHarmonisation()
      return
    }
    goToStep(targetStep)
  }

  return (
    <div className="flex flex-col gap-5">
      <ConsoleViewHeader
        uiMode={uiMode}
        onUiModeChange={onUiModeChange}
        stageIdx={stageIdx}
        step={step}
        maxStepReached={maxStepReached}
        expandedStage={expandedStage}
        setExpandedStage={setExpandedStage}
        goToStep={goToStepGuarded}
        isStepReachable={(s) => {
          if (s === 6) return classificationComplete
          return s <= maxStepReached
        }}
      />

      <div key={step === 5 || step === 6 ? 'classify-harmonise' : step} className="dhara-page-enter flex min-w-0 flex-1 flex-col gap-[18px]">
        {!statusPage && !showPdfPreview && (
          <div className="flex flex-col">
            {stageBack && (
              <div
                className="mb-3.5 inline-flex cursor-pointer items-center gap-1.5 text-[14px] font-medium text-teal transition-colors duration-dhara ease-dhara hover:text-teal-dark"
                onClick={() => setStep(stageBack.step)}
              >
                <ArrowLeft className="h-4 w-4" strokeWidth={1.75} aria-hidden />
                {stageBack.label}
              </div>
            )}
            <div className="flex items-center justify-between gap-6">
              <div>
                {(step === 5 || step === 6) ? (
                  <ClassifyBreadcrumb
                    phase={step === 6 ? 'harmonisation' : 'classification'}
                    canOpenHarmonisation={classificationComplete}
                    onNavigate={(next) => {
                      if (next === 'harmonisation') requestHarmonisation()
                      else setStep(5)
                    }}
                    size="page"
                  />
                ) : (
                  <div className="dhara-page-title">{info.title}</div>
                )}
              </div>
              {step >= 1 && step <= 4 && (
                <div className="flex flex-none flex-shrink-0 flex-wrap items-center justify-end gap-2.5">
                  <KydsSummaryCard variant="corner" />
                </div>
              )}
            </div>
          </div>
        )}

        {showPdfPreview ? (
          <div className="flex flex-col gap-5 rounded-2xl border border-line/90 bg-white p-5 sm:p-6">
            <PdfReview
              embedded
              jobId={pdfReviewJobId}
              filename={pdfReviewFilename}
              onDone={() => setPdfReviewJob(null, null)}
              onContinueToGrouping={(id, persistResponse) => {
                continueFromPdfPreview(id, persistResponse).catch(() => {})
              }}
            />
          </div>
        ) : (
          <ConsoleWorkflowPanels
            layout="guided"
            hasLlmKey={hasLlmKey}
            hasKey={hasKey}
            onGoSettings={onGoSettings}
            onGoDashboard={onGoDashboard}
            onGoCatalogue={onGoCatalogue}
            onUploadAnother={onUploadAnother}
            pipeline={pipeline}
            classificationComplete={classificationComplete}
            setClassificationComplete={setClassificationComplete}
            goToHarmRef={goToHarmRef}
          />
        )}
      </div>
    </div>
  )
}
