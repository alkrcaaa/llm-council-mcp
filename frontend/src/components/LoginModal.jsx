import { useState } from 'react';
import './LoginModal.css';

export default function LoginModal({ onLoginSuccess }) {
  const [username, setUsername] = useState('admin');
  const [password, setPassword] = useState('');
  const [error, setError] = useState(null);
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!username.trim() || !password) {
      setError('Please enter both username and password.');
      return;
    }

    try {
      setIsLoading(true);
      setError(null);
      const { api } = await import('../api');
      const res = await api.login(username.trim(), password);
      onLoginSuccess(res.username);
    } catch (err) {
      setError(err.message || 'Invalid username or password');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="login-modal-backdrop">
      <div className="login-modal-card">
        <div className="login-modal-header">
          <div className="login-brand-icon">🏛️</div>
          <h2>LLM Council</h2>
          <p className="login-subtitle">Multi-model deliberation & architecture synthesis engine</p>
        </div>

        <form className="login-form" onSubmit={handleSubmit}>
          {error && <div className="login-error-alert">{error}</div>}

          <div className="login-input-group">
            <label htmlFor="login-username">Username</label>
            <input
              id="login-username"
              type="text"
              autoComplete="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="e.g. admin"
              disabled={isLoading}
              required
            />
          </div>

          <div className="login-input-group">
            <label htmlFor="login-password">Password</label>
            <input
              id="login-password"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Enter password"
              disabled={isLoading}
              autoFocus
              required
            />
          </div>

          <button
            type="submit"
            className="login-submit-btn"
            disabled={isLoading || !password}
          >
            {isLoading ? 'Authenticating...' : 'Sign In to Council'}
          </button>

          <div className="login-footer-tip">
            <span>Default credentials: <code>admin</code> / <code>admin</code></span>
          </div>
        </form>
      </div>
    </div>
  );
}
