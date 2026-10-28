'use client'

import { useState } from 'react'
import { Send } from 'lucide-react'
import Button from '../../ui/Button'

export default function ChatComposer({
  onSend,
  disabled,
  loading,
  commands = [],
  placeholder = 'Or type a command...',
}) {
  const [text, setText] = useState('')

  const submit = () => {
    const trimmed = text.trim()
    if (!trimmed || disabled || loading) return
    onSend?.(trimmed)
    setText('')
  }

  return (
    <div className="flex w-full flex-col gap-2 rounded-[28px] border border-line/90 bg-white px-3 py-2 shadow-[0_8px_32px_rgba(18,64,62,0.12)]">
      {commands.length > 0 && (
        <div className="flex flex-wrap gap-1.5 px-1 pt-1" role="group" aria-label="Commands">
          {commands.map((command) => (
            <button
              key={command}
              type="button"
              disabled={disabled || loading}
              className="rounded-full border border-line bg-sage px-2.5 py-1 text-left text-[12px] font-medium text-ink transition-colors hover:border-teal hover:text-teal disabled:opacity-60"
              onClick={() => onSend?.(command)}
            >
              {command}
            </button>
          ))}
        </div>
      )}
      <div className="flex w-full items-end gap-2">
      <textarea
        rows={1}
        value={text}
        disabled={disabled || loading}
        placeholder={placeholder}
        className="max-h-28 min-h-[40px] flex-1 resize-none rounded-2xl border-0 bg-transparent px-2 py-2 text-[14px] text-ink outline-none placeholder:text-ink-soft/80 disabled:opacity-60"
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault()
            submit()
          }
        }}
      />
      <Button
        type="button"
        size="sm"
        className="mb-0.5 h-10 w-10 flex-none rounded-full p-0"
        disabled={disabled || loading || !text.trim()}
        loading={loading}
        onClick={submit}
        aria-label="Send message"
      >
        <Send className="h-4 w-4" strokeWidth={2} aria-hidden />
      </Button>
      </div>
    </div>
  )
}
