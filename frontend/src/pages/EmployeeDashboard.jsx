import React, { useState, useEffect } from 'react';
import { apiRequest } from '../services/api';
import { useAuth } from '../context/AuthContext';

export const EmployeeDashboard = () => {
  const { user } = useAuth();
  const [accounts, setAccounts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [search, setSearch] = useState('');

  // Account creation form modal state
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [targetUserId, setTargetUserId] = useState('');
  const [accType, setAccType] = useState('savings');
  const [initialDeposit, setInitialDeposit] = useState('0.00');
  const [actionLoading, setActionLoading] = useState(false);

  const fetchAccounts = async (query = '') => {
    setLoading(true);
    setError('');
    try {
      const url = query ? `/api/accounts?search=${encodeURIComponent(query)}` : '/api/accounts';
      const data = await apiRequest(url);
      setAccounts(data.accounts || []);
    } catch (err) {
      setError(err.message || 'Failed to fetch account list.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAccounts();
  }, []);

  const handleSearch = (e) => {
    e.preventDefault();
    fetchAccounts(search);
  };

  const handleStatusChange = async (accountId, newStatus) => {
    if (!window.confirm(`Are you sure you want to change status of account #${accountId} to "${newStatus}"?`)) {
      return;
    }
    setError('');
    try {
      await apiRequest(`/api/accounts/${accountId}/status`, {
        method: 'PATCH',
        body: JSON.stringify({ status: newStatus }),
      });
      await fetchAccounts(search);
    } catch (err) {
      alert(`Status update failed: ${err.message}`);
    }
  };

  const handleCreateAccount = async (e) => {
    e.preventDefault();
    if (!targetUserId) {
      alert('User ID is required.');
      return;
    }
    setActionLoading(true);
    setError('');
    try {
      await apiRequest('/api/accounts', {
        method: 'POST',
        body: JSON.stringify({
          user_id: parseInt(targetUserId, 10),
          account_type: accType,
          initial_deposit: initialDeposit,
        }),
      });
      setShowCreateModal(false);
      setTargetUserId('');
      setInitialDeposit('0.00');
      await fetchAccounts(search);
    } catch (err) {
      alert(`Failed to create account: ${err.message}`);
    } finally {
      setActionLoading(false);
    }
  };

  return (
    <div className="dashboard-layout">
      <header className="page-header">
        <div>
          <h1>Employee & Management Portal</h1>
          <p className="subtitle">Account and Balance Administration &bull; Role: {user?.role.toUpperCase()}</p>
        </div>
        <button className="btn btn-primary" onClick={() => setShowCreateModal(true)}>
          + Create Customer Account
        </button>
      </header>

      {error && <div className="alert alert-danger">{error}</div>}

      <div className="search-bar-container">
        <form onSubmit={handleSearch} className="search-form">
          <input
            type="text"
            className="input-control"
            placeholder="Search accounts by account number, owner username, name, or email..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <button type="submit" className="btn btn-primary">Search</button>
          {search && (
            <button
              type="button"
              className="btn btn-outline"
              onClick={() => {
                setSearch('');
                fetchAccounts('');
              }}
            >
              Clear
            </button>
          )}
        </form>
      </div>

      {loading ? (
        <div className="center-container">
          <div className="spinner"></div>
          <p>Loading accounts...</p>
        </div>
      ) : accounts.length === 0 ? (
        <div className="empty-state">
          <h3>No Accounts Match Criteria</h3>
          <p>No account records found in system matching your filter.</p>
        </div>
      ) : (
        <div className="table-responsive">
          <table className="data-table">
            <thead>
              <tr>
                <th>Account #</th>
                <th>Owner (ID)</th>
                <th>Type</th>
                <th>Balance (₹)</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {accounts.map((acc) => (
                <tr key={acc.id}>
                  <td><strong>{acc.account_number}</strong></td>
                  <td>
                    <div>{acc.owner_name}</div>
                    <small className="text-muted">@{acc.owner_username} (ID: {acc.user_id})</small>
                  </td>
                  <td><span className="badge-type">{acc.account_type.toUpperCase()}</span></td>
                  <td><strong>₹{parseFloat(acc.balance).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</strong></td>
                  <td><span className={`status-badge badge-${acc.status}`}>{acc.status}</span></td>
                  <td>
                    <div className="action-buttons">
                      {acc.status === 'active' && (
                        <button
                          className="btn btn-warning btn-xs"
                          onClick={() => handleStatusChange(acc.id, 'frozen')}
                        >
                          Freeze
                        </button>
                      )}
                      {acc.status === 'frozen' && (
                        <button
                          className="btn btn-success btn-xs"
                          onClick={() => handleStatusChange(acc.id, 'active')}
                        >
                          Activate
                        </button>
                      )}
                      {acc.status !== 'closed' && (
                        <button
                          className="btn btn-danger btn-xs"
                          title="Requires zero balance"
                          onClick={() => handleStatusChange(acc.id, 'closed')}
                        >
                          Close
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {showCreateModal && (
        <div className="modal-overlay">
          <div className="modal-content">
            <h3>Open Account for Customer</h3>
            <form onSubmit={handleCreateAccount}>
              <div className="form-group">
                <label>Customer User ID</label>
                <input
                  type="number"
                  className="input-control"
                  placeholder="e.g. 3"
                  value={targetUserId}
                  onChange={(e) => setTargetUserId(e.target.value)}
                  required
                />
              </div>
              <div className="form-group">
                <label>Account Type</label>
                <select
                  className="input-control"
                  value={accType}
                  onChange={(e) => setAccType(e.target.value)}
                >
                  <option value="savings">Savings Account</option>
                  <option value="current">Current Account</option>
                </select>
              </div>
              <div className="form-group">
                <label>Initial Opening Balance (₹)</label>
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
                  onClick={() => setShowCreateModal(false)}
                  disabled={actionLoading}
                >
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary" disabled={actionLoading}>
                  {actionLoading ? 'Creating...' : 'Create Account'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
