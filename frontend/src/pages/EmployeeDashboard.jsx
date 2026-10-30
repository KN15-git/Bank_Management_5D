import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { apiRequest } from '../services/api';
import { useAuth } from '../context/AuthContext';

export const EmployeeDashboard = () => {
  const { user } = useAuth();
  const [accounts, setAccounts] = useState([]);
  const [loans, setLoans] = useState([]);
  const [loanStatusFilter, setLoanStatusFilter] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [successMsg, setSuccessMsg] = useState('');
  const [search, setSearch] = useState('');

  // Account creation form modal state
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [targetUserId, setTargetUserId] = useState('');
  const [accType, setAccType] = useState('savings');
  const [initialDeposit, setInitialDeposit] = useState('0.00');
  const [actionLoading, setActionLoading] = useState(false);

  // Loan rejection modal state (Issues #11 & #12)
  const [rejectingLoan, setRejectingLoan] = useState(null);
  const [rejectionReason, setRejectionReason] = useState('');
  const [loanActionLoading, setLoanActionLoading] = useState(false);

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

  const fetchLoans = async (statusFilter = loanStatusFilter) => {
    try {
      const url = statusFilter
        ? `/api/loans?status=${encodeURIComponent(statusFilter)}`
        : '/api/loans';
      const data = await apiRequest(url);
      setLoans(data.loans || []);
    } catch (err) {
      setError(err.message || 'Failed to fetch loan applications.');
    }
  };

  useEffect(() => {
    fetchAccounts();
    fetchLoans('');
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

  const handleApproveLoan = async (loan) => {
    setError('');
    setSuccessMsg('');
    setLoanActionLoading(true);
    try {
      const res = await apiRequest(`/api/loans/${loan.id}/decision`, {
        method: 'PATCH',
        body: JSON.stringify({
          decision: 'approved',
          decision_notes: 'Approved after officer verification',
        }),
      });
      setSuccessMsg(`Loan ${res.loan.reference_id} approved successfully.`);
      await fetchLoans(loanStatusFilter);
    } catch (err) {
      setError(err.message || 'Failed to approve loan.');
    } finally {
      setLoanActionLoading(false);
    }
  };

  const handleRejectLoanSubmit = async (e) => {
    e.preventDefault();
    if (!rejectingLoan) return;
    if (!rejectionReason.trim()) {
      setError('A rejection reason is required when rejecting a loan application.');
      return;
    }
    setError('');
    setSuccessMsg('');
    setLoanActionLoading(true);
    try {
      const res = await apiRequest(`/api/loans/${rejectingLoan.id}/decision`, {
        method: 'PATCH',
        body: JSON.stringify({
          decision: 'rejected',
          rejection_reason: rejectionReason.trim(),
        }),
      });
      setSuccessMsg(`Loan ${res.loan.reference_id} rejected.`);
      setRejectingLoan(null);
      setRejectionReason('');
      await fetchLoans(loanStatusFilter);
    } catch (err) {
      setError(err.message || 'Failed to reject loan.');
    } finally {
      setLoanActionLoading(false);
    }
  };

  const handleLoanFilterChange = (newStatus) => {
    setLoanStatusFilter(newStatus);
    fetchLoans(newStatus);
  };

  return (
    <div className="dashboard-layout">
      <header className="page-header">
        <div>
          <h1>Employee &amp; Management Portal</h1>
          <p className="subtitle">Account, Balance &amp; Loan Administration &bull; Role: {user?.role.toUpperCase()}</p>
        </div>
        <button className="btn btn-primary" onClick={() => setShowCreateModal(true)}>
          + Create Customer Account
        </button>
      </header>

      {error && <div className="alert alert-danger">{error}</div>}
      {successMsg && <div className="alert alert-success">{successMsg}</div>}

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
                      <Link to={`/accounts/${acc.id}`} className="btn btn-outline btn-xs">
                        View
                      </Link>
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

      {/* Loan Applications Review Queue Section (Issues #11 & #12) */}
      <section style={{ marginTop: '2.5rem' }}>
        <div className="page-header" style={{ marginBottom: '1rem' }}>
          <div>
            <h2>Loan Applications Review Queue</h2>
            <p className="subtitle">Review customer loan applications and process approvals or rejections</p>
          </div>
          <div className="action-buttons">
            <select
              className="input-control"
              style={{ width: 'auto', minWidth: '160px' }}
              value={loanStatusFilter}
              onChange={(e) => handleLoanFilterChange(e.target.value)}
            >
              <option value="">All Statuses</option>
              <option value="pending">Pending Review</option>
              <option value="approved">Approved</option>
              <option value="rejected">Rejected</option>
            </select>
          </div>
        </div>

        {loans.length === 0 ? (
          <div className="empty-state">
            <p>No loan applications found matching the selected status filter.</p>
          </div>
        ) : (
          <div className="table-responsive">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Reference ID</th>
                  <th>Applicant</th>
                  <th>Type</th>
                  <th>Amount (₹)</th>
                  <th>Term &amp; Rate</th>
                  <th>Purpose</th>
                  <th>Status</th>
                  <th>Review Notes / Reason</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {loans.map((loan) => (
                  <tr key={loan.id}>
                    <td><strong>{loan.reference_id}</strong></td>
                    <td>
                      <div>{loan.applicant_name}</div>
                      <small className="text-muted">@{loan.applicant_username} (ID: {loan.user_id})</small>
                    </td>
                    <td><span className="badge-type">{loan.loan_type.toUpperCase()}</span></td>
                    <td>
                      <strong>
                        ₹{parseFloat(loan.amount).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                      </strong>
                    </td>
                    <td>{loan.term_months} mos @ {loan.interest_rate}%</td>
                    <td>{loan.purpose}</td>
                    <td>
                      <span className={`status-badge badge-${loan.status === 'approved' ? 'active' : loan.status === 'rejected' ? 'closed' : 'frozen'}`}>
                        {loan.status.toUpperCase()}
                      </span>
                    </td>
                    <td>
                      {loan.status === 'rejected' && loan.rejection_reason ? (
                        <span className="text-danger"><strong>Reason:</strong> {loan.rejection_reason}</span>
                      ) : loan.decision_notes ? (
                        <span>{loan.decision_notes}</span>
                      ) : (
                        <span className="text-muted">Pending review</span>
                      )}
                    </td>
                    <td>
                      {loan.status === 'pending' ? (
                        <div className="action-buttons">
                          <button
                            className="btn btn-success btn-xs"
                            disabled={loanActionLoading}
                            onClick={() => handleApproveLoan(loan)}
                          >
                            Approve
                          </button>
                          <button
                            className="btn btn-danger btn-xs"
                            disabled={loanActionLoading}
                            onClick={() => {
                              setRejectingLoan(loan);
                              setRejectionReason('');
                            }}
                          >
                            Reject
                          </button>
                        </div>
                      ) : (
                        <small className="text-muted">
                          By @{loan.reviewer_username || 'officer'}
                        </small>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

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

      {rejectingLoan && (
        <div className="modal-overlay">
          <div className="modal-content">
            <h3>Reject Loan Application ({rejectingLoan.reference_id})</h3>
            <p className="subtitle">
              Applicant: {rejectingLoan.applicant_name} &bull; Amount: ₹{rejectingLoan.amount}
            </p>
            <form onSubmit={handleRejectLoanSubmit}>
              <div className="form-group">
                <label>Rejection Reason (Required)</label>
                <input
                  type="text"
                  className="input-control"
                  placeholder="e.g. Insufficient credit history or income verification"
                  value={rejectionReason}
                  onChange={(e) => setRejectionReason(e.target.value)}
                  disabled={loanActionLoading}
                  required
                />
              </div>
              <div className="modal-actions">
                <button
                  type="button"
                  className="btn btn-outline"
                  onClick={() => setRejectingLoan(null)}
                  disabled={loanActionLoading}
                >
                  Cancel
                </button>
                <button type="submit" className="btn btn-danger" disabled={loanActionLoading}>
                  {loanActionLoading ? 'Rejecting...' : 'Confirm Rejection'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
