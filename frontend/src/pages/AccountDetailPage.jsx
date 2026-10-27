import React, { useState, useEffect, useMemo } from 'react';
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


  // Transaction history filters, pagination, and export (Issues #13-#15).
  const [filters, setFilters] = useState({
    type: '', search: '', date_from: '', date_to: '', sort_by: 'date', sort_order: 'desc',
  });
  const [page, setPage] = useState(1);
  const [perPage, setPerPage] = useState(10);
  const [pagination, setPagination] = useState({
    page: 1, per_page: 10, total: 0, total_pages: 0, has_next: false, has_previous: false,
  });
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState('');
  const [historyReloadKey, setHistoryReloadKey] = useState(0);

  const transactionQuery = useMemo(() => {
    const params = new URLSearchParams();
    Object.entries(filters).forEach(([key, value]) => {
      if (value) params.set(key, value);
    });
    params.set('page', String(page));
    params.set('per_page', String(perPage));
    return params.toString();
  }, [filters, page, perPage]);

  // Transaction form states
  const [txType, setTxType] = useState('deposit');
  const [txAmount, setTxAmount] = useState('');
  const [txDesc, setTxDesc] = useState('');
  const [destAccountNumber, setDestAccountNumber] = useState('');
  const [txLoading, setTxLoading] = useState(false);
  const [txSuccess, setTxSuccess] = useState('');
  const [txError, setTxError] = useState('');

  // Load account details independently from transaction history to avoid stale-response races.
  useEffect(() => {
    let cancelled = false;
    const loadAccount = async () => {
      setLoading(true);
      setError('');
      try {
        const data = await apiRequest(`/api/accounts/${id}`);
        if (!cancelled) setAccount(data.account);
      } catch (err) {
        if (!cancelled) setError(err.message || 'Failed to load account details.');
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    loadAccount();
    return () => { cancelled = true; };
  }, [id]);

  // Every filter/page change loads only the requested page; prior requests are ignored.
  useEffect(() => {
    let cancelled = false;
    const loadHistory = async () => {
      setHistoryLoading(true);
      setHistoryError('');
      try {
        const data = await apiRequest(`/api/accounts/${id}/transactions?${transactionQuery}`);
        if (!cancelled) {
          setTransactions(data.transactions || []);
          setPagination(data.pagination || {
            page: 1, per_page: perPage, total: 0, total_pages: 0,
            has_next: false, has_previous: false,
          });
        }
      } catch (err) {
        if (!cancelled) setHistoryError(err.message || 'Could not load transaction history.');
      } finally {
        if (!cancelled) setHistoryLoading(false);
      }
    };
    loadHistory();
    return () => { cancelled = true; };
  }, [id, transactionQuery, historyReloadKey]);

  const handleTransactionSubmit = async (e) => {
    e.preventDefault();
    setTxError('');
    setTxSuccess('');

    const parsedAmount = parseFloat(txAmount);
    if (isNaN(parsedAmount) || parsedAmount <= 0) {
      setTxError('Please enter a valid amount greater than zero.');
      return;
    }

    if (txType === 'transfer') {
      const cleanDest = destAccountNumber.trim();
      if (!cleanDest) {
        setTxError('Please enter a destination account number.');
        return;
      }
      if (account && cleanDest === account.account_number) {
        setTxError('Cannot transfer funds to the same account.');
        return;
      }
    }

    setTxLoading(true);
    const endpoint =
      txType === 'deposit'
        ? `/api/accounts/${id}/deposit`
        : txType === 'withdrawal'
        ? `/api/accounts/${id}/withdraw`
        : `/api/accounts/${id}/transfer`;

    const payload =
      txType === 'transfer'
        ? {
            destination_account_number: destAccountNumber.trim(),
            amount: txAmount,
            description: txDesc,
          }
        : {
            amount: txAmount,
            description: txDesc,
          };

    try {
      const data = await apiRequest(endpoint, {
        method: 'POST',
        body: JSON.stringify(payload),
      });

      if (txType === 'transfer') {
        const trf = data.transfer || data.transaction;
        setTxSuccess(
          `Transfer of ₹${trf.amount} to A/C #${trf.destination_account_number} successful! Ref: ${trf.reference_id}`
        );
        setDestAccountNumber('');
      } else {
        setTxSuccess(
          `${txType === 'deposit' ? 'Deposit' : 'Withdrawal'} of ₹${data.transaction.amount} successful! Ref: ${data.transaction.reference_id}`
        );
      }
      setTxAmount('');
      setTxDesc('');

      // Refresh account details and transaction history
      const accData = await apiRequest(`/api/accounts/${id}`);
      setAccount(accData.account);
      // Refresh the active filtered/sorted page instead of overwriting it with unfiltered history.
      setHistoryReloadKey((current) => current + 1);
    } catch (err) {
      const actionLabel =
        txType === 'deposit' ? 'Deposit' : txType === 'withdrawal' ? 'Withdrawal' : 'Transfer';
      setTxError(err.message || `${actionLabel} failed.`);
    } finally {
      setTxLoading(false);
    }
  };

  const isCreditTransaction = (type) => type === 'deposit' || type === 'transfer_in';

  const formatTransactionTypeLabel = (type) => {
    if (type === 'transfer_out') return 'TRANSFER OUT';
    if (type === 'transfer_in') return 'TRANSFER IN';
    return (type || '').toUpperCase();
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

      {/* Transaction Action Form (Deposit / Withdraw / Transfer) */}
      <div className="card transaction-action-card">
        <h3>Transact: Deposit, Withdraw &amp; Transfer (Issues #5, #6, #8, #9)</h3>
        {isClosed && (
          <div className="alert alert-danger">
            This account is closed. No further deposits, withdrawals, or transfers are permitted.
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
                  onChange={(e) => {
                    setTxType(e.target.value);
                    setTxError('');
                    setTxSuccess('');
                  }}
                  disabled={txLoading}
                >
                  <option value="deposit">Deposit Money</option>
                  <option value="withdrawal">Withdraw Money</option>
                  <option value="transfer">Transfer Funds</option>
                </select>
              </div>

              {txType === 'transfer' && (
                <div className="form-group flex-1">
                  <label>Destination Account #</label>
                  <input
                    type="text"
                    className="input-control"
                    placeholder="e.g. 200987654321"
                    value={destAccountNumber}
                    onChange={(e) => setDestAccountNumber(e.target.value)}
                    disabled={txLoading}
                    required
                  />
                </div>
              )}

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
                  placeholder={
                    txType === 'transfer'
                      ? 'e.g. Rent transfer, bill split'
                      : 'e.g. Cash deposit, grocery payment'
                  }
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
                  {txLoading
                    ? 'Processing...'
                    : txType === 'deposit'
                    ? 'Confirm Deposit'
                    : txType === 'withdrawal'
                    ? 'Confirm Withdrawal'
                    : 'Confirm Transfer'}
                </button>
              </div>
            </div>
          </form>
        )}
      </div>

      {/* Transaction History (Issues #13, #14 and #15) */}
      <div className="card transaction-ledger-card">
        <div className="card-header-simple">
          <div>
            <h3>Transaction History</h3>
            <p className="subtitle">Search, filter, sort, and export account transactions.</p>
          </div>
          <span className="badge-count">{pagination.total} record(s)</span>
        </div>

        <div className="transaction-toolbar">
          <div className="form-group">
            <label htmlFor="txn-search">Search reference or description</label>
            <input
              id="txn-search"
              className="input-control"
              value={filters.search}
              placeholder="Search transactions..."
              onChange={(event) => {
                setFilters({ ...filters, search: event.target.value });
                setPage(1);
              }}
            />
          </div>
          <div className="form-group">
            <label htmlFor="txn-type">Transaction type</label>
            <select
              id="txn-type"
              className="input-control"
              value={filters.type}
              onChange={(event) => {
                setFilters({ ...filters, type: event.target.value });
                setPage(1);
              }}
            >
              <option value="">All transactions</option>
              <option value="deposit">Deposit</option>
              <option value="withdrawal">Withdrawal</option>
              <option value="transfer_in">Transfer in</option>
              <option value="transfer_out">Transfer out</option>
            </select>
          </div>
          <div className="form-group">
            <label htmlFor="txn-from">From date</label>
            <input
              id="txn-from"
              type="date"
              className="input-control"
              value={filters.date_from}
              onChange={(event) => {
                setFilters({ ...filters, date_from: event.target.value });
                setPage(1);
              }}
            />
          </div>
          <div className="form-group">
            <label htmlFor="txn-to">To date</label>
            <input
              id="txn-to"
              type="date"
              className="input-control"
              value={filters.date_to}
              onChange={(event) => {
                setFilters({ ...filters, date_to: event.target.value });
                setPage(1);
              }}
            />
          </div>
          <div className="form-group">
            <label htmlFor="txn-sort">Sort by</label>
            <select
              id="txn-sort"
              className="input-control"
              value={filters.sort_by}
              onChange={(event) => {
                setFilters({ ...filters, sort_by: event.target.value });
                setPage(1);
              }}
            >
              <option value="date">Date</option>
              <option value="amount">Amount</option>
              <option value="type">Type</option>
              <option value="reference">Reference</option>
            </select>
          </div>
          <div className="form-group">
            <label htmlFor="txn-order">Order</label>
            <select
              id="txn-order"
              className="input-control"
              value={filters.sort_order}
              onChange={(event) => {
                setFilters({ ...filters, sort_order: event.target.value });
                setPage(1);
              }}
            >
              <option value="desc">Descending</option>
              <option value="asc">Ascending</option>
            </select>
          </div>
        </div>

        <div className="transaction-actions">
          <button
            type="button"
            className="btn btn-outline"
            onClick={() => {
              setFilters({
                type: '',
                search: '',
                date_from: '',
                date_to: '',
                sort_by: 'date',
                sort_order: 'desc',
              });
              setPage(1);
            }}
          >
            Clear filters
          </button>
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => {
              const params = new URLSearchParams();
              Object.entries(filters).forEach(([key, value]) => {
                if (value) params.set(key, value);
              });
              window.location.href = `/api/accounts/${id}/transactions/export?${params.toString()}`;
            }}
          >
            Export CSV statement
          </button>
          <label className="page-size-control">
            Rows per page
            <select
              className="input-control"
              value={perPage}
              onChange={(event) => {
                setPerPage(Number(event.target.value));
                setPage(1);
              }}
            >
              <option value={5}>5</option>
              <option value={10}>10</option>
              <option value={25}>25</option>
              <option value={50}>50</option>
            </select>
          </label>
        </div>

        {historyError && <div className="alert alert-danger">{historyError}</div>}
        {historyLoading ? (
          <p role="status">Loading transaction history...</p>
        ) : transactions.length === 0 ? (
          <div className="empty-state small">
            <p>No transactions match these filters.</p>
          </div>
        ) : (
          <div className="table-responsive">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Reference</th>
                  <th>Date &amp; time</th>
                  <th>Type</th>
                  <th>Amount (₹)</th>
                  <th>Balance after (₹)</th>
                  <th>Description</th>
                </tr>
              </thead>
              <tbody>
                {transactions.map((transaction) => {
                  const isCredit = isCreditTransaction(transaction.transaction_type);
                  return (
                    <tr key={transaction.id}>
                      <td><code>{transaction.reference_id}</code></td>
                      <td><small>{transaction.created_at}</small></td>
                      <td>
                        <span className={`status-badge ${isCredit ? 'badge-active' : 'badge-closed'}`}>
                          {formatTransactionTypeLabel(transaction.transaction_type)}
                        </span>
                      </td>
                      <td>
                        <strong className={isCredit ? 'text-success' : 'text-danger'}>
                          {isCredit ? '+' : '-'}₹{Number(transaction.amount).toLocaleString('en-IN', {
                            minimumFractionDigits: 2,
                            maximumFractionDigits: 2,
                          })}
                        </strong>
                      </td>
                      <td>
                        ₹{Number(transaction.balance_after).toLocaleString('en-IN', {
                          minimumFractionDigits: 2,
                          maximumFractionDigits: 2,
                        })}
                      </td>
                      <td>{transaction.description || '—'}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        <div className="pagination-controls">
          <button
            type="button"
            className="btn btn-outline"
            disabled={!pagination.has_previous || historyLoading}
            onClick={() => setPage((current) => Math.max(1, current - 1))}
          >
            Previous
          </button>
          <span>
            Page {pagination.page || page} of {Math.max(1, pagination.total_pages || 0)}
          </span>
          <button
            type="button"
            className="btn btn-outline"
            disabled={!pagination.has_next || historyLoading}
            onClick={() => setPage((current) => current + 1)}
          >
            Next
          </button>
        </div>
      </div>
    </div>
  );
};
