'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import Button from '../../ui/Button'
import ConsoleViewHeader from '../ConsoleViewHeader'
import ConsoleWorkflowPanels from '../ConsoleWorkflowPanels'
import ConsoleStatusPlaceholder from '../ConsoleStatusPlaceholder'
import ProcessingStepper from '../ProcessingStepper'
import PdfReview from '../../pdf/PdfReview'
import ChatUploadScreen from './ChatUploadScreen'
import ChatComposer from './ChatComposer'
import ChatScrollRegion from './ChatScrollRegion'
import {
  CHAT_COMPOSER_HEIGHT,
  CHAT_MESSAGES_SCROLL_HEIGHT,
  CHAT_SPLIT_CHAT_WIDTH,
  CHAT_SPLIT_HEIGHT,
  CHAT_SPLIT_WORKSPACE_CLASS,
} from './chatLayout'
import ChatInlineProcessing from './ChatInlineProcessing'
import ChatInlinePdfGrouping from './ChatInlinePdfGrouping'
import ChatStageArtifact from './ChatStageArtifact'
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
import { requestAppSidebarCollapse } from '../../../lib/appSidebar'
import {
  catalogFromBatchTables,
  catalogFromPdfResultTables,
  excludeTablesFromMatchResult,
  fetchPdfJobResultTables,
  groupingStageSummary,
  previewStageSummary,
  downloadPdfJobTablesZip,
} from '../../../lib/chatConsoleHelpers'
import {
  persistPdfApprovedAndLoadGrouping,
  PDF_GROUPING_PROGRESS_SUBTITLE,
} from '../../../lib/pdfPreviewGroupingProgress'
import { STATUS_TRANSITIONS } from '../../../lib/consoleStatusTransitions'
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

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

function buildStatusTransitionSteps(steps, activeIdx) {
  return (steps || []).map((s, i) => ({
    key: s.key || `step-${i}`,
    label: s.label,
    status: i < activeIdx ? 'done' : i === activeIdx ? 'active' : 'pending',
  }))
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
  /** Chat-owned AI find filter for the right-hand preview (PDF + batch). */
  const [previewAiFilter, setPreviewAiFilter] = useState(null)
  const [groupingPhase, setGroupingPhase] = useState('persist')
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

  // Restore step to preview when a PDF/batch result exists — do not auto-open workspace.
  useEffect(() => {
    if (!pdfReviewJobId && previewTables.length === 0) return
    if (step >= 3) return
    setMaxStepReached((m) => Math.max(m, 2))
    setStep((s) => (s < 2 ? 2 : s))
  }, [pdfReviewJobId, previewTables.length, setMaxStepReached, setStep, step])

  // Close inspect split when leaving preview step (e.g. after trust-path verify).
  useEffect(() => {
    if (step < 3) return
    setWorkspace((prev) => (prev?.stageId === 'preview' ? null : prev))
  }, [step])

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
    if (step !== 2) return
    if (pdfReviewJobId) {
      ensureStageAnchor('preview', () => ({
        title: 'Preview',
        subtitle: pdfReviewFilename || undefined,
        summary: 'Extraction complete. Verify & proceed to continue, or Expand to inspect tables.',
        bullets: [],
      }))
      return
    }
    if (previewTables.length) {
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
  }, [step, previewTables, savedIds, ensureStageAnchor, pdfReviewJobId, pdfReviewFilename])

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
    setWorkspace({ stageId: stageId === 'grouping-metadata' ? 'grouping' : stageId })
    requestAppSidebarCollapse()
  }, [setStep, step])

  const closeWorkspace = useCallback(() => {
    setWorkspace(null)
  }, [])

  const runChatStatusTransition = useCallback(async (transitionKey, { title, onDone } = {}) => {
    const cfg = STATUS_TRANSITIONS[transitionKey]
    if (!cfg) {
      onDone?.()
      return
    }
    const taskKey = `transition-${transitionKey}-${Date.now()}`
    upsertTask(taskKey, {
      taskVariant: 'status-transition',
      title: title || cfg.title,
      lines: [cfg.subtitle],
      status: 'running',
      collapsed: true,
      transitionSteps: cfg.steps,
      transitionActiveIdx: 0,
    })
    const stepCount = cfg.steps?.length || 1
    for (let i = 0; i < stepCount; i += 1) {
      upsertTask(taskKey, { transitionActiveIdx: i })
      await sleep(cfg.msPerStep || 850)
    }
    upsertTask(taskKey, {
      status: 'done',
      collapsed: true,
      transitionActiveIdx: stepCount,
      lines: [cfg.subtitle, 'Done.'],
    })
    onDone?.()
  }, [upsertTask])

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
    setWorkspace(null)
    setMaxStepReached((m) => Math.max(m, 2))
    setStep(2)
    setMessages((prev) => prev.map((m) => (
      m.kind === 'task' && m.jobId === jobId
        ? {
          ...m,
          status: 'done',
          collapsed: true,
          title: filename ? `Extracted tables from ${filename}` : 'Extraction complete',
          lines: ['Files uploaded and processed.', 'Verify & proceed to continue, or Expand to inspect tables.'],
          jobId: null,
        }
        : m
    )))
    ensureStageAnchor('preview', () => ({
      title: 'Preview',
      subtitle: filename || undefined,
      summary: 'Extraction complete. Verify & proceed to continue, or Expand to inspect tables.',
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
        lines: ['Matched and loaded. Verify & proceed to continue, or Expand to inspect.'],
        jobId: null,
      })
      setWorkspace(null)
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
      const jobId = pdfReviewJobId
      const filename = pdfReviewFilename || 'pdf'
      const taskKey = `pdf-grouping-${jobId}`
      // Capture edits from open inspect panel before closing it.
      const tablesFromPanel = workspace?.stageId === 'preview'
        ? pdfReviewRef.current?.getTablesForPersist?.()
        : null

      setWorkspace(null)
      setGroupingPhase('persist')
      upsertTask(taskKey, {
        taskVariant: 'pdf-grouping',
        title: filename,
        filename,
        lines: [PDF_GROUPING_PROGRESS_SUBTITLE],
        status: 'running',
        collapsed: true,
        phase: 'persist',
      })

      try {
        let tables = tablesFromPanel
        if (!tables?.length) {
          tables = await fetchPdfJobResultTables(jobId).catch(() => undefined)
        }
        const { matchResult: nextMatch, persistData } = await persistPdfApprovedAndLoadGrouping(jobId, {
          tables,
          sourceFile: filename,
          onPhase: (phase) => {
            setGroupingPhase(phase)
            upsertTask(taskKey, { phase })
          },
        })
        if (persistData?.grouping) {
          await continueFromPdfPreview(jobId, persistData)
        } else if (nextMatch) {
          setMatchResult(nextMatch)
          setPdfReviewJob(null, null)
          setMaxStepReached((m) => Math.max(m, 3))
          setStep(3)
        } else {
          throw new Error('Could not load grouping after preview')
        }
        upsertTask(taskKey, {
          status: 'done',
          collapsed: true,
          phase: 'done',
          lines: [PDF_GROUPING_PROGRESS_SUBTITLE, 'Grouping ready — Verify & proceed or Expand to review groups.'],
        })
      } catch (e) {
        upsertTask(taskKey, {
          status: 'error',
          collapsed: false,
          lines: [e.message || 'Could not continue to grouping.'],
        })
        appendMessage({ kind: 'assistant', text: e.message || 'Could not continue to grouping.' })
      }
      return
    }

    if (unsavedMismatched.length || unsavedAiFilled.length) {
      appendMessage({
        kind: 'assistant',
        text: `Please Expand preview and save corrections for ${unsavedMismatched.length + unsavedAiFilled.length} table(s) before continuing.`,
      })
      return
    }

    await runChatStatusTransition('previewToGrouping', {
      title: 'Preparing grouping',
      onDone: () => applyReconcile({}, { skipStatusPage: true }),
    })
  }

  const verifyGrouping = () => {
    setWorkspace(null)
    requestContinueToMetadata()
  }

  const verifyClassification = () => {
    if (!classificationComplete) {
      appendMessage({
        kind: 'assistant',
        text: 'Expand classification to finish mapping columns, then Verify & proceed again.',
      })
      return
    }
    setWorkspace(null)
    requestHarmonisation()
  }

  const verifyHarmonisation = () => {
    setWorkspace(null)
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

  // statusPage is suppressed in chat for transitions we handle inline (preview→grouping).
  const chatOwnsTransition = statusPage?.key === 'previewToGrouping'
  const showUpload = step === 1 && !previewTables.length && !statusPage && !activeJobId && !pdfReviewJobId
  const showChat = !showUpload

  const isPdfRelease = Boolean(pdfReviewJobId || matchResult?.pdf_job_id)
  // Inspect path only: workspace is set explicitly via Expand / find filter.
  const rightPanelStageId = workspace?.stageId || null
  const showRightPanel = showChat && Boolean(rightPanelStageId) && !chatOwnsTransition

  const workspaceTitle = {
    preview: 'Preview',
    grouping: step === 4 ? 'Metadata' : 'Grouping',
    classification: 'Classification',
    harmonisation: 'Harmonisation',
    publish: 'Publish',
  }[rightPanelStageId] || 'Workspace'

  const previewAiFindTableIds = isPreviewAiFindActive(previewAiFilter)
    ? previewAiFilter.tableIds
    : null

  const showComposer = showChat && (!statusPage || chatOwnsTransition)
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
          className={`flex min-h-0 min-w-0 flex-col ${showRightPanel ? 'flex-none' : 'flex-1'}`}
          style={{
            height: CHAT_SPLIT_HEIGHT,
            maxHeight: CHAT_SPLIT_HEIGHT,
            width: showRightPanel ? CHAT_SPLIT_CHAT_WIDTH : undefined,
          }}
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

            {statusPage && !chatOwnsTransition && (
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

            {showChat && (!statusPage || chatOwnsTransition) && (
              <div className="mx-auto flex max-w-3xl flex-col gap-4 py-2">
                {messages.map((m) => {
                  if (m.kind === 'task') {
                    return (
                      <ChatTaskBlock
                        key={m.id}
                        task={m}
                        onToggleCollapsed={toggleTaskCollapsed}
                      >
                        {m.taskVariant === 'pdf-grouping' && (
                          <ChatInlinePdfGrouping
                            filename={m.filename || m.title}
                            phase={m.phase || groupingPhase}
                          />
                        )}
                        {m.taskVariant === 'status-transition' && (
                          <ProcessingStepper
                            steps={buildStatusTransitionSteps(
                              m.transitionSteps,
                              m.transitionActiveIdx ?? 0,
                            )}
                          />
                        )}
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
                    const pdfJobId = matchResult?.pdf_job_id || pdfReviewJobId
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
                    const expandStageId = sid.replace('-metadata', '')
                    const expandLabel = sid === 'preview' ? 'Expand' : 'Expand'
                    return (
                      <div
                        key={m.id}
                        ref={(el) => { anchorRefs.current[sid] = el }}
                        data-chat-stage={sid}
                      >
                        <ChatStageArtifact
                          title={m.title}
                          subtitle={m.subtitle || (sid === 'preview' ? pdfReviewFilename : undefined)}
                          summary={m.summary}
                          bullets={m.bullets}
                          extra={downloadExtra}
                          expandLabel={expandLabel}
                          onExpand={
                            sid !== 'publish' && workspace?.stageId !== expandStageId
                              ? () => openWorkspace(expandStageId)
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
                            setProposalSelection(new Set(m.tables.map((t) => t._uid)))
                            openWorkspace('preview')
                            setWorkspace({
                              stageId: 'preview',
                              mode: 'proposal',
                              proposalId: m.proposalId,
                            })
                            requestAppSidebarCollapse()
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
          <div className={CHAT_SPLIT_WORKSPACE_CLASS}>
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
              onClose={closeWorkspace}
              onVerify={() => handleVerifyForStage(
                rightPanelStageId === 'grouping' && step === 4 ? 'grouping-metadata' : rightPanelStageId,
              )}
            >
              {rightPanelStageId === 'preview' && pdfReviewJobId ? (
                <PdfReview
                  ref={pdfReviewRef}
                  embedded
                  compact
                  deferContinueProgress
                  jobId={pdfReviewJobId}
                  filename={pdfReviewFilename}
                  previewAiFilter={previewAiFilter}
                  onPreviewAiFilterChange={setPreviewAiFilter}
                  onDone={() => {
                    setPdfReviewJob(null, null)
                    setPreviewAiFilter(null)
                    setWorkspace(null)
                  }}
                  onContinueProgressStart={(id) => {
                    const filename = pdfReviewFilename || 'pdf'
                    const taskKey = `pdf-grouping-${id}`
                    setWorkspace(null)
                    setGroupingPhase('persist')
                    upsertTask(taskKey, {
                      taskVariant: 'pdf-grouping',
                      title: filename,
                      filename,
                      lines: [PDF_GROUPING_PROGRESS_SUBTITLE],
                      status: 'running',
                      collapsed: true,
                      phase: 'persist',
                    })
                    setTimeout(() => {
                      setGroupingPhase('group')
                      upsertTask(taskKey, { phase: 'group' })
                    }, 900)
                  }}
                  onContinueProgressError={(message) => {
                    const taskKey = `pdf-grouping-${pdfReviewJobId}`
                    upsertTask(taskKey, {
                      status: 'error',
                      collapsed: false,
                      lines: [message || 'Could not continue to grouping.'],
                    })
                    appendMessage({ kind: 'assistant', text: message || 'Could not continue to grouping.' })
                  }}
                  onContinueToGrouping={async (id, persistResponse) => {
                    // PdfReview already persisted — apply result in chat without a second persist.
                    const filename = pdfReviewFilename || 'pdf'
                    const taskKey = `pdf-grouping-${id}`
                    try {
                      await continueFromPdfPreview(id, persistResponse)
                      upsertTask(taskKey, {
                        status: 'done',
                        collapsed: true,
                        phase: 'done',
                        lines: [PDF_GROUPING_PROGRESS_SUBTITLE, 'Grouping ready — Verify & proceed or Expand to review groups.'],
                      })
                    } catch (e) {
                      upsertTask(taskKey, {
                        status: 'error',
                        collapsed: false,
                        lines: [e.message || 'Could not load grouping.'],
                      })
                      appendMessage({ kind: 'assistant', text: e.message || 'Could not load grouping.' })
                    }
                  }}
                />
              ) : rightPanelStageId === 'preview' && previewTables.length > 0 && !isPdfRelease && step === 2 && !pdfReviewJobId ? (
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
          </div>
        )}
      </div>
    </div>
  )
}
