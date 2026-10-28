'use client'

import { useState } from 'react'
import { commandsForStep } from '../../lib/chatCommands'
import { postStageCommand } from '../../lib/stageCommandClient'

export default function StageCommandBar({
  step,
  lines,
  hasLlmKey,
}) {
  const commands = commandsForStep(step)
  const [loading, setLoading] = useState(false)
  const [reply, setReply] = useState('')
  const [error, setError] = useState('')

  const ask = async (command) => {
    if (!hasLlmKey || loading) return
    setLoading(true)
    setError('')
    setReply('')
    try {
      const data = await postStageCommand(command, lines)
      setReply(data.reply || 'Done.')
    } catch (err) {
      setError(err.message || 'Could not run that command.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="rounded-2xl border border-line bg-white px-3 py-3">
      <p className="m-0 mb-2 text-[12px] font-medium uppercase tracking-wide text-ink-soft">
        Commands
      </p>
      <div className="flex flex-wrap gap-1.5" role="group" aria-label="Commands">
        {commands.map((command) => (
          <button
            key={command}
            type="button"
            disabled={!hasLlmKey || loading}
            className="rounded-full border border-line bg-sage px-2.5 py-1 text-left text-[12px] font-medium text-ink transition-colors hover:border-teal hover:text-teal disabled:opacity-60"
            onClick={() => ask(command)}
          >
            {command}
          </button>
        ))}
      </div>
      {!hasLlmKey && (
        <p className="m-0 mt-2 text-[13px] text-ink-soft">Choose an on-prem model in Settings to run a command.</p>
      )}
      {loading && <p className="m-0 mt-2 text-[13px] text-ink-soft">Running command…</p>}
      {reply && <p className="m-0 mt-2 text-[14px] text-ink">{reply}</p>}
      {error && <p className="m-0 mt-2 text-[14px] text-red-700">{error}</p>}
    </div>
  )
}
