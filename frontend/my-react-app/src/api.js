const API_BASE = 'http://localhost:8000/api/v1'
const TOKEN_KEY = 'rest_chat_token'
const USER_KEY = 'rest_chat_user'
const AUTH_EVENT = 'rest_chat_auth_changed'


export const auth = {
  getToken: () => localStorage.getItem(TOKEN_KEY),
  getUser: () => {
    const raw = localStorage.getItem(USER_KEY)
    return raw ? JSON.parse(raw) : null
  },
  setSession: (token, user) => {
    localStorage.setItem(TOKEN_KEY, token)
    localStorage.setItem(USER_KEY, JSON.stringify(user))
    window.dispatchEvent(new Event(AUTH_EVENT))
  },
  clear: () => {
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(USER_KEY)
    window.dispatchEvent(new Event(AUTH_EVENT))
  },
  onChange: (handler) => {
    window.addEventListener(AUTH_EVENT, handler)
    return () => window.removeEventListener(AUTH_EVENT, handler)
  },
}


async function request(path, { method = 'GET', body, headers = {}, isForm = false } = {}) {
  const token = auth.getToken()
  const finalHeaders = {
    ...(isForm ? {} : { 'Content-Type': 'application/json' }),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...headers,
  }
  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers: finalHeaders,
    body: isForm ? body : body ? JSON.stringify(body) : undefined,
  })
  if (res.status === 401) {
    auth.clear()
    throw new Error('Session expired. Please log in again.')
  }
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`
    try {
      const data = await res.json()
      if (data?.detail) detail = data.detail
    } catch {}
    throw new Error(detail)
  }
  if (res.status === 204) return null
  return res.json()
}


export const api = {
  login: async (email, password) => {
    const form = new URLSearchParams()
    form.set('username', email)
    form.set('password', password)
    const data = await request('/users/login', {
      method: 'POST',
      body: form,
      isForm: true,
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    })
    const me = await request('/users/me', {
      headers: { Authorization: `Bearer ${data.access_token}` },
    })
    auth.setSession(data.access_token, {
      user_id: me.user_id,
      user_name: me.user_name,
      user_email: me.user_email,
    })
    return data
  },

  register: async (payload) => {
    await request('/users/', { method: 'POST', body: payload })
    return api.login(payload.user_email, payload.user_password)
  },

  listSessions: () => request('/chat/sessions'),
  createSession: (title = null) =>
    request('/chat/sessions', { method: 'POST', body: { title } }),
  renameSession: (sessionId, title) =>
    request(`/chat/sessions/${sessionId}`, { method: 'PATCH', body: { title } }),
  deleteSession: (sessionId) =>
    request(`/chat/sessions/${sessionId}`, { method: 'DELETE' }),

  getMessages: (sessionId) => request(`/chat/sessions/${sessionId}/messages`),
  sendMessage: (sessionId, message) =>
    request(`/chat/sessions/${sessionId}/messages`, {
      method: 'POST',
      body: { message },
    }),
}
