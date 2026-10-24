import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { apiRequest } from '../services/api';
import { useAuth } from '../context/AuthContext';

export const CustomerDashboard = () => {
  const { user } = useAuth();
  const [accounts, setAccounts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [showOpenModal, setShowOpenModal] = useState(false);
  const [initialDeposit, setInitialDeposit] = useState('1000.00');
  const [modalLoading, setModalLoading] = useState(false);

  const fetchAccounts = async () => {
    setLoading(true);
    setError('');
    try {
      const data = await apiRequest('/api/accounts');
      setAccounts(data.accounts || []);
    } catch (err) {
      setError(err.message || 'Failed to load accounts.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAccounts();
  }, []);

  const handleOpenAccount = async (e) => {
    e.preventDefault();
    setModalLoading(true);
    setError('');
    try {
      await apiRequest('/api/accounts', {
        method: 'POST',
        body: JSON.stringify({
          account_type: 'savings',
          initial_deposit: initialDeposit,
        }),
      });
      setShowOpenModal(false);
      await fetchAccounts();
    } catch (err) {
      setError(err.message || 'Failed to open account.');
    } finally {
      setModalLoading(false);
    }
  };

  return (
    <div className="dashboard-layout">
      <header className="page-header">
        <div>
          <h1>Welcome, {user?.full_name}</h1>
          <p className="subtitle">Customer Portal &bull; Account Overview</p>
        </div>
        <button className="btn btn-primary" onClick={() => setShowOpenModal(true)}>
          + Open Savings Account
        </button>
      </header>

      {error && <div className="alert alert-danger">{error}</div>}

      {loading ? (
        <div className="center-container">
          <div className="spinner"></div>
          <p>Loading your accounts...</p>
        </div>
      ) : accounts.length === 0 ? (
        <div className="empty-state">
          <h3>No Accounts Found</h3>
          <p>You do not currently have any active accounts. Open a savings account to get started.</p>
          <button className="btn btn-primary" onClick={() => setShowOpenModal(true)}>
            Open an Account
          </button>
        </div>
      ) : (
        <div className="accounts-grid">
          {accounts.map((acc) => (
            <div key={acc.id} className={`account-card status-${acc.status}`}>
              <div className="account-card-header">
                <span className="account-type-tag">{acc.account_type.toUpperCase()} ACCOUNT</span>
                <span className={`status-badge badge-${acc.status}`}>{acc.status}</span>
              </div>
              <div className="account-number">
                <span className="label">Account Number</span>
                <p className="value">{acc.account_number}</p>
              </div>
              <div className="account-balance">
                <span className="label">Current Balance</span>
                <h2 className="balance-amount">₹{parseFloat(acc.balance).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</h2>
              </div>
              <div className="account-card-actions">
                <Link to={`/accounts/${acc.id}`} className="btn btn-outline btn-block">
                  View Account Details
                </Link>
              </div>
            </div>
          ))}
        </div>
      )}

      {showOpenModal && (
        <div className="modal-overlay">
          <div className="modal-content">
            <h3>Open New Savings Account</h3>
            <p>Customers can open an online savings account with an optional initial deposit.</p>
            <form onSubmit={handleOpenAccount}>
              <div className="form-group">
                <label>Account Type</label>
                <input type="text" className="input-control" value="Savings Account" disabled />
              </div>
              <div className="form-group">
                <label>Initial Deposit (₹)</label>
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  className="input-control"
                  value={initialDeposit}
                  onChange={(e) => setInitialDeposit(e.target.value)}
                  required
                />
              </div>
              <div className="modal-actions">
                <button
                  type="button"
                  className="btn btn-outline"
                  onClick={() => setShowOpenModal(false)}
                  disabled={modalLoading}
                >
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary" disabled={modalLoading}>
                  {modalLoading ? 'Processing...' : 'Confirm & Open'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
