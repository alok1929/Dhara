'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { useConsolePipeline } from './useConsolePipeline'
import { useApp } from '../../context/AppContext'
import { loadConsoleUiMode, saveConsoleUiMode, UI_MODES } from '../../lib/consoleUiMode'
import { isChatModeAllowedForStep } from '../../lib/chatStages'
import ConsoleGuidedView from './ConsoleGuidedView'
import ChatConsole from './chat/ChatConsole'
import Toast from '../ui/Toast'

export default function Console({ hasKey, onGoSettings, onGoDashboard, onGoCatalogue, onUploadAnother }) {
  const { keySaved } = useApp()
  const hasLlmKey = hasKey || keySaved
  const pipeline = useConsolePipeline()
  const { setStep, syncGuidedPreviewStep, step } = pipeline

  const [uiMode, setUiMode] = useState(() => loadConsoleUiMode())
  const [modeToast, setModeToast] = useState(null)
  const [classificationComplete, setClassificationComplete] = useState(false)
  const goToHarmRef = useRef(null)

  useEffect(() => {
    if (!modeToast) return undefined
    const timer = setTimeout(() => setModeToast(null), 3500)
    return () => clearTimeout(timer)
  }, [modeToast])

  useEffect(() => {
    if (isChatModeAllowedForStep(step) || uiMode !== UI_MODES.chat) return
    saveConsoleUiMode(UI_MODES.guided)
    setUiMode(UI_MODES.guided)
    setModeToast('Chat is available through Grouping. Switched to Guided view.')
  }, [step, uiMode])

  const onUiModeChange = useCallback((mode) => {
    if (mode === uiMode) return
    if (mode === UI_MODES.chat && !isChatModeAllowedForStep(step)) {
      setModeToast('Chat is available through Grouping only.')
      return
    }
    saveConsoleUiMode(mode)
    if (mode === UI_MODES.guided) {
      syncGuidedPreviewStep()
    }
    setUiMode(mode)
    setModeToast(mode === UI_MODES.chat ? 'Switched to Chat mode' : 'Switched to Guided mode')
  }, [uiMode, syncGuidedPreviewStep])

  const requestHarmonisation = () => {
    if (goToHarmRef.current) goToHarmRef.current()
    else if (classificationComplete) setStep(6)
  }

  const shared = {
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
  }

  return (
    <>
      {uiMode === UI_MODES.chat ? <ChatConsole {...shared} /> : <ConsoleGuidedView {...shared} />}
      {modeToast && (
        <Toast
          message={modeToast}
          tone="info"
          onDismiss={() => setModeToast(null)}
        />
      )}
    </>
  )
}
