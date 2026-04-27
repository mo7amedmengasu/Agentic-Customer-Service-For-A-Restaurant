import { useCallback, useEffect, useState } from 'react'
import './App.css'
import { api, auth } from './api'
import Login from './Login'
import Sidebar from './Sidebar'
import ChatView from './ChatView'

export default function App() {
  const [user, setUser] = useState(() => auth.getUser())
  const [sessions, setSessions] = useState([])
  const [activeId, setActiveId] = useState(null)
  const [messages, setMessages] = useState([])
  const [isSending, setIsSending] = useState(false)
  const [isLoadingHistory, setIsLoadingHistory] = useState(false)
  const [globalError, setGlobalError] = useState('')

  useEffect(() => auth.onChange(() => setUser(auth.getUser())), [])

  const refreshSessions = useCallback(async () => {
    try {
      const list = await api.listSessions()
      setSessions(list)
      return list
    } catch (e) {
      setGlobalError(e.message)
      return []
    }
  }, [])

  useEffect(() => {
    if (!user) return
    refreshSessions()
  }, [user, refreshSessions])

  const selectSession = async (sessionId) => {
    setActiveId(sessionId)
    setMessages([])
    setIsLoadingHistory(true)
    setGlobalError('')
    try {
      const msgs = await api.getMessages(sessionId)
      setMessages(msgs)
    } catch (e) {
      setGlobalError(e.message)
    } finally {
      setIsLoadingHistory(false)
    }
  }

  const newChat = async () => {
    setGlobalError('')
    try {
      const sess = await api.createSession()
      setSessions((prev) => [sess, ...prev.filter((s) => s.session_id !== sess.session_id)])
      setActiveId(sess.session_id)
      setMessages([])
    } catch (e) {
      setGlobalError(e.message)
    }
  }

  const deleteChat = async (sessionId) => {
    setGlobalError('')
    try {
      await api.deleteSession(sessionId)
      setSessions((prev) => prev.filter((s) => s.session_id !== sessionId))
      if (sessionId === activeId) {
        setActiveId(null)
        setMessages([])
      }
    } catch (e) {
      setGlobalError(e.message)
    }
  }

  const renameChat = async (sessionId, title) => {
    setGlobalError('')
    try {
      const updated = await api.renameSession(sessionId, title)
      setSessions((prev) =>
        prev.map((s) => (s.session_id === sessionId ? updated : s))
      )
    } catch (e) {
      setGlobalError(e.message)
    }
  }

  const sendMessage = async (text) => {
    if (!activeId) return
    setIsSending(true)
    setGlobalError('')
    const optimistic = { role: 'user', content: text, _pending: true }
    setMessages((prev) => [...prev, optimistic])
    try {
      const data = await api.sendMessage(activeId, text)
      setMessages((prev) => [
        ...prev.map((m) => (m === optimistic ? { role: 'user', content: text } : m)),
        { role: 'assistant', content: data.response },
      ])
      refreshSessions()
    } catch (e) {
      setMessages((prev) => prev.filter((m) => m !== optimistic))
      setGlobalError(`Send failed: ${e.message}`)
    } finally {
      setIsSending(false)
    }
  }

  const handleLogout = () => {
    auth.clear()
    setSessions([])
    setActiveId(null)
    setMessages([])
  }

  if (!user) {
    return <Login onAuthenticated={() => setUser(auth.getUser())} />
  }

  return (
    <div className="app-shell">
      <Sidebar
        sessions={sessions}
        activeId={activeId}
        onSelect={selectSession}
        onNewChat={newChat}
        onDelete={deleteChat}
        onRename={renameChat}
        user={user}
        onLogout={handleLogout}
      />
      <div className="chat-pane">
        <header className="chat-header">
          <div className="header-content">
            <h1>🍽️ Restaurant Assistant</h1>
            <p className="subtitle">Powered by Agentic AI</p>
          </div>
        </header>
        {globalError && <div className="banner-error">{globalError}</div>}
        <ChatView
          sessionId={activeId}
          messages={messages}
          onSend={sendMessage}
          isSending={isSending}
          isLoadingHistory={isLoadingHistory}
        />
      </div>
    </div>
  )
}
