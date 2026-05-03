import { useState, useEffect, useRef, useCallback } from 'react';
import ReactMarkdown from 'react-markdown';
import { useAuth } from '../context/AuthContext';
import {
    getSessions,
    createSession,
    deleteSession,
    getMessages,
    sendMessage,
} from '../api/client';
import '../App.css';

// ── Sidebar ───────────────────────────────────────────────────────────────────
function Sidebar({ sessions, activeId, onSelect, onNew, onDelete, user, onLogout }) {
    return (
        <aside className="sidebar">
            <div className="sidebar-header">
                <div className="sidebar-brand">
                    <span className="brand-icon">🍽️</span>
                    Bella Tavola
                </div>
                <button className="btn-new-chat" onClick={onNew}>
                    ＋ New Conversation
                </button>
            </div>

            <div className="sidebar-sessions">
                {sessions.length === 0 && (
                    <p style={{ color: '#5A3030', fontSize: '0.82rem', padding: '0.8rem 0.5rem' }}>
                        No conversations yet. Start one!
                    </p>
                )}
                {sessions.map((s) => (
                    <div
                        key={s.id}
                        className={`session-item${activeId === s.id ? ' active' : ''}`}
                        onClick={() => onSelect(s.id)}
                    >
                        <span className="session-title">💬 {s.title}</span>
                        <button
                            className="btn-delete-session"
                            title="Delete"
                            onClick={(e) => { e.stopPropagation(); onDelete(s.id); }}
                        >
                            ✕
                        </button>
                    </div>
                ))}
            </div>

            <div className="sidebar-footer">
                <div className="user-info">
                    <div className="user-avatar">
                        {(user?.user_name || user?.user_email || '?')[0].toUpperCase()}
                    </div>
                    <span className="user-name">{user?.user_name || user?.user_email}</span>
                </div>
                <button className="btn-logout" onClick={onLogout}>Logout</button>
            </div>
        </aside>
    );
}

// ── Message bubble ────────────────────────────────────────────────────────────
function MessageBubble({ role, content }) {
    return (
        <div className={`message-row ${role}`}>
            <div className="msg-avatar">
                {role === 'user' ? '👤' : '🍴'}
            </div>
            <div className="msg-bubble msg-markdown">
                <ReactMarkdown>{content}</ReactMarkdown>
            </div>
        </div>
    );
}

// ── Typing indicator ──────────────────────────────────────────────────────────
function TypingIndicator() {
    return (
        <div className="message-row assistant">
            <div className="msg-avatar">🍴</div>
            <div className="msg-bubble">
                <div className="msg-typing">
                    <span /><span /><span />
                </div>
            </div>
        </div>
    );
}

// ── Chat window ───────────────────────────────────────────────────────────────
function ChatWindow({ sessionId, sessionTitle }) {
    const [messages, setMessages] = useState([]);
    const [input, setInput] = useState('');
    const [sending, setSending] = useState(false);
    const bottomRef = useRef(null);
    const textareaRef = useRef(null);

    useEffect(() => {
        if (!sessionId) return;
        getMessages(sessionId).then((r) => setMessages(r.data));
    }, [sessionId]);

    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages, sending]);

    const handleSend = useCallback(async () => {
        const text = input.trim();
        if (!text || sending) return;
        setInput('');
        setMessages((prev) => [...prev, { id: Date.now(), role: 'user', content: text }]);
        setSending(true);
        try {
            const res = await sendMessage(sessionId, text);
            setMessages((prev) => [...prev, res.data]);
        } catch {
            setMessages((prev) => [
                ...prev,
                { id: Date.now() + 1, role: 'assistant', content: 'Sorry, something went wrong. Please try again.' },
            ]);
        } finally {
            setSending(false);
        }
    }, [input, sending, sessionId]);

    const handleKeyDown = (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
    };

    // Auto-resize textarea
    const handleInput = (e) => {
        setInput(e.target.value);
        e.target.style.height = 'auto';
        e.target.style.height = Math.min(e.target.scrollHeight, 140) + 'px';
    };

    return (
        <>
            <div className="chat-topbar">
                <span className="chat-topbar-icon">🍴</span>
                <h2>{sessionTitle || 'Restaurant Assistant'}</h2>
            </div>

            <div className="chat-messages">
                {messages.length === 0 && !sending && (
                    <div className="chat-empty">
                        <span className="empty-icon">🍽️</span>
                        <h3>How can I assist you today?</h3>
                        <p>Ask me about our menu, ingredients, specials, or anything else!</p>
                    </div>
                )}
                {messages.map((m) => (
                    <MessageBubble key={m.id} role={m.role} content={m.content} />
                ))}
                {sending && <TypingIndicator />}
                <div ref={bottomRef} />
            </div>

            <div className="chat-input-bar">
                <textarea
                    ref={textareaRef}
                    className="chat-textarea"
                    placeholder="Ask about our menu, specials, ingredients…"
                    value={input}
                    onChange={handleInput}
                    onKeyDown={handleKeyDown}
                    rows={1}
                    disabled={sending}
                />
                <button
                    className="btn-send"
                    onClick={handleSend}
                    disabled={!input.trim() || sending}
                    title="Send"
                >
                    ➤
                </button>
            </div>
        </>
    );
}

// ── Chat page (root) ──────────────────────────────────────────────────────────
export default function ChatPage() {
    const { user, logout } = useAuth();
    const [sessions, setSessions] = useState([]);
    const [activeId, setActiveId] = useState(null);

    const loadSessions = useCallback(() => {
        getSessions().then((r) => setSessions(r.data));
    }, []);

    useEffect(() => { loadSessions(); }, [loadSessions]);

    const handleNew = async () => {
        const res = await createSession('New Chat');
        setSessions((prev) => [res.data, ...prev]);
        setActiveId(res.data.id);
    };

    const handleDelete = async (id) => {
        await deleteSession(id);
        setSessions((prev) => prev.filter((s) => s.id !== id));
        if (activeId === id) setActiveId(null);
    };

    const activeSession = sessions.find((s) => s.id === activeId);

    return (
        <div className="chat-layout">
            <Sidebar
                sessions={sessions}
                activeId={activeId}
                onSelect={setActiveId}
                onNew={handleNew}
                onDelete={handleDelete}
                user={user}
                onLogout={logout}
            />

            <main className="chat-main">
                {activeId ? (
                    <ChatWindow
                        key={activeId}
                        sessionId={activeId}
                        sessionTitle={activeSession?.title}
                    />
                ) : (
                    <div className="no-session">
                        <span className="big-icon">🍽️</span>
                        <h2>Welcome to Bella Tavola</h2>
                        <p>Select a conversation from the sidebar or start a new one to chat with your personal dining assistant.</p>
                        <button
                            className="btn-primary"
                            style={{ width: 'auto', padding: '0.6rem 1.5rem', marginTop: '0.5rem' }}
                            onClick={handleNew}
                        >
                            Start a Conversation
                        </button>
                    </div>
                )}
            </main>
        </div>
    );
}
