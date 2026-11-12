import React, { useState } from 'react';
import { useNavigate, useLocation, Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export const LoginPage = () => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!username.trim() || !password) {
      setError('Please provide both username and password.');
      return;
    }

    setError('');
    setLoading(true);

    try {
      const user = await login(username, password);
      // Navigate to role-appropriate dashboard or original target
      if (location.state?.from) {
        navigate(location.state.from.pathname);
      } else if (user.role === 'customer') {
        navigate('/customer');
      } else if (user.role === 'employee') {
        navigate('/employee');
      } else if (user.role === 'admin') {
        navigate('/admin');
      } else {
        navigate('/');
      }
    } catch (err) {
      setError(err.message || 'Login failed. Please check credentials.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-card">
      <div className="card-header">
        <h2>Secure Login</h2>
        <p className="subtitle">Sign in to your PES Bank account</p>
      </div>

      {error && <div className="alert alert-danger">{error}</div>}

      <form onSubmit={handleSubmit} className="form">
        <div className="form-group">
          <label htmlFor="username">Username or Email</label>
          <input
            id="username"
            type="text"
            className="input-control"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            placeholder="e.g. rahul_k or admin@pesbank.com"
            disabled={loading}
            required
          />
        </div>

        <div className="form-group">
          <label htmlFor="password">Password</label>
          <input
            id="password"
            type="password"
            className="input-control"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="••••••••"
            disabled={loading}
            required
          />
        </div>

        <button type="submit" className="btn btn-primary btn-block" disabled={loading}>
          {loading ? 'Authenticating...' : 'Sign In'}
        </button>
      </form>

      <div className="card-footer">
        <p>New customer? <Link to="/register">Create an account</Link></p>
        <div className="seed-hints">
          <p><strong>Demo Test Accounts:</strong></p>
          <code>Customer: rahul_k / Bank@1234</code><br/>
          <code>Employee: teller_priya / TellerPass@123</code><br/>
          <code>Admin: admin_boss / AdminPassword@123</code>
        </div>
      </div>
    </div>
  );
};
