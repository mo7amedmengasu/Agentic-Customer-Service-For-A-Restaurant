import { useState, useRef, useEffect } from 'react'
import './App.css'

const API_URL = 'http://localhost:8000/api/v1/chat/'

function App() {
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      content: "Hi! I'm your restaurant assistant. I can help you browse the menu, place an order, or answer questions. What can I do for you today?",
    },
  ])
  const [input, setInput] = useState('')
  const [sessionId, setSessionId] = useState(null)
  const [isLoading, setIsLoading] = useState(false)
  const messagesEndRef = useRef(null)

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isLoading])

  const sendMessage = async () => {
    const trimmed = input.trim()
    if (!trimmed || isLoading) return

    // Add user message to UI
    const userMessage = { role: 'user', content: trimmed }
    setMessages((prev) => [...prev, userMessage])
    setInput('')
    setIsLoading(true)

    try {
      const response = await fetch(API_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: trimmed,
          session_id: sessionId,
        }),
      })

      if (!response.ok) {
        throw new Error(`Server returned ${response.status}`)
      }

      const data = await response.json()

      // Save session ID from first response
      if (!sessionId) setSessionId(data.session_id)

      // Add assistant response
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: data.response },
      ])
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: `Sorry, something went wrong: ${err.message}. Make sure the backend is running.`,
          error: true,
        },
      ])
    } finally {
      setIsLoading(false)
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  const resetChat = () => {
    setMessages([
      {
        role: 'assistant',
        content: "Hi! I'm your restaurant assistant. I can help you browse the menu, place an order, or answer questions. What can I do for you today?",
      },
    ])
    setSessionId(null)
  }

  return (
    <div className="chat-app">
      <header className="chat-header">
        <div className="header-content">
          <h1>🍽️ Restaurant Assistant</h1>
          <p className="subtitle">Powered by Agentic AI</p>
        </div>
        <button className="reset-btn" onClick={resetChat} title="Start new conversation">
          New Chat
        </button>
      </header>

      <main className="chat-messages">
        {messages.map((msg, i) => (
          <div
            key={i}
            className={`message ${msg.role} ${msg.error ? 'error' : ''}`}
          >
            <div className="avatar">{msg.role === 'user' ? '🙂' : '🤖'}</div>
            <div className="bubble">{msg.content}</div>
          </div>
        ))}

        {isLoading && (
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
      </main>

      <footer className="chat-input-area">
        <textarea
          className="chat-input"
          placeholder="Type your message... (Enter to send, Shift+Enter for new line)"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          rows={1}
          disabled={isLoading}
        />
        <button
          className="send-btn"
          onClick={sendMessage}
          disabled={isLoading || !input.trim()}
        >
          Send
        </button>
      </footer>

      {sessionId && (
        <div className="session-info">
          Session: <code>{sessionId.slice(0, 8)}...</code>
        </div>
      )}
    </div>
  )
}

export default App
