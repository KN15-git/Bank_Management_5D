import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { apiRequest } from '../services/api';
import { useAuth } from '../context/AuthContext';

export const AccountDetailPage = () => {
  const { id } = useParams();
  const { user } = useAuth();
  const [account, setAccount] = useState(null);
  const [transactions, setTransactions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // Transaction form states
  const [txType, setTxType] = useState('deposit');
  const [txAmount, setTxAmount] = useState('');
  const [txDesc, setTxDesc] = useState('');
  const [txLoading, setTxLoading] = useState(false);
  const [txSuccess, setTxSuccess] = useState('');
  const [txError, setTxError] = useState('');

  const fetchDetailAndTxns = async () => {
    setLoading(true);
    setError('');
    try {
      const [accData, txnData] = await Promise.all([
        apiRequest(`/api/accounts/${id}`),
        apiRequest(`/api/accounts/${id}/transactions`),
      ]);
      setAccount(accData.account);
      setTransactions(txnData.transactions || []);
    } catch (err) {
      setError(err.message || 'Failed to load account details.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDetailAndTxns();
  }, [id]);

  const handleTransactionSubmit = async (e) => {
    e.preventDefault();
    setTxError('');
    setTxSuccess('');

    const parsedAmount = parseFloat(txAmount);
    if (isNaN(parsedAmount) || parsedAmount <= 0) {
      setTxError('Please enter a valid amount greater than zero.');
      return;
    }

    setTxLoading(true);
    const endpoint = txType === 'deposit' ? `/api/accounts/${id}/deposit` : `/api/accounts/${id}/withdraw`;

    try {
      const data = await apiRequest(endpoint, {
        method: 'POST',
        body: JSON.stringify({
          amount: txAmount,
          description: txDesc,
        }),
      });

      setTxSuccess(
        `${txType === 'deposit' ? 'Deposit' : 'Withdrawal'} of ₹${data.transaction.amount} successful! Ref: ${data.transaction.reference_id}`
      );
      setTxAmount('');
      setTxDesc('');

      // Refresh account details and transaction history
      const [accData, txnData] = await Promise.all([
        apiRequest(`/api/accounts/${id}`),
        apiRequest(`/api/accounts/${id}/transactions`),
      ]);
      setAccount(accData.account);
      setTransactions(txnData.transactions || []);
    } catch (err) {
      setTxError(err.message || `${txType === 'deposit' ? 'Deposit' : 'Withdrawal'} failed.`);
    } finally {
      setTxLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="center-container">
        <div className="spinner"></div>
        <p>Loading account details and transactions...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="center-container">
        <div className="alert alert-danger">{error}</div>
        <Link to="/" className="btn btn-outline">Back to Dashboard</Link>
      </div>
    );
  }

  const isFrozen = account.status === 'frozen';
  const isClosed = account.status === 'closed';

  return (
    <div className="detail-layout">
      <div className="detail-card">
        <div className="card-header">
          <div>
            <span className={`status-badge badge-${account.status}`}>{account.status}</span>
            <h2>{account.account_type.toUpperCase()} ACCOUNT</h2>
            <p className="subtitle">Account #{account.account_number}</p>
          </div>
          <Link to={user?.role === 'customer' ? '/customer' : '/employee'} className="btn btn-outline btn-sm">
            &larr; Back
          </Link>
        </div>

        <div className="balance-highlight">
          <span className="label">Current Available Balance</span>
          <h1 className="balance-large">
            ₹{parseFloat(account.balance).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </h1>
          <p className="paise-raw">({account.balance_paise} paise stored internally)</p>
        </div>

        <div className="detail-grid">
          <div className="detail-item">
            <span className="label">Account Owner</span>
            <p className="value">{account.owner_name} (@{account.owner_username})</p>
          </div>
          <div className="detail-item">
            <span className="label">Owner Email</span>
            <p className="value">{account.owner_email}</p>
          </div>
          <div className="detail-item">
            <span className="label">Account Type</span>
            <p className="value">{account.account_type.toUpperCase()}</p>
          </div>
          <div className="detail-item">
            <span className="label">Account Status</span>
            <p className="value">{account.status.toUpperCase()}</p>
          </div>
          <div className="detail-item">
            <span className="label">Date Opened</span>
            <p className="value">{account.created_at}</p>
          </div>
          <div className="detail-item">
            <span className="label">Last Updated</span>
            <p className="value">{account.updated_at}</p>
          </div>
        </div>
      </div>

      {/* Transaction Action Form (Deposit / Withdraw) */}
      <div className="card transaction-action-card">
        <h3>Transact: Deposit & Withdraw (Issues #5, #6)</h3>
        {isClosed && (
          <div className="alert alert-danger">
            This account is closed. No further deposits or withdrawals are permitted.
          </div>
        )}
        {isFrozen && (
          <div className="alert alert-warning">
            This account is currently frozen. Transactions are temporarily suspended. Contact bank administration.
          </div>
        )}

        {!isClosed && !isFrozen && (
          <form onSubmit={handleTransactionSubmit} className="tx-form">
            {txSuccess && <div className="alert alert-success">{txSuccess}</div>}
            {txError && <div className="alert alert-danger">{txError}</div>}

            <div className="tx-form-row">
              <div className="form-group flex-1">
                <label>Operation Type</label>
                <select
                  className="input-control"
                  value={txType}
                  onChange={(e) => setTxType(e.target.value)}
                  disabled={txLoading}
                >
                  <option value="deposit">Deposit Money</option>
                  <option value="withdrawal">Withdraw Money</option>
                </select>
              </div>

              <div className="form-group flex-1">
                <label>Amount (₹)</label>
                <input
                  type="number"
                  step="0.01"
                  min="0.01"
                  className="input-control"
                  placeholder="e.g. 500.00"
                  value={txAmount}
                  onChange={(e) => setTxAmount(e.target.value)}
                  disabled={txLoading}
                  required
                />
              </div>

              <div className="form-group flex-2">
                <label>Note / Description (Optional)</label>
                <input
                  type="text"
                  className="input-control"
                  placeholder="e.g. Cash deposit, grocery payment"
                  value={txDesc}
                  onChange={(e) => setTxDesc(e.target.value)}
                  disabled={txLoading}
                />
              </div>

              <div className="form-group form-action-col">
                <button
                  type="submit"
                  className={`btn ${txType === 'deposit' ? 'btn-success' : 'btn-primary'} btn-block`}
                  disabled={txLoading}
                >
                  {txLoading ? 'Processing...' : txType === 'deposit' ? 'Confirm Deposit' : 'Confirm Withdrawal'}
                </button>
              </div>
            </div>
          </form>
        )}
      </div>

      {/* Transaction Ledger Table (Issue #7) */}
      <div className="card transaction-ledger-card">
        <div className="card-header-simple">
          <h3>Transaction History & Ledger (Issue #7)</h3>
          <span className="badge-count">{transactions.length} record(s)</span>
        </div>

        {transactions.length === 0 ? (
          <div className="empty-state small">
            <p>No transactions recorded yet for this account.</p>
          </div>
        ) : (
          <div className="table-responsive">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Ref ID</th>
                  <th>Date & Time</th>
                  <th>Type</th>
                  <th>Amount (₹)</th>
                  <th>Balance After (₹)</th>
                  <th>Description</th>
                </tr>
              </thead>
              <tbody>
                {transactions.map((t) => (
                  <tr key={t.id}>
                    <td><code>{t.reference_id}</code></td>
                    <td><small>{t.created_at}</small></td>
                    <td>
                      <span className={`status-badge ${t.transaction_type === 'deposit' ? 'badge-active' : 'badge-closed'}`}>
                        {t.transaction_type.toUpperCase()}
                      </span>
                    </td>
                    <td>
                      <strong className={t.transaction_type === 'deposit' ? 'text-success' : 'text-danger'}>
                        {t.transaction_type === 'deposit' ? '+' : '-'}₹{parseFloat(t.amount).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                      </strong>
                    </td>
                    <td>
                      ₹{parseFloat(t.balance_after).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                    </td>
                    <td>{t.description || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
