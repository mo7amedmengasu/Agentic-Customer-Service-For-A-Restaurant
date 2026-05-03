import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { login, getMe } from '../api/client';
import { useAuth } from '../context/AuthContext';
import '../App.css';

export default function LoginPage() {
    const { setUser } = useAuth();
    const navigate = useNavigate();
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(false);

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError('');
        setLoading(true);
        try {
            const res = await login(username, password);
            localStorage.setItem('token', res.data.access_token);
            const me = await getMe();
            setUser(me.data);
            navigate('/chat');
        } catch (err) {
            setError(err.response?.data?.detail || 'Login failed. Please try again.');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="auth-page">
            <div className="auth-card">
                <div className="auth-logo">
                    <span className="icon">🍽️</span>
                    <h1>Bella Tavola</h1>
                    <p>Your personal dining assistant</p>
                </div>
                <h2>Welcome Back</h2>
                {error && <div className="auth-error">{error}</div>}
                <form onSubmit={handleSubmit}>
                    <div className="form-group">
                        <label>Email or Username</label>
                        <input
                            type="text"
                            placeholder="Enter your email or username"
                            value={username}
                            onChange={(e) => setUsername(e.target.value)}
                            required
                            autoFocus
                        />
                    </div>
                    <div className="form-group">
                        <label>Password</label>
                        <input
                            type="password"
                            placeholder="Enter your password"
                            value={password}
                            onChange={(e) => setPassword(e.target.value)}
                            required
                        />
                    </div>
                    <button type="submit" className="btn-primary" disabled={loading}>
                        {loading ? 'Signing in…' : 'Sign In'}
                    </button>
                </form>
                <div className="auth-footer">
                    Don&apos;t have an account?{' '}
                    <Link to="/register">Create one</Link>
                </div>
            </div>
        </div>
    );
}
