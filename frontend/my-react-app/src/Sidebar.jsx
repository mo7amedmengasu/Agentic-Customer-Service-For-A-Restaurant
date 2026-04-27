function relTime(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  const diff = (Date.now() - d.getTime()) / 1000
  if (diff < 60) return 'just now'
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
  return d.toLocaleDateString()
}

export default function Sidebar({
  sessions,
  activeId,
  onSelect,
  onNewChat,
  onDelete,
  onRename,
  user,
  onLogout,
}) {
  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <button className="new-chat-btn" onClick={onNewChat}>
          + New Chat
        </button>
      </div>

      <ul className="session-list">
        {sessions.length === 0 && (
          <li className="empty">No conversations yet.</li>
        )}
        {sessions.map((s) => (
          <li
            key={s.session_id}
            className={`session-item ${s.session_id === activeId ? 'active' : ''}`}
            onClick={() => onSelect(s.session_id)}
            title={s.title || 'Untitled chat'}
          >
            <div className="session-title">
              {s.title || 'Untitled chat'}
            </div>
            <div className="session-meta">{relTime(s.updated_at)}</div>
            <div className="session-actions" onClick={(e) => e.stopPropagation()}>
              <button
                className="icon-btn"
                title="Rename"
                onClick={() => {
                  const next = window.prompt('Rename chat:', s.title || '')
                  if (next !== null && next.trim() !== (s.title || '').trim()) {
                    onRename(s.session_id, next.trim() || null)
                  }
                }}
              >
                ✎
              </button>
              <button
                className="icon-btn danger"
                title="Delete"
                onClick={() => {
                  if (window.confirm('Delete this chat?')) {
                    onDelete(s.session_id)
                  }
                }}
              >
                ×
              </button>
            </div>
          </li>
        ))}
      </ul>

      <div className="sidebar-footer">
        <div className="user-line" title={user?.user_email}>
          {user?.user_name || user?.user_email || 'Guest'}
        </div>
        <button className="logout-btn" onClick={onLogout}>
          Log out
        </button>
      </div>
    </aside>
  )
}
