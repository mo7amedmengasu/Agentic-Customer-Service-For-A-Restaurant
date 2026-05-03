import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { register, login, getMe } from '../api/client';
import { useAuth } from '../context/AuthContext';
import '../App.css';

export default function RegisterPage() {
    const { setUser } = useAuth();
    const navigate = useNavigate();
    const [form, setForm] = useState({
        user_name: '',
        user_email: '',
        user_tel: '',
        user_password: '',
        confirm: '',
    });
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(false);

    const set = (field) => (e) => setForm((f) => ({ ...f, [field]: e.target.value }));

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError('');
        if (form.user_password !== form.confirm) {
            setError('Passwords do not match.');
            return;
        }
        setLoading(true);
        try {
            await register({
                user_name: form.user_name,
                user_email: form.user_email,
                user_tel: form.user_tel,
                user_password: form.user_password,
                user_type: 'customer',
            });
            // Auto-login after register
            const loginRes = await login(form.user_email, form.user_password);
            localStorage.setItem('token', loginRes.data.access_token);
            const me = await getMe();
            setUser(me.data);
            navigate('/chat');
        } catch (err) {
            setError(err.response?.data?.detail || 'Registration failed. Please try again.');
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
                <h2>Create Account</h2>
                {error && <div className="auth-error">{error}</div>}
                <form onSubmit={handleSubmit}>
                    <div className="form-group">
                        <label>Full Name</label>
                        <input
                            type="text"
                            placeholder="Your name"
                            value={form.user_name}
                            onChange={set('user_name')}
                            required
                            autoFocus
                        />
                    </div>
                    <div className="form-group">
                        <label>Email</label>
                        <input
                            type="email"
                            placeholder="you@example.com"
                            value={form.user_email}
                            onChange={set('user_email')}
                            required
                        />
                    </div>
                    <div className="form-group">
                        <label>Phone (optional)</label>
                        <input
                            type="tel"
                            placeholder="+1 555 000 0000"
                            value={form.user_tel}
                            onChange={set('user_tel')}
                        />
                    </div>
                    <div className="form-group">
                        <label>Password</label>
                        <input
                            type="password"
                            placeholder="Min. 8 characters"
                            value={form.user_password}
                            onChange={set('user_password')}
                            required
                            minLength={8}
                        />
                    </div>
                    <div className="form-group">
                        <label>Confirm Password</label>
                        <input
                            type="password"
                            placeholder="Repeat password"
                            value={form.confirm}
                            onChange={set('confirm')}
                            required
                        />
                    </div>
                    <button type="submit" className="btn-primary" disabled={loading}>
                        {loading ? 'Creating account…' : 'Create Account'}
                    </button>
                </form>
                <div className="auth-footer">
                    Already have an account?{' '}
                    <Link to="/login">Sign in</Link>
                </div>
            </div>
        </div>
    );
}
