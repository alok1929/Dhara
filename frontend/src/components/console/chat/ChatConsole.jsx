'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import Button from '../../ui/Button'
import ConsoleViewHeader from '../ConsoleViewHeader'
import ConsoleWorkflowPanels from '../ConsoleWorkflowPanels'
import ConsoleStatusPlaceholder from '../ConsoleStatusPlaceholder'
import PdfReview from '../../pdf/PdfReview'
import ChatUploadScreen from './ChatUploadScreen'
import ChatComposer from './ChatComposer'
import ChatScrollRegion from './ChatScrollRegion'
import { CHAT_COMPOSER_HEIGHT, CHAT_MESSAGES_SCROLL_HEIGHT, CHAT_SPLIT_HEIGHT } from './chatLayout'
import ChatInlineProcessing from './ChatInlineProcessing'
import ChatTaskBlock from './ChatTaskBlock'
import ChatRightPanel from './ChatRightPanel'
import {
  clearLegacyChatMessages,
  loadChatActiveJob,
  saveChatActiveJob,
  saveChatReviewJob,
} from '../../../lib/chatPersist'
import {
  fetchConsoleChatSession,
  saveConsoleChatMessages,
} from '../../../lib/consoleChatSession'
import { saveConsoleUiMode, UI_MODES } from '../../../lib/consoleUiMode'
import { stepForChatPillId } from '../../../lib/chatStages'
import {
  catalogFromBatchTables,
  catalogFromPdfResultTables,
  excludeTablesFromMatchResult,
  fetchPdfJobResultTables,
  groupingStageSummary,
  previewStageSummary,
  downloadPdfJobTablesZip,
} from '../../../lib/chatConsoleHelpers'
import { runConsoleTableAiChat, runPdfJobTableAiChat } from '../../../lib/chatTableAiChat'
import { runConsoleTableAiSearch, runPdfJobTableAiSearch } from '../../../lib/chatTableAiSearch'
import {
  buildPreviewChatConversation,
  isPreviewShowFindIntent,
} from '../../../lib/chatPreviewConversation'
import {
  catalogRowsForAiSearch,
  createPreviewAiFindFilter,
  isPreviewAiFindActive,
} from '../../../lib/tablePreviewFilter'
function newId() {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`
}

function StageCard({
  stageId,
  title,
  summary,
  bullets,
  onExpand,
  onVerify,
  verifyLabel = 'Verify & proceed',
  verifyDisabled,
  extra,
}) {
  return (
    <article className="rounded-2xl border border-line/90 bg-white p-4 shadow-sm">
      <div className="text-[11px] font-bold uppercase tracking-wide text-teal">{title}</div>
      <p className="mt-2 text-[14px] leading-relaxed text-ink">{summary}</p>
      {bullets?.length > 0 && (
        <ul className="mt-2 list-disc space-y-1 pl-5 text-[13px] text-ink-soft">
          {bullets.map((b) => (
            <li key={b}>{b}</li>
          ))}
        </ul>
      )}
      {extra}
      <div className="mt-4 flex flex-wrap gap-2">
        {onExpand && (
          <Button variant="secondary" size="sm" onClick={onExpand}>
            Expand preview
          </Button>
        )}
        {onVerify && (
          <Button size="sm" disabled={verifyDisabled} onClick={onVerify}>
            {verifyLabel}
          </Button>
        )}
      </div>
    </article>
  )
}

function ProposalCard({
  count,
  rationale,
  tables,
  selectedIds,
  onToggle,
  onExpand,
  onConfirm,
}) {
  return (
    <article className="rounded-2xl border border-line/90 bg-white p-4">
      <div className="text-[15px] font-semibold text-ink">{count} table{count === 1 ? '' : 's'} identified</div>
      <p className="mt-1.5 text-[13px] text-ink-soft">{rationale}</p>
      <ul className="mt-3 max-h-40 space-y-1 overflow-y-auto text-[12.5px] text-ink">
        {tables.slice(0, 8).map((t) => (
          <li key={t._uid} className="truncate">
            {t.title || t.id} · {t.filename || 'source'}
          </li>
        ))}
        {tables.length > 8 && (
          <li className="text-ink-soft">…and {tables.length - 8} more</li>
        )}
      </ul>
      <div className="mt-3 flex flex-wrap gap-2">
        <Button variant="secondary" size="sm" onClick={onExpand}>
          Expand to review
        </Button>
        <Button size="sm" onClick={onConfirm}>
          Verify & proceed
        </Button>
      </div>
      <div className="mt-2 text-[11px] text-ink-soft">
        {selectedIds.size} of {tables.length} selected for exclusion
      </div>
    </article>
  )
}

export default function ChatConsole({
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
  const [messages, setMessages] = useState([])
  const [messagesReady, setMessagesReady] = useState(false)
  const [composerLoading, setComposerLoading] = useState(false)
  const [workspace, setWorkspace] = useState(null) // { stageId, mode?: 'proposal', proposalId? }
  const [proposalSelection, setProposalSelection] = useState(() => new Set())
  const [activeJobId, setActiveJobId] = useState(() => loadChatActiveJob())
  const [rightPanelDismissed, setRightPanelDismissed] = useState(false)
  /** Chat-owned AI find filter for the right-hand preview (PDF + batch). */
  const [previewAiFilter, setPreviewAiFilter] = useState(null)
  const anchorRefs = useRef({})
  const scrollRootRef = useRef(null)
  const pdfReviewRef = useRef(null)

  const {
    applyReconcile,
    expandedStage,
    goToStep,
    matchResult,
    maxStepReached,
    metadataFilling,
    pdfError,
    pdfUploading,
    pendingDatasetFiles,
    previewTables,
    publishFromClassify,
    requestContinueToMetadata,
    savedIds,
    setExpandedStage,
    setMatchResult,
    setMaxStepReached,
    setPdfError,
    setStep,
    setUploadChoice,
    startDatasetProcessing,
    stageIdx,
    statusPage,
    step,
    step1MetadataFiles,
    unsavedAiFilled,
    unsavedMismatched,
    addPendingDatasetFiles,
    addStep1MetadataFiles,
    removePendingDatasetFile,
    removeStep1MetadataFile,
    chatSessionId,
    beginNewConsoleChatSession,
    linkConsoleChatSessionId,
    pdfReviewJobId,
    pdfReviewFilename,
    setPdfReviewJob,
    continueFromPdfPreview,
  } = pipeline

  const chatHydratedRef = useRef(false)
  const skipChatLoadRef = useRef(null)

  useEffect(() => {
    clearLegacyChatMessages()
  }, [])

  useEffect(() => {
    if (!chatSessionId) {
      setMessages([])
      setMessagesReady(true)
      chatHydratedRef.current = true
      return undefined
    }
    if (skipChatLoadRef.current === chatSessionId) {
      skipChatLoadRef.current = null
      setMessagesReady(true)
      chatHydratedRef.current = true
      return undefined
    }
    let cancelled = false
    setMessagesReady(false)
    chatHydratedRef.current = false
    fetchConsoleChatSession(chatSessionId)
      .then((data) => {
        if (cancelled) return
        setMessages(Array.isArray(data.messages) ? data.messages : [])
        setMessagesReady(true)
        chatHydratedRef.current = true
      })
      .catch(() => {
        if (cancelled) return
        setMessages([])
        setMessagesReady(true)
        chatHydratedRef.current = true
      })
    return () => { cancelled = true }
  }, [chatSessionId])

  useEffect(() => {
    if (!chatSessionId || !messagesReady || !chatHydratedRef.current) return undefined
    const timer = setTimeout(() => {
      saveConsoleChatMessages(chatSessionId, messages).catch(() => {})
    }, 450)
    return () => clearTimeout(timer)
  }, [messages, chatSessionId, messagesReady])

  useEffect(() => {
    const batchId = matchResult?.batch_id
    if (!chatSessionId || !batchId) return
    linkConsoleChatSessionId({ batchId }).catch(() => {})
  }, [chatSessionId, matchResult?.batch_id, linkConsoleChatSessionId])

  const restoredPreviewRef = useRef(false)
  useEffect(() => {
    if (restoredPreviewRef.current) return
    if (!pdfReviewJobId && previewTables.length === 0) return
    restoredPreviewRef.current = true
    setWorkspace((prev) => prev ?? { stageId: 'preview' })
    setMaxStepReached((m) => Math.max(m, 2))
    setStep((s) => (s < 2 ? 2 : s))
  }, [pdfReviewJobId, previewTables.length, setMaxStepReached, setStep])

  useEffect(() => {
    if (step >= 2 || (!pdfReviewJobId && previewTables.length === 0)) return
    setMaxStepReached((m) => Math.max(m, 2))
    setStep(2)
  }, [pdfReviewJobId, previewTables.length, step, setMaxStepReached, setStep])

  useEffect(() => {
    if (!activeJobId) return
    setMessages((prev) => {
      if (prev.some((m) => m.kind === 'task' && m.jobId === activeJobId)) return prev
      return [...prev, {
        id: newId(),
        kind: 'task',
        taskKey: `extract-${activeJobId}`,
        jobId: activeJobId,
        status: 'running',
        collapsed: true,
        title: 'Extracting tables',
        lines: ['Resuming extraction progress…'],
      }]
    })
  }, [activeJobId])

  const appendMessage = useCallback((msg) => {
    setMessages((prev) => [...prev, { id: newId(), ...msg }])
  }, [])

  const upsertTask = useCallback((taskKey, patch) => {
    setMessages((prev) => {
      const idx = prev.findIndex((m) => m.kind === 'task' && m.taskKey === taskKey)
      if (idx < 0) {
        return [...prev, {
          id: newId(),
          kind: 'task',
          taskKey,
          collapsed: true,
          status: 'running',
          lines: [],
          ...patch,
        }]
      }
      const next = [...prev]
      next[idx] = { ...next[idx], ...patch }
      return next
    })
  }, [])

  const toggleTaskCollapsed = useCallback((messageId) => {
    setMessages((prev) => prev.map((m) => (
      m.kind === 'task' && m.id === messageId ? { ...m, collapsed: !m.collapsed } : m
    )))
  }, [])

  const ensureStageAnchor = useCallback((stageId, builder) => {
    setMessages((prev) => {
      if (prev.some((m) => m.kind === 'stage' && m.stageId === stageId)) return prev
      return [...prev, { id: newId(), kind: 'stage', stageId, ...builder() }]
    })
  }, [])

  useEffect(() => {
    if (step === 2 && previewTables.length) {
      const s = previewStageSummary(previewTables, savedIds)
      ensureStageAnchor('preview', () => ({
        title: 'Preview',
        summary: `Extraction complete. I found ${s.total} table${s.total === 1 ? '' : 's'} across your documents.`,
        bullets: [
          `${s.ok} look good.`,
          s.needsFix ? `${s.needsFix} need review.` : null,
          s.aiReview ? `${s.aiReview} filled by AI and need a quick check.` : null,
        ].filter(Boolean),
      }))
    }
  }, [step, previewTables, savedIds, ensureStageAnchor])

  useEffect(() => {
    if (step === 3 && matchResult) {
      const g = groupingStageSummary(matchResult)
      ensureStageAnchor('grouping', () => ({
        title: 'Grouping',
        summary: `Tables are organised into ${g.groups} group${g.groups === 1 ? '' : 's'}.`,
        bullets: [
          `${g.tables} tables in this release.`,
          g.unmatched ? `${g.unmatched} still need a group assignment.` : 'Every table is assigned to a group.',
        ],
      }))
    }
  }, [step, matchResult, ensureStageAnchor])

  useEffect(() => {
    if (step === 4) {
      ensureStageAnchor('grouping-metadata', () => ({
        title: 'Metadata',
        summary: 'Add catalogue metadata for each group before classification.',
        bullets: ['Open the workspace to edit titles, coverage, and required fields.'],
      }))
    }
  }, [step, ensureStageAnchor])

  useEffect(() => {
    if (step === 5) {
      ensureStageAnchor('classification', () => ({
        title: 'Classification',
        summary: 'Map columns to standard concepts and code lists.',
        bullets: ['Review each group, then continue to harmonisation.'],
      }))
    }
  }, [step, ensureStageAnchor])

  useEffect(() => {
    if (step === 6) {
      ensureStageAnchor('harmonisation', () => ({
        title: 'Harmonisation',
        summary: 'Align values across related tables and confirm catalogue placement.',
        bullets: [],
      }))
    }
  }, [step, ensureStageAnchor])

  useEffect(() => {
    if (step === 7) {
      ensureStageAnchor('publish', () => ({
        title: 'Publish',
        summary: 'Complete publication to register API and MCP endpoints for this release.',
        bullets: [],
      }))
    }
  }, [step, ensureStageAnchor])

  const goToStepGuarded = (targetStep) => {
    if (targetStep === 6) {
      requestHarmonisation()
      return
    }
    goToStep(targetStep)
  }

  const openWorkspace = useCallback((stageId) => {
    const targetStep = stageId === 'grouping-metadata' ? 4 : stepForChatPillId(stageId)
    if (targetStep !== step) setStep(targetStep)
    setRightPanelDismissed(false)
    setWorkspace({ stageId: stageId === 'grouping-metadata' ? 'grouping' : stageId })
  }, [setStep, step])

  const applyChatPreviewFind = useCallback((tableIds, { rationale = '', prompt = '' } = {}) => {
    const ids = [...new Set((tableIds || []).map((id) => String(id)).filter(Boolean))]
    if (!ids.length) {
      setPreviewAiFilter(null)
    } else {
      setPreviewAiFilter(createPreviewAiFindFilter({ tableIds: ids, rationale, prompt }))
    }
    openWorkspace('preview')
  }, [openWorkspace])

  const handleInlineJobComplete = useCallback(({ jobId, filename }) => {
    saveChatActiveJob(null)
    setActiveJobId(null)
    setPdfReviewJob(jobId, filename || null)
    setPreviewAiFilter(null)
    linkConsoleChatSessionId({ pdfJobId: jobId }).catch(() => {})
    setWorkspace({ stageId: 'preview' })
    setRightPanelDismissed(false)
    setMaxStepReached((m) => Math.max(m, 2))
    setStep(2)
    setMessages((prev) => prev.map((m) => (
      m.kind === 'task' && m.jobId === jobId
        ? {
          ...m,
          status: 'done',
          collapsed: true,
          title: filename ? `Extracted tables from ${filename}` : 'Extraction complete',
          lines: ['Files uploaded and processed.', 'Preview is ready — ask about your tables or use Verify & proceed.'],
          jobId: null,
        }
        : m
    )))
    ensureStageAnchor('preview', () => ({
      title: 'Preview',
      summary: 'Extraction complete. Review tables in the workspace or ask questions in chat.',
      bullets: [],
    }))
  }, [ensureStageAnchor, setMaxStepReached, setPdfReviewJob, setStep])

  const handleInlineJobError = useCallback((message) => {
    saveChatActiveJob(null)
    const failedJobId = activeJobId
    setActiveJobId(null)
    setPdfError(message || 'Processing failed')
    if (failedJobId) {
      setMessages((prev) => prev.map((m) => (
        m.kind === 'task' && m.jobId === failedJobId
          ? {
            ...m,
            status: 'error',
            collapsed: true,
            title: 'Extraction failed',
            lines: [message || 'Processing failed. Try again or switch to Guided view.'],
            jobId: null,
          }
          : m
      )))
    } else {
      appendMessage({ kind: 'assistant', text: message || 'Processing failed. Try again or switch to Guided view.' })
    }
  }, [activeJobId, appendMessage, setPdfError, upsertTask])

  const handleStartProcessing = async () => {
    if (pdfUploading || !hasLlmKey || !pendingDatasetFiles.length) return
    saveConsoleUiMode(UI_MODES.chat)
    setUploadChoice('xlsx')
    clearLegacyChatMessages()
    setMessages([])
    setMessagesReady(false)
    chatHydratedRef.current = false
    try {
      const newSessionId = await beginNewConsoleChatSession()
      skipChatLoadRef.current = newSessionId
    } catch (e) {
      appendMessage({ kind: 'assistant', text: e.message || 'Could not start a new chat session.' })
      return
    }
    setMessagesReady(true)
    chatHydratedRef.current = true
    saveChatActiveJob(null)
    saveChatReviewJob(null)
    setActiveJobId(null)
    setPdfReviewJob(null, null)
    setPreviewAiFilter(null)
    setRightPanelDismissed(false)
    setWorkspace(null)
    const taskKey = `extract-${Date.now()}`
    upsertTask(taskKey, {
      status: 'running',
      collapsed: true,
      title: 'Extracting tables',
      lines: ['Uploading files and starting extraction…'],
      jobId: null,
    })
    const result = await startDatasetProcessing({ navigate: false })
    if (result?.kind === 'matched') {
      upsertTask(taskKey, {
        status: 'done',
        collapsed: true,
        title: 'Workbooks extracted',
        lines: ['Matched and loaded into preview.'],
        jobId: null,
      })
      setWorkspace({ stageId: 'preview' })
      setRightPanelDismissed(false)
    } else if (result?.kind === 'job' && result.jobId) {
      saveChatActiveJob(result.jobId)
      setActiveJobId(result.jobId)
      linkConsoleChatSessionId({ pdfJobId: result.jobId }).catch(() => {})
      upsertTask(taskKey, {
        jobId: result.jobId,
        lines: ['Uploading files and starting extraction…', 'Extraction is running — progress below.'],
      })
    } else if (result?.kind === 'error') {
      upsertTask(taskKey, {
        status: 'error',
        collapsed: true,
        title: 'Extraction failed',
        lines: [result.message || 'Upload failed.'],
        jobId: null,
      })
    }
  }

  const verifyPreview = async () => {
    if (pdfReviewJobId) {
      try {
        if (pdfReviewRef.current?.continueToGrouping) {
          await pdfReviewRef.current.continueToGrouping()
        } else {
          await continueFromPdfPreview(pdfReviewJobId)
        }
      } catch (e) {
        appendMessage({ kind: 'assistant', text: e.message || 'Could not continue to grouping.' })
        openWorkspace('preview')
      }
      return
    }
    if (unsavedMismatched.length || unsavedAiFilled.length) {
      appendMessage({
        kind: 'assistant',
        text: `Please save corrections for ${unsavedMismatched.length + unsavedAiFilled.length} table(s) in the preview workspace before continuing.`,
      })
      openWorkspace('preview')
      return
    }
    applyReconcile({})
  }

  const verifyGrouping = () => {
    requestContinueToMetadata()
  }

  const verifyClassification = () => {
    if (!classificationComplete) {
      appendMessage({
        kind: 'assistant',
        text: 'Finish classifying columns for each group, then verify again to open harmonisation.',
      })
      openWorkspace('classification')
      return
    }
    requestHarmonisation()
  }

  const verifyHarmonisation = () => {
    publishFromClassify()
  }

  const handleVerifyForStage = (stageId) => {
    if (stageId === 'preview') verifyPreview()
    else if (stageId === 'grouping') verifyGrouping()
    else if (stageId === 'grouping-metadata') requestContinueToMetadata()
    else if (stageId === 'classification') verifyClassification()
    else if (stageId === 'harmonisation') verifyHarmonisation()
  }

  const resolvePreviewCatalog = async () => {
    if (previewTables.length) {
      return { catalog: catalogFromBatchTables(previewTables), tables: previewTables, jobId: null }
    }
    if (pdfReviewJobId) {
      const pdfTables = await fetchPdfJobResultTables(pdfReviewJobId)
      return {
        catalog: catalogFromPdfResultTables(pdfTables),
        tables: pdfTables,
        jobId: pdfReviewJobId,
      }
    }
    return { catalog: [], tables: [], jobId: null }
  }

  const handleUserMessage = async (text) => {
    const conversation = buildPreviewChatConversation(messages)
    appendMessage({ kind: 'user', text })
    if (!hasLlmKey) {
      appendMessage({ kind: 'assistant', text: 'Save an LLM API key in Settings to chat about your tables.' })
      return
    }

    setComposerLoading(true)
    try {
      const { catalog, tables, jobId } = await resolvePreviewCatalog()
      if (!catalog.length) {
        appendMessage({
          kind: 'assistant',
          text: step <= 1
            ? 'Upload files and start extraction first — then I can answer questions about your tables.'
            : 'No table catalog is available at this step yet.',
        })
        return
      }

      let data = jobId
        ? await runPdfJobTableAiChat(jobId, text, catalog, { conversation })
        : await runConsoleTableAiChat(text, catalog, { conversation })

      let action = data.action === 'remove' ? 'remove' : data.action === 'find' ? 'find' : 'none'
      let findIds = (data.table_ids || []).map(String).filter(Boolean)

      const needsSearchFallback = action !== 'remove' && (
        (action === 'find' && !findIds.length)
        || (action === 'none' && isPreviewShowFindIntent(text))
      )
      if (needsSearchFallback) {
        const searchRows = catalogRowsForAiSearch(tables, { pdfJob: Boolean(jobId) })
        const searchPrompt = [text, ...conversation.map((t) => t.content)].join('\n\n')
        const searchResult = jobId
          ? await runPdfJobTableAiSearch(jobId, searchPrompt, searchRows)
          : await runConsoleTableAiSearch(searchPrompt, searchRows)
        if (searchResult.intent !== 'remove' && searchResult.table_ids?.length) {
          action = 'find'
          findIds = searchResult.table_ids.map(String)
          data = {
            ...data,
            reply: searchResult.rationale || data.reply || `Showing ${findIds.length} table(s) in the preview.`,
          }
        }
      }

      appendMessage({ kind: 'assistant', text: data.reply || 'Done.' })

      const idSet = new Set(findIds)
      const batchTables = previewTables.length ? previewTables : []
      const matched = batchTables.length
        ? batchTables.filter((t) => idSet.has(String(t._uid)))
        : tables.filter((t) => idSet.has(String(t.table_id)))

      if (action === 'remove' && matched.length) {
        const proposalId = newId()
        const uids = matched.map((t) => t._uid || t.table_id)
        setProposalSelection(new Set(uids))
        appendMessage({
          kind: 'proposal',
          proposalId,
          rationale: 'Review this selection before excluding tables from grouping.',
          tables: matched.map((t) => (t._uid ? t : { ...t, _uid: t.table_id })),
          intent: 'remove',
        })
      } else if (action === 'find') {
        applyChatPreviewFind(findIds, { rationale: data.reply || '', prompt: text })
      }
    } catch (e) {
      appendMessage({ kind: 'assistant', text: e.message || 'Could not interpret that request.' })
    } finally {
      setComposerLoading(false)
    }
  }

  const confirmProposal = (msg) => {
    const ids = [...proposalSelection]
    if (!ids.length) {
      appendMessage({ kind: 'assistant', text: 'Select at least one table to exclude.' })
      return
    }
    const next = excludeTablesFromMatchResult(matchResult, ids)
    setMatchResult(next)
    appendMessage({
      kind: 'assistant',
      text: `Excluded ${ids.length} table${ids.length === 1 ? '' : 's'} from this release. Grouping totals have been updated.`,
    })
    setWorkspace(null)
  }

  const showUpload = step === 1 && !previewTables.length && !statusPage && !activeJobId && !pdfReviewJobId
  const showChat = !showUpload

  const chatPreviewAvailable = Boolean(
    pdfReviewJobId || (step >= 2 && previewTables.length > 0),
  )
  const rightPanelStageId = workspace?.stageId
    ?? (!rightPanelDismissed && chatPreviewAvailable ? 'preview' : null)

  const showRightPanel = showChat && !statusPage && Boolean(rightPanelStageId) && !rightPanelDismissed

  const workspaceTitle = {
    preview: 'Preview',
    grouping: step === 4 ? 'Metadata' : 'Grouping',
    classification: 'Classification',
    harmonisation: 'Harmonisation',
    publish: 'Publish',
  }[rightPanelStageId] || 'Workspace'

  const closeRightPanel = () => {
    setWorkspace(null)
    setRightPanelDismissed(true)
  }

  const previewAiFindTableIds = isPreviewAiFindActive(previewAiFilter)
    ? previewAiFilter.tableIds
    : null

  const showComposer = showChat && !statusPage
  const messagesScrollHeight = showComposer ? CHAT_MESSAGES_SCROLL_HEIGHT : CHAT_SPLIT_HEIGHT

  return (
    <div className="console-chat-screen flex flex-col gap-5 overflow-hidden">
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

      <div
        className={`flex min-h-0 gap-3 overflow-hidden ${showRightPanel ? 'flex-row' : 'flex-col'}`}
        style={{ height: CHAT_SPLIT_HEIGHT, maxHeight: CHAT_SPLIT_HEIGHT }}
      >
        <div
          ref={scrollRootRef}
          className={`flex min-h-0 min-w-0 flex-col ${showRightPanel ? 'w-[min(440px,42%)] flex-none' : 'flex-1'}`}
          style={{ height: CHAT_SPLIT_HEIGHT, maxHeight: CHAT_SPLIT_HEIGHT }}
        >
          <ChatScrollRegion height={messagesScrollHeight} className="px-2">
            {showUpload && (
              <ChatUploadScreen
                hasLlmKey={hasLlmKey}
                onGoSettings={onGoSettings}
                datasetFiles={pendingDatasetFiles}
                metadataFiles={step1MetadataFiles}
                onDatasetAdd={addPendingDatasetFiles}
                onDatasetRemove={removePendingDatasetFile}
                onMetadataAdd={addStep1MetadataFiles}
                onMetadataRemove={removeStep1MetadataFile}
                onStartProcessing={handleStartProcessing}
                processing={pdfUploading}
                error={pdfError}
                onClearError={() => setPdfError('')}
              />
            )}

            {statusPage && (
              <div className="rounded-2xl border border-line/90 bg-white p-5">
                <ConsoleStatusPlaceholder
                  key={statusPage.key}
                  title={statusPage.title}
                  subtitle={statusPage.subtitle}
                  steps={statusPage.steps}
                  work={statusPage.work || null}
                  msPerStep={statusPage.msPerStep || 850}
                  onComplete={statusPage.after}
                />
              </div>
            )}

            {showChat && !statusPage && (
              <div className="mx-auto flex max-w-3xl flex-col gap-4 py-2">
                {messages.map((m) => {
                  if (m.kind === 'task') {
                    return (
                      <ChatTaskBlock
                        key={m.id}
                        task={m}
                        onToggleCollapsed={toggleTaskCollapsed}
                      >
                        {m.status === 'running' && m.jobId && activeJobId === m.jobId && (
                          <ChatInlineProcessing
                            jobId={m.jobId}
                            onComplete={handleInlineJobComplete}
                            onError={handleInlineJobError}
                            compact
                          />
                        )}
                      </ChatTaskBlock>
                    )
                  }
                  if (m.kind === 'user') {
                    return (
                      <div key={m.id} className="flex justify-end">
                        <div className="max-w-[85%] rounded-2xl rounded-br-md bg-teal-deep px-4 py-2.5 text-[14px] text-cream">
                          {m.text}
                        </div>
                      </div>
                    )
                  }
                  if (m.kind === 'status') {
                    return null
                  }
                  if (m.kind === 'assistant') {
                    return (
                      <div key={m.id} className="flex justify-start">
                        <div className="max-w-[90%] rounded-2xl rounded-bl-md border border-line/80 bg-white px-4 py-2.5 text-[14px] text-ink">
                          {m.text}
                        </div>
                      </div>
                    )
                  }
                  if (m.kind === 'stage') {
                    const sid = m.stageId
                    const pdfJobId = matchResult?.pdf_job_id
                    const downloadExtra = sid === 'preview' && pdfJobId ? (
                      <div className="mt-3">
                        <Button
                          variant="secondary"
                          size="sm"
                          onClick={() => {
                            downloadPdfJobTablesZip(pdfJobId).catch((e) => {
                              appendMessage({ kind: 'assistant', text: e.message || 'Download failed.' })
                            })
                          }}
                        >
                          Download extracted tables (ZIP)
                        </Button>
                      </div>
                    ) : null
                    return (
                      <div
                        key={m.id}
                        ref={(el) => { anchorRefs.current[sid] = el }}
                        data-chat-stage={sid}
                      >
                        <StageCard
                          stageId={sid}
                          title={m.title}
                          summary={m.summary}
                          bullets={m.bullets}
                          extra={downloadExtra}
                          onExpand={
                            sid !== 'publish' && !(showRightPanel && sid === 'preview')
                              ? () => openWorkspace(sid.replace('-metadata', ''))
                              : undefined
                          }
                          onVerify={sid !== 'publish' ? () => handleVerifyForStage(sid) : undefined}
                          verifyDisabled={sid === 'grouping' && metadataFilling}
                        />
                      </div>
                    )
                  }
                  if (m.kind === 'proposal') {
                    return (
                      <div key={m.id}>
                        <ProposalCard
                          count={m.tables.length}
                          rationale={m.rationale}
                          tables={m.tables}
                          selectedIds={proposalSelection}
                          onExpand={() => {
                            setWorkspace({ stageId: 'preview', mode: 'proposal', proposalId: m.proposalId })
                            setProposalSelection(new Set(m.tables.map((t) => t._uid)))
                          }}
                          onConfirm={() => confirmProposal(m)}
                        />
                      </div>
                    )
                  }
                  return null
                })}
              </div>
            )}
          </ChatScrollRegion>

          {showComposer && (
            <div
              className="flex flex-none items-center px-2 pt-2"
              style={{ height: CHAT_COMPOSER_HEIGHT, minHeight: CHAT_COMPOSER_HEIGHT }}
            >
              <ChatComposer
                onSend={handleUserMessage}
                disabled={!hasLlmKey}
                loading={composerLoading}
              />
            </div>
          )}
        </div>

        {showRightPanel && (
          <ChatRightPanel
            title={
              rightPanelStageId === 'preview' && pdfReviewFilename
                ? pdfReviewFilename
                : workspaceTitle
            }
            compact={rightPanelStageId === 'preview'}
            panelHeight={CHAT_SPLIT_HEIGHT}
            contentClassName={
              rightPanelStageId === 'preview' && pdfReviewJobId ? 'px-2 py-2' : 'p-3 sm:p-4'
            }
            onClose={closeRightPanel}
            onVerify={() => handleVerifyForStage(
              rightPanelStageId === 'grouping' && step === 4 ? 'grouping-metadata' : rightPanelStageId,
            )}
          >
            {rightPanelStageId === 'preview' && pdfReviewJobId ? (
              <PdfReview
                ref={pdfReviewRef}
                embedded
                compact
                jobId={pdfReviewJobId}
                filename={pdfReviewFilename}
                previewAiFilter={previewAiFilter}
                onPreviewAiFilterChange={setPreviewAiFilter}
                onDone={() => {
                  setPdfReviewJob(null, null)
                  setPreviewAiFilter(null)
                  setWorkspace(null)
                }}
                onContinueToGrouping={(id, persistResponse) => {
                  continueFromPdfPreview(id, persistResponse)
                    .then(() => setWorkspace(null))
                    .catch((e) => {
                      appendMessage({ kind: 'assistant', text: e.message || 'Could not load grouping.' })
                    })
                }}
              />
            ) : rightPanelStageId === 'preview' && previewTables.length > 0 ? (
              <ConsoleWorkflowPanels
                layout="workspace"
                forcePreview
                previewAiFindTableIds={previewAiFindTableIds}
                onClearPreviewAiFind={() => setPreviewAiFilter(null)}
                previewAiFindRationale={previewAiFilter?.rationale}
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
            ) : rightPanelStageId === 'preview' ? (
              <div className="rounded-xl border border-dashed border-line/90 bg-white/80 px-4 py-12 text-center text-[13px] text-ink-soft">
                Preview will appear here when extraction finishes.
              </div>
            ) : (
              <ConsoleWorkflowPanels
                layout="workspace"
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
          </ChatRightPanel>
        )}
      </div>
    </div>
  )
}
