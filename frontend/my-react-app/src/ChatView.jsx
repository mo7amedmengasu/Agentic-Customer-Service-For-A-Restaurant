import { useEffect, useRef, useState } from 'react'

export default function ChatView({
  sessionId,
  messages,
  onSend,
  isSending,
  isLoadingHistory,
}) {
  const [input, setInput] = useState('')
  const messagesEndRef = useRef(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isSending])

  const send = () => {
    const trimmed = input.trim()
    if (!trimmed || isSending) return
    onSend(trimmed)
    setInput('')
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      send()
    }
  }

  if (!sessionId) {
    return (
      <main className="chat-empty">
        <div>
          <h2>👋 Welcome</h2>
          <p>Start a new chat or pick one from the sidebar.</p>
        </div>
      </main>
    )
  }

  return (
    <main className="chat-main">
      <section className="chat-messages">
        {isLoadingHistory && (
          <div className="loading-line">Loading history…</div>
        )}

        {!isLoadingHistory && messages.length === 0 && (
          <div className="loading-line">
            Send a message to begin the conversation.
          </div>
        )}

        {messages.map((msg, i) => (
          <div key={i} className={`message ${msg.role}`}>
            <div className="avatar">{msg.role === 'user' ? '🙂' : '🤖'}</div>
            <div className="bubble">{msg.content}</div>
          </div>
        ))}

        {isSending && (
          <div className="message assistant">
            <div className="avatar">🤖</div>
            <div className="bubble typing">
              <span></span>
              <span></span>
              <span></span>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </section>

      <footer className="chat-input-area">
        <textarea
          className="chat-input"
          placeholder="Type your message... (Enter to send, Shift+Enter for new line)"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          rows={1}
          disabled={isSending}
        />
        <button
          className="send-btn"
          onClick={send}
          disabled={isSending || !input.trim()}
        >
          Send
        </button>
      </footer>
    </main>
  )
}
