import axios from 'axios';

const BASE_URL = 'http://localhost:8000/api/v1';

const api = axios.create({ baseURL: BASE_URL });

// Attach JWT token to every request
api.interceptors.request.use((config) => {
    const token = localStorage.getItem('token');
    if (token) config.headers.Authorization = `Bearer ${token}`;
    return config;
});

// Auth
export const login = (username, password) => {
    const form = new URLSearchParams();
    form.append('username', username);
    form.append('password', password);
    return api.post('/users/login', form, {
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    });
};

export const register = (data) => api.post('/users/', data);
export const getMe = () => api.get('/users/me');

// Chat sessions
export const getSessions = () => api.get('/chat/sessions');
export const createSession = (title = 'New Chat') => api.post('/chat/sessions', { title });
export const deleteSession = (id) => api.delete(`/chat/sessions/${id}`);

// Messages
export const getMessages = (sessionId) => api.get(`/chat/sessions/${sessionId}/messages`);
export const sendMessage = (sessionId, content) =>
    api.post(`/chat/sessions/${sessionId}/messages`, { content });
