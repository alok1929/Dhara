'use client'

import ConsoleViewModeSwitch from './ConsoleViewModeSwitch'
import { StageSidebar } from './ConsoleStages'

/** Shared chrome: stage stepper and view-mode toggle on one row. */
export default function ConsoleViewHeader({
  uiMode,
  onUiModeChange,
  stageIdx,
  step,
  maxStepReached,
  expandedStage,
  setExpandedStage,
  goToStep,
  isStepReachable,
  chatDisabled = false,
}) {
  return (
    <div className="flex flex-wrap items-center gap-3">
      <div className="min-w-0 flex-1">
        <StageSidebar
          stageIdx={stageIdx}
          step={step}
          maxStepReached={maxStepReached}
          expandedStage={expandedStage}
          setExpandedStage={setExpandedStage}
          goToStep={goToStep}
          isStepReachable={isStepReachable}
        />
      </div>
      <ConsoleViewModeSwitch mode={uiMode} onChange={onUiModeChange} chatDisabled={chatDisabled} />
    </div>
  )
}
