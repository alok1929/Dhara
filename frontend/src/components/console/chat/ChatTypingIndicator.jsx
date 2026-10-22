'use client'

/** Assistant bubble with three-dot typing animation while a chat reply is loading. */
export default function ChatTypingIndicator() {
  return (
    <div className="flex justify-start" aria-live="polite" aria-busy="true">
      <div
        className="flex items-center gap-1.5 rounded-2xl rounded-bl-md border border-line/80 bg-white px-4 py-3.5"
        role="status"
        aria-label="Dhara is typing"
      >
        {[0, 1, 2].map((i) => (
          <span
            key={i}
            className="chat-typing-dot h-2 w-2 rounded-full bg-ink-soft/75"
            style={{ animationDelay: `${i * 0.18}s` }}
          />
        ))}
      </div>
    </div>
  )
}
