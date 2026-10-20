'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import Button from '../../ui/Button'
import ConsoleViewHeader from '../ConsoleViewHeader'
import ConsoleWorkflowPanels from '../ConsoleWorkflowPanels'
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
import ChatFloatingProceed from './ChatFloatingProceed'
import ChatTableResultBlock from './ChatTableResultBlock'
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
import { isChatModeAllowedForStep, stepForChatPillId } from '../../../lib/chatStages'
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
  deletePdfJobTables,
  filterReviewNeededTables,
  isReviewNeededIntent,
  rowsFromMatchedTables,
} from '../../../lib/chatPreviewActions'
import { postLlmInput } from '../../../lib/llmPreviewClient'
import { pdfGroupingToMatchResult } from '../../../lib/postPreview'
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
  const [activeJobId, setActiveJobId] = useState(() => loadChatActiveJob())
  /** Chat-owned AI find filter for the right-hand preview (PDF + batch). */
  const [previewAiFilter, setPreviewAiFilter] = useState(null)
  const [previewFocusTableId, setPreviewFocusTableId] = useState(null)
  const [groupingPhase, setGroupingPhase] = useState('persist')
  const [proceeding, setProceeding] = useState(false)
  const [deletingMessageId, setDeletingMessageId] = useState(null)
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
    setStatusPage,
    setMetaLabel,
    setMetadataId,
    setMetadataIds,
    setPendingGroups,
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
        summary: 'Your PDF has been uploaded and is in Preview.',
        bullets: [],
      }))
      return
    }
    if (previewTables.length) {
      const s = previewStageSummary(previewTables, savedIds)
      ensureStageAnchor('preview', () => ({
        title: 'Preview',
        summary: `Your files have been uploaded and are in Preview. I found ${s.total} table${s.total === 1 ? '' : 's'} across your documents.`,
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

  const goToStepGuarded = (targetStep) => {
    if (targetStep === 6) {
      requestHarmonisation()
      return
    }
    goToStep(targetStep)
  }

  const openWorkspace = useCallback((stageId) => {
    if (!isChatModeAllowedForStep(step)) return
    const normalized = stageId === 'grouping-metadata' ? 'grouping' : stageId
    if (!['preview', 'grouping'].includes(normalized)) return
    const targetStep = stageId === 'grouping-metadata' ? 4 : stepForChatPillId(stageId)
    if (targetStep !== step) setStep(targetStep)
    setWorkspace({ stageId: normalized })
    requestAppSidebarCollapse()
  }, [setStep, step])

  const closeWorkspace = useCallback(() => {
    setWorkspace(null)
  }, [])

  const runChatStatusPage = useCallback(async (page, { title: titleOverride } = {}) => {
    if (!page) return
    const {
      key,
      title,
      subtitle,
      steps,
      work,
      after,
      msPerStep = 850,
    } = page
    const taskKey = `transition-${key || 'status'}-${Date.now()}`
    setWorkspace(null)
    upsertTask(taskKey, {
      taskVariant: 'status-transition',
      title: titleOverride || title || 'Working…',
      lines: subtitle ? [subtitle] : [],
      status: 'running',
      collapsed: false,
      transitionSteps: steps || [],
      transitionActiveIdx: 0,
    })
    const workPromise = work
      ? Promise.resolve().then(() => work()).catch(() => {})
      : Promise.resolve()
    const stepCount = steps?.length || 1
    for (let i = 0; i < stepCount; i += 1) {
      upsertTask(taskKey, { transitionActiveIdx: i })
      await sleep(msPerStep)
    }
    await workPromise
    upsertTask(taskKey, {
      status: 'done',
      collapsed: true,
      transitionActiveIdx: stepCount,
      lines: [...(subtitle ? [subtitle] : []), 'Done.'],
    })
    after?.()
  }, [upsertTask])

  const runChatStatusTransition = useCallback(async (transitionKey, opts = {}) => {
    const cfg = STATUS_TRANSITIONS[transitionKey]
    if (!cfg) {
      opts.onDone?.()
      return
    }
    await runChatStatusPage({ ...cfg, key: transitionKey, msPerStep: cfg.msPerStep || 850 }, opts)
    opts.onDone?.()
  }, [runChatStatusPage])

  const consumingStatusPageRef = useRef(false)
  useEffect(() => {
    if (!statusPage || !isChatModeAllowedForStep(step)) return
    if (consumingStatusPageRef.current) return
    consumingStatusPageRef.current = true
    const page = { ...statusPage }
    setStatusPage(null)
    void runChatStatusPage(page).finally(() => {
      consumingStatusPageRef.current = false
    })
  }, [statusPage, step, setStatusPage, runChatStatusPage])

  const openPreviewTable = useCallback((tableId, { tableIds = null, rationale = '', prompt = '' } = {}) => {
    const focusId = tableId != null ? String(tableId) : null
    setPreviewFocusTableId(focusId)
    if (tableIds?.length) {
      setPreviewAiFilter(createPreviewAiFindFilter({
        tableIds: tableIds.map(String),
        rationale,
        prompt,
      }))
    } else if (focusId) {
      setPreviewAiFilter(createPreviewAiFindFilter({
        tableIds: [focusId],
        rationale,
        prompt,
      }))
    }
    openWorkspace('preview')
  }, [openWorkspace])

  const handleInlineJobComplete = useCallback(({ jobId, filename }) => {
    saveChatActiveJob(null)
    setActiveJobId(null)
    setPdfReviewJob(jobId, filename || null)
    setPreviewAiFilter(null)
    setPreviewFocusTableId(null)
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
          lines: ['Files uploaded and processed.', 'Expand and preview to inspect tables, or Save and proceed.'],
          jobId: null,
        }
        : m
    )))
    ensureStageAnchor('preview', () => ({
      title: 'Preview',
      subtitle: filename || undefined,
      summary: 'Your PDF has been uploaded and is in Preview.',
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
        lines: ['Matched and loaded. Expand and preview to inspect, or Save and proceed.'],
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
    if (proceeding) return
    setProceeding(true)
    setPreviewFocusTableId(null)
    try {
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
          collapsed: false,
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
          text: `Please Expand and preview and save corrections for ${unsavedMismatched.length + unsavedAiFilled.length} table(s) before continuing.`,
        })
        return
      }

      setWorkspace(null)
      await runChatStatusTransition('previewToGrouping', {
        title: 'Preparing grouping',
        onDone: () => applyReconcile({}, { skipStatusPage: true }),
      })
    } finally {
      setProceeding(false)
    }
  }

  const verifyGrouping = () => {
    setWorkspace(null)
    requestContinueToMetadata()
  }

  const verifyMetadataAndOpenClassify = async () => {
    setWorkspace(null)
    setMetaLabel('this release')
    setMetadataIds([])
    setMetadataId(null)
    setPendingGroups(null)
    await runChatStatusPage({
      ...STATUS_TRANSITIONS.metadataToClassify,
      key: 'metadataToClassify',
      msPerStep: 550,
      after: () => {
        setMaxStepReached((m) => Math.max(m, 5))
        setStep(5)
        saveConsoleUiMode(UI_MODES.guided)
        onUiModeChange(UI_MODES.guided)
      },
    })
  }

  const handleVerifyForStage = (stageId) => {
    if (stageId === 'preview') verifyPreview()
    else if (stageId === 'grouping') verifyGrouping()
    else if (stageId === 'grouping-metadata') verifyMetadataAndOpenClassify()
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

  const resolveChatJobId = useCallback(() => (
    pdfReviewJobId || matchResult?.pdf_job_id || activeJobId || null
  ), [pdfReviewJobId, matchResult?.pdf_job_id, activeJobId])

  const applyLlmInputResponse = useCallback(async (data, { jobId } = {}) => {
    const type = String(data?.type || '')
    const rationale = String(data?.rationale || data?.message || '').trim() || 'Done.'
    const ids = (data?.table_ids || []).map(String).filter(Boolean)
    const nameMap = data?.table_names && typeof data.table_names === 'object'
      ? data.table_names
      : {}

    appendMessage({ kind: 'assistant', text: rationale })

    if (type === 'merge_groups') {
      if (data.executed && data.grouping) {
        const next = pdfGroupingToMatchResult(
          data.grouping,
          pdfReviewFilename || matchResult?.groups?.[0]?.matched_tables?.[0]?.table?.source_file || 'pdf',
          jobId || data.job_id || matchResult?.pdf_job_id || null,
        )
        setMatchResult(next)
        openWorkspace('grouping')
      }
      return
    }

    if ((type === 'propose_group' || type === 'bulk_propose_group') && ids.length) {
      const rows = ids.map((id) => ({
        id,
        title: nameMap[id] || id,
        page: null,
        reason: null,
      }))
      appendMessage({
        kind: 'tableResults',
        variant: 'group',
        rationale: data.group_name
          ? `Proposed group “${data.group_name}”. Confirm to apply.`
          : 'Proposed group. Confirm to apply.',
        tableIds: ids,
        rows,
        groupName: data.group_name || '',
        confirmed: false,
      })
      return
    }

    if (!ids.length) return

    let sourceTables = []
    try {
      sourceTables = await fetchPdfJobResultTables(jobId || data.job_id).catch(() => [])
    } catch {
      sourceTables = []
    }
    const rows = rowsFromMatchedTables(sourceTables, ids, { pdfJob: true })
    const displayRows = rows.length
      ? rows
      : ids.map((id) => ({
        id,
        title: nameMap[id] || id,
        page: null,
        reason: null,
      }))

    if (type === 'delete' || type === 'bulk_delete') {
      appendMessage({
        kind: 'tableResults',
        variant: 'delete',
        rationale: 'Confirm to permanently remove these tables from the preview.',
        tableIds: ids,
        rows: displayRows,
        confirmed: false,
      })
      return
    }

    if (
      type === 'find'
      || type === 'bulk_find'
      || type === 'find_review_needed'
      || type === 'find_ai_review_needed'
      || type === 'download'
      || type === 'bulk_download'
    ) {
      appendMessage({
        kind: 'tableResults',
        variant: type.includes('review') ? 'review' : 'find',
        rationale: 'Open a row to inspect it in Preview.',
        tableIds: ids,
        rows: displayRows,
      })
    }
  }, [appendMessage, matchResult, openWorkspace, pdfReviewFilename, setMatchResult])

  const handleUserMessage = async (text) => {
    const conversation = buildPreviewChatConversation(messages)
    appendMessage({ kind: 'user', text })
    if (!hasLlmKey) {
      appendMessage({ kind: 'assistant', text: 'Save an LLM API key in Settings to chat about your tables.' })
      return
    }

    setComposerLoading(true)
    try {
      const jobId = resolveChatJobId()
      // PDF jobs: notebook-style backend llm_input (Preview + Grouping).
      if (jobId && (step === 2 || step === 3 || step === 4)) {
        const stage = step >= 3 ? 'grouping' : 'preview'
        const data = await postLlmInput(jobId, {
          userRequest: text,
          stage,
          prompt: conversation.map((t) => `${t.role}: ${t.content}`).join('\n').slice(-2000) || null,
        })
        await applyLlmInputResponse(data, { jobId })
        return
      }

      const { catalog, tables, resolvedJobId } = await (async () => {
        const resolved = await resolvePreviewCatalog()
        return { ...resolved, resolvedJobId: resolved.jobId }
      })()
      if (!catalog.length) {
        appendMessage({
          kind: 'assistant',
          text: step <= 1
            ? 'Upload files and start extraction first — then I can answer questions about your tables.'
            : 'No table catalog is available at this step yet.',
        })
        return
      }

      const pdfJob = Boolean(resolvedJobId)

      if (isReviewNeededIntent(text)) {
        const reviewRows = filterReviewNeededTables(tables, { pdfJob })
        appendMessage({
          kind: 'assistant',
          text: reviewRows.length
            ? `Found ${reviewRows.length} table${reviewRows.length === 1 ? '' : 's'} that need review.`
            : 'No tables currently need human review.',
        })
        if (reviewRows.length) {
          appendMessage({
            kind: 'tableResults',
            variant: 'review',
            rationale: 'Open a row to inspect it in Preview.',
            tableIds: reviewRows.map((r) => r.id),
            rows: reviewRows,
          })
        }
        return
      }

      let data = resolvedJobId
        ? await runPdfJobTableAiChat(resolvedJobId, text, catalog, { conversation })
        : await runConsoleTableAiChat(text, catalog, { conversation })

      let action = data.action === 'remove' ? 'remove' : data.action === 'find' ? 'find' : 'none'
      let findIds = (data.table_ids || []).map(String).filter(Boolean)
      const userWantsRemove = /\b(remove|delete|drop|discard|exclude|get rid of|take out)\b/i.test(text)
      const parseFailed = /could not interpret that response/i.test(String(data.reply || ''))

      const needsSearchFallback = (
        (action === 'remove' && !findIds.length)
        || (action === 'find' && !findIds.length)
        || (action === 'none' && (isPreviewShowFindIntent(text) || userWantsRemove || parseFailed))
      )
      if (needsSearchFallback) {
        const searchRows = catalogRowsForAiSearch(tables, { pdfJob })
        const searchPrompt = [text, ...conversation.map((t) => t.content)].join('\n\n')
        const searchResult = resolvedJobId
          ? await runPdfJobTableAiSearch(resolvedJobId, searchPrompt, searchRows)
          : await runConsoleTableAiSearch(searchPrompt, searchRows)
        if (searchResult.table_ids?.length) {
          const asRemove = userWantsRemove && (
            searchResult.intent === 'remove' || action === 'remove' || parseFailed
          )
          action = asRemove ? 'remove' : 'find'
          findIds = searchResult.table_ids.map(String)
          data = {
            ...data,
            reply: asRemove
              ? (searchResult.rationale
                || `Found ${findIds.length} table(s) to remove. Confirm in chat to delete them.`)
              : (searchResult.rationale || data.reply || `Found ${findIds.length} matching table(s).`),
          }
        }
      }

      appendMessage({ kind: 'assistant', text: data.reply || 'Done.' })

      const sourceTables = previewTables.length && !pdfJob ? previewTables : tables
      const rows = rowsFromMatchedTables(sourceTables, findIds, { pdfJob })

      if (action === 'remove' && rows.length) {
        appendMessage({
          kind: 'tableResults',
          variant: 'delete',
          rationale: 'Confirm to permanently remove these tables from the preview.',
          tableIds: rows.map((r) => r.id),
          rows,
          confirmed: false,
        })
      } else if (action === 'find' && rows.length) {
        appendMessage({
          kind: 'tableResults',
          variant: 'find',
          rationale: 'Open a row to inspect it in Preview.',
          tableIds: rows.map((r) => r.id),
          rows,
        })
      }
    } catch (e) {
      appendMessage({ kind: 'assistant', text: e.message || 'Could not interpret that request.' })
    } finally {
      setComposerLoading(false)
    }
  }

  const confirmGroupProposal = async (msg) => {
    const jobId = resolveChatJobId()
    const ids = (msg.tableIds || msg.rows?.map((r) => r.id) || []).map(String).filter(Boolean)
    if (!jobId || !ids.length) {
      appendMessage({ kind: 'assistant', text: 'Could not apply group — missing job or tables.' })
      return
    }
    setDeletingMessageId(msg.id)
    try {
      const data = await postLlmInput(jobId, {
        stage: 'grouping',
        applyGroup: {
          group_name: msg.groupName || 'Untitled group',
          table_ids: ids,
        },
      })
      if (!data.executed || !data.grouping) {
        throw new Error(data.message || 'Could not apply group')
      }
      setMatchResult(pdfGroupingToMatchResult(
        data.grouping,
        pdfReviewFilename || 'pdf',
        jobId,
      ))
      setMessages((prev) => prev.map((m) => (m.id === msg.id ? { ...m, confirmed: true } : m)))
      appendMessage({ kind: 'assistant', text: data.rationale || 'Group applied.' })
      openWorkspace('grouping')
    } catch (e) {
      appendMessage({ kind: 'assistant', text: e.message || 'Could not apply group.' })
    } finally {
      setDeletingMessageId(null)
    }
  }

  const confirmTableDelete = async (msg) => {
    const ids = (msg.tableIds || msg.rows?.map((r) => r.id) || []).map(String).filter(Boolean)
    if (!ids.length) {
      appendMessage({ kind: 'assistant', text: 'No tables selected to delete.' })
      return
    }
    setDeletingMessageId(msg.id)
    try {
      const jobId = pdfReviewJobId || resolveChatJobId()
      if (jobId) {
        await deletePdfJobTables(jobId, ids)
        // Refresh right-panel filter if open; PdfReview will refetch on remount / user can reopen.
        setPreviewAiFilter((prev) => {
          if (!isPreviewAiFindActive(prev)) return prev
          const nextIds = prev.tableIds.filter((id) => !ids.includes(String(id)))
          return nextIds.length
            ? createPreviewAiFindFilter({ ...prev, tableIds: nextIds })
            : null
        })
        if (previewFocusTableId && ids.includes(String(previewFocusTableId))) {
          setPreviewFocusTableId(null)
        }
        // Force PdfReview to remount with fresh data if panel is open.
        if (workspace?.stageId === 'preview') {
          setWorkspace({ stageId: 'preview', refreshKey: Date.now() })
        }
      } else if (matchResult) {
        const next = excludeTablesFromMatchResult(matchResult, ids)
        setMatchResult(next)
      } else {
        throw new Error('Nothing to delete — open Preview after extraction first.')
      }
      setMessages((prev) => prev.map((m) => (
        m.id === msg.id ? { ...m, confirmed: true } : m
      )))
      appendMessage({
        kind: 'assistant',
        text: `Deleted ${ids.length} table${ids.length === 1 ? '' : 's'} from this preview.`,
      })
    } catch (e) {
      appendMessage({ kind: 'assistant', text: e.message || 'Could not delete tables.' })
    } finally {
      setDeletingMessageId(null)
    }
  }

  const showUpload = step === 1 && !previewTables.length && !statusPage && !activeJobId && !pdfReviewJobId
  const showChat = !showUpload

  const isPdfRelease = Boolean(pdfReviewJobId || matchResult?.pdf_job_id)
  // Inspect path only: workspace is set explicitly via Expand / find filter.
  const rightPanelStageId = workspace?.stageId || null
  const showRightPanel = showChat
    && Boolean(rightPanelStageId)
    && isChatModeAllowedForStep(step)
    && ['preview', 'grouping'].includes(rightPanelStageId)

  const workspaceTitle = {
    preview: 'Preview',
    grouping: step === 4 ? 'Metadata' : 'Grouping',
  }[rightPanelStageId] || 'Workspace'

  const previewAiFindTableIds = isPreviewAiFindActive(previewAiFilter)
    ? previewAiFilter.tableIds
    : null

  const showComposer = showChat && isChatModeAllowedForStep(step)
  const messagesScrollHeight = showComposer ? CHAT_MESSAGES_SCROLL_HEIGHT : CHAT_SPLIT_HEIGHT
  const previewReady = step === 2 && Boolean(pdfReviewJobId || previewTables.length)
  const showFloatingProceed = previewReady && !proceeding

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
        chatDisabled={!isChatModeAllowedForStep(step)}
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
          className={`relative flex min-h-0 min-w-0 flex-col overflow-hidden ${showRightPanel ? 'flex-none' : 'flex-1'}`}
          style={{
            height: CHAT_SPLIT_HEIGHT,
            maxHeight: CHAT_SPLIT_HEIGHT,
            width: showRightPanel ? CHAT_SPLIT_CHAT_WIDTH : undefined,
          }}
        >
          <ChatScrollRegion height={messagesScrollHeight} className="min-h-0 px-2">
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

            {showChat && (
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
                    const isPreviewStage = sid === 'preview'
                    const downloadExtra = isPreviewStage && pdfJobId ? (
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
                    return (
                      <div
                        key={m.id}
                        ref={(el) => { anchorRefs.current[sid] = el }}
                        data-chat-stage={sid}
                      >
                        <ChatStageArtifact
                          title={m.title}
                          subtitle={m.subtitle || (isPreviewStage ? pdfReviewFilename : undefined)}
                          summary={m.summary}
                          bullets={m.bullets}
                          extra={downloadExtra}
                          expandLabel={isPreviewStage ? 'Expand and preview' : 'Expand'}
                          onExpand={
                            sid !== 'publish' && workspace?.stageId !== expandStageId
                              ? () => openWorkspace(expandStageId)
                              : undefined
                          }
                          onSaveAndProceed={
                            isPreviewStage
                              ? () => handleVerifyForStage('preview')
                              : undefined
                          }
                          saveAndProceedDisabled={proceeding || Boolean(activeJobId)}
                          onVerify={
                            !isPreviewStage && ['grouping', 'grouping-metadata'].includes(sid)
                              ? () => handleVerifyForStage(sid)
                              : undefined
                          }
                          verifyDisabled={
                            (sid === 'grouping' && metadataFilling)
                            || (sid === 'grouping-metadata' && step !== 4)
                          }
                        />
                      </div>
                    )
                  }
                  if (m.kind === 'tableResults') {
                    return (
                      <div key={m.id}>
                        <ChatTableResultBlock
                          variant={m.variant || 'find'}
                          rationale={m.rationale}
                          rows={m.rows || []}
                          confirmed={Boolean(m.confirmed)}
                          confirming={deletingMessageId === m.id}
                          groupName={m.groupName}
                          onOpen={(row) => {
                            openPreviewTable(row.id, {
                              tableIds: m.tableIds || [row.id],
                              rationale: m.rationale || '',
                              prompt: '',
                            })
                          }}
                          onExpand={() => {
                            const ids = (m.tableIds || m.rows?.map((r) => r.id) || []).map(String)
                            if (!ids.length) return
                            if (step >= 3) {
                              openWorkspace('grouping')
                              return
                            }
                            openPreviewTable(ids[0], {
                              tableIds: ids,
                              rationale: m.rationale || '',
                              prompt: '',
                            })
                          }}
                          onConfirmDelete={() => confirmTableDelete(m)}
                          onConfirmGroup={() => confirmGroupProposal(m)}
                        />
                      </div>
                    )
                  }
                  return null
                })}
              </div>
            )}
          </ChatScrollRegion>

          {showFloatingProceed && (
            <ChatFloatingProceed
              onClick={() => handleVerifyForStage('preview')}
              disabled={composerLoading || Boolean(activeJobId)}
              loading={proceeding}
            />
          )}

          {showComposer && (
            <div
              className="flex shrink-0 flex-none items-center px-2 pt-2"
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
            >
              {rightPanelStageId === 'preview' && pdfReviewJobId ? (
                <PdfReview
                  key={workspace?.refreshKey || pdfReviewJobId}
                  ref={pdfReviewRef}
                  embedded
                  compact
                  deferContinueProgress
                  jobId={pdfReviewJobId}
                  filename={pdfReviewFilename}
                  previewAiFilter={previewAiFilter}
                  onPreviewAiFilterChange={setPreviewAiFilter}
                  focusTableId={previewFocusTableId}
                  onDone={() => {
                    setPdfReviewJob(null, null)
                    setPreviewAiFilter(null)
                    setPreviewFocusTableId(null)
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
                      collapsed: false,
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
                  suppressStatusPage
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
                  suppressStatusPage
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
