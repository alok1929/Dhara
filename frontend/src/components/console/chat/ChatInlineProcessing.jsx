'use client'

import { useEffect, useRef, useState } from 'react'
import ProcessingStepper from '../ProcessingStepper'
import ErrorBanner from '../../ui/ErrorBanner'
import { withAuthHeaders } from '../../../lib/auth'

const POLL_MS = 2000

const STAGES = [
  { key: 'classify', label: 'Scanning your document to find pages with tables', range: [2, 10] },
  { key: 'extract', label: 'Extracting tables from the document', range: [10, 45] },
  { key: 'classify_confidence', label: 'Checking how confident we are in each table', range: [45, 55] },
  { key: 'validate', label: 'Double-checking uncertain tables with AI', range: [55, 100] },
]
const STAGE_ORDER = STAGES.map((s) => s.key)

function buildSteps(job, sawValidate) {
  if (!job) return STAGES.map((s) => ({ ...s, status: 'pending' }))
  const currentIdx = STAGE_ORDER.indexOf(job.stage)
  return STAGES.map((s, i) => {
    if (job.status === 'done' || job.status === 'completed_with_errors') {
      if (s.key === 'validate' && !sawValidate) {
        return { ...s, status: 'skipped', message: 'Skipped — all tables auto-accepted' }
      }
      return { ...s, status: 'done' }
    }
    if (i < currentIdx) return { ...s, status: 'done' }
    if (i === currentIdx) {
      const [lo, hi] = s.range
      const localPercent = Math.max(0, Math.min(100, Math.round(((job.percent - lo) / (hi - lo)) * 100)))
      return { ...s, status: 'active', percent: localPercent, message: job.message }
    }
    return { ...s, status: 'pending' }
  })
}

export default function ChatInlineProcessing({ jobId, onComplete, onError, compact = false }) {
  const [job, setJob] = useState(null)
  const [error, setError] = useState('')
  const sawValidateRef = useRef(false)
  const onCompleteRef = useRef(onComplete)
  const onErrorRef = useRef(onError)
  onCompleteRef.current = onComplete
  onErrorRef.current = onError

  useEffect(() => {
    if (!jobId) return undefined
    let cancelled = false
    let finished = false
    const poll = async () => {
      try {
        const res = await fetch(`/api/pdf/jobs/${jobId}`, withAuthHeaders())
        if (!res.ok) throw new Error('Lost track of this processing job')
        const data = await res.json()
        if (cancelled || finished) return
        if (data.stage === 'validate') sawValidateRef.current = true
        setJob(data)
        if (data.status === 'done' || data.status === 'completed_with_errors') {
          finished = true
          onCompleteRef.current?.({ jobId, filename: data.filename })
        } else if (data.status === 'error' || data.status === 'failed') {
          finished = true
          onErrorRef.current?.(data.message || 'Processing failed')
        }
      } catch (e) {
        if (!cancelled && !finished) onErrorRef.current?.(e.message || 'Processing failed')
      }
    }
    poll()
    const timer = setInterval(poll, POLL_MS)
    return () => {
      cancelled = true
      clearInterval(timer)
    }
  }, [jobId])

  if (error) {
    return <ErrorBanner>{error}</ErrorBanner>
  }

  if (compact) {
    return (
      <div className="mt-1">
        <ProcessingStepper steps={buildSteps(job, sawValidateRef.current)} />
      </div>
    )
  }

  return (
    <div className="rounded-2xl border border-line/90 bg-white p-5">
      <div className="font-display text-[18px] font-medium text-ink">
        {job?.filename || 'Processing your documents'}
      </div>
      <div className="mt-1 text-[13px] text-ink-soft">
        Extraction is running — you can stay in chat view while this completes.
      </div>
      <div className="mt-6">
        <ProcessingStepper steps={buildSteps(job, sawValidateRef.current)} />
      </div>
    </div>
  )
}
