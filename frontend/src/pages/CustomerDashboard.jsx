import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { apiRequest } from '../services/api';
import { useAuth } from '../context/AuthContext';

export const CustomerDashboard = () => {
  const { user } = useAuth();
  const [accounts, setAccounts] = useState([]);
  const [loans, setLoans] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [successMsg, setSuccessMsg] = useState('');
  const [showOpenModal, setShowOpenModal] = useState(false);
  const [initialDeposit, setInitialDeposit] = useState('1000.00');
  const [modalLoading, setModalLoading] = useState(false);

  // Fund transfer modal states (Issues #8 & #9)
  const [showTransferModal, setShowTransferModal] = useState(false);
  const [transferSourceId, setTransferSourceId] = useState('');
  const [transferDestNumber, setTransferDestNumber] = useState('');
  const [transferAmount, setTransferAmount] = useState('');
  const [transferDesc, setTransferDesc] = useState('');
  const [transferError, setTransferError] = useState('');
  const [transferLoading, setTransferLoading] = useState(false);

  // Loan application modal states (Issues #10 & #12)
  const [showLoanModal, setShowLoanModal] = useState(false);
  const [loanType, setLoanType] = useState('personal');
  const [loanAmount, setLoanAmount] = useState('');
  const [loanTermMonths, setLoanTermMonths] = useState('12');
  const [loanAccountId, setLoanAccountId] = useState('');
  const [loanPurpose, setLoanPurpose] = useState('');
  const [loanError, setLoanError] = useState('');
  const [loanLoading, setLoanLoading] = useState(false);

  const fetchDashboardData = async () => {
    setLoading(true);
    setError('');
    try {
      const [accData, loanData] = await Promise.all([
        apiRequest('/api/accounts'),
        apiRequest('/api/loans'),
      ]);
      const list = accData.accounts || [];
      setAccounts(list);
      setLoans(loanData.loans || []);
      const firstActive = list.find((a) => a.status === 'active');
      if (firstActive && !transferSourceId) {
        setTransferSourceId(String(firstActive.id));
      }
      if (firstActive && !loanAccountId) {
        setLoanAccountId(String(firstActive.id));
      }
    } catch (err) {
      setError(err.message || 'Failed to load dashboard data.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDashboardData();
  }, []);

  const handleOpenAccount = async (e) => {
    e.preventDefault();
    setModalLoading(true);
    setError('');
    setSuccessMsg('');
    try {
      await apiRequest('/api/accounts', {
        method: 'POST',
        body: JSON.stringify({
          account_type: 'savings',
          initial_deposit: initialDeposit,
        }),
      });
      setShowOpenModal(false);
      await fetchDashboardData();
    } catch (err) {
      setError(err.message || 'Failed to open account.');
    } finally {
      setModalLoading(false);
    }
  };

  const openTransferModal = () => {
    const activeAccs = accounts.filter((a) => a.status === 'active');
    if (activeAccs.length > 0 && !transferSourceId) {
      setTransferSourceId(String(activeAccs[0].id));
    }
    setTransferError('');
    setSuccessMsg('');
    setShowTransferModal(true);
  };

  const handleTransferSubmit = async (e) => {
    e.preventDefault();
    setTransferError('');
    setSuccessMsg('');

    if (!transferSourceId) {
      setTransferError('Please select a source account.');
      return;
    }
    const cleanDest = transferDestNumber.trim();
    if (!cleanDest) {
      setTransferError('Please enter a destination account number.');
      return;
    }
    const parsedAmount = parseFloat(transferAmount);
    if (isNaN(parsedAmount) || parsedAmount <= 0) {
      setTransferError('Please enter a valid transfer amount greater than zero.');
      return;
    }

    setTransferLoading(true);
    try {
      const data = await apiRequest(`/api/accounts/${transferSourceId}/transfer`, {
        method: 'POST',
        body: JSON.stringify({
          destination_account_number: cleanDest,
          amount: transferAmount,
          description: transferDesc,
        }),
      });
      const trf = data.transfer || data.transaction;
      setSuccessMsg(
        `Transferred ₹${trf.amount} from A/C #${trf.source_account_number} to A/C #${trf.destination_account_number} (Ref: ${trf.reference_id})`
      );
      setShowTransferModal(false);
      setTransferDestNumber('');
      setTransferAmount('');
      setTransferDesc('');
      await fetchDashboardData();
    } catch (err) {
      setTransferError(err.message || 'Transfer failed.');
    } finally {
      setTransferLoading(false);
    }
  };

  const openLoanModal = () => {
    setLoanError('');
    setSuccessMsg('');
    setShowLoanModal(true);
  };

  const handleLoanSubmit = async (e) => {
    e.preventDefault();
    setLoanError('');
    setSuccessMsg('');

    const parsedAmount = parseFloat(loanAmount);
    if (isNaN(parsedAmount) || parsedAmount <= 0) {
      setLoanError('Please enter a valid loan amount greater than zero.');
      return;
    }
    const parsedTerm = parseInt(loanTermMonths, 10);
    if (isNaN(parsedTerm) || parsedTerm < 1 || parsedTerm > 360) {
      setLoanError('Please enter a valid loan term between 1 and 360 months.');
      return;
    }
    if (!loanPurpose.trim()) {
      setLoanError('Please specify the purpose of the loan.');
      return;
    }

    setLoanLoading(true);
    try {
      const data = await apiRequest('/api/loans', {
        method: 'POST',
        body: JSON.stringify({
          loan_type: loanType,
          amount: loanAmount,
          term_months: parsedTerm,
          account_id: loanAccountId ? parseInt(loanAccountId, 10) : null,
          purpose: loanPurpose.trim(),
        }),
      });
      const submittedLoan = data.loan;
      setSuccessMsg(
        `Loan application submitted! Reference ID: ${submittedLoan.reference_id} (Status: ${submittedLoan.status.toUpperCase()})`
      );
      setShowLoanModal(false);
      setLoanAmount('');
      setLoanPurpose('');
      await fetchDashboardData();
    } catch (err) {
      setLoanError(err.message || 'Failed to submit loan application.');
    } finally {
      setLoanLoading(false);
    }
  };

  const activeAccounts = accounts.filter((a) => a.status === 'active');

  return (
    <div className="dashboard-layout">
      <header className="page-header">
        <div>
          <h1>Welcome, {user?.full_name}</h1>
          <p className="subtitle">Customer Portal &bull; Account &amp; Loan Overview</p>
        </div>
        <div className="action-buttons">
          {activeAccounts.length > 0 && (
            <button className="btn btn-outline" onClick={openTransferModal}>
              &#8644; Transfer Funds
            </button>
          )}
          <button className="btn btn-outline" onClick={openLoanModal}>
            + Apply for Loan
          </button>
          <button className="btn btn-primary" onClick={() => setShowOpenModal(true)}>
            + Open Savings Account
          </button>
        </div>
      </header>

      {error && <div className="alert alert-danger">{error}</div>}
      {successMsg && <div className="alert alert-success">{successMsg}</div>}

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

      {/* Loan Applications Section (Issues #10 & #12) */}
      <section style={{ marginTop: '2.5rem' }}>
        <div className="page-header" style={{ marginBottom: '1rem' }}>
          <div>
            <h2>My Loan Applications</h2>
            <p className="subtitle">Track your submitted loan applications and approval status</p>
          </div>
        </div>

        {loans.length === 0 ? (
          <div className="empty-state">
            <p>You have not submitted any loan applications yet.</p>
          </div>
        ) : (
          <div className="table-responsive">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Reference ID</th>
                  <th>Loan Type</th>
                  <th>Amount (₹)</th>
                  <th>Term &amp; Rate</th>
                  <th>Linked A/C</th>
                  <th>Purpose</th>
                  <th>Status</th>
                  <th>Officer Decision / Notes</th>
                </tr>
              </thead>
              <tbody>
                {loans.map((loan) => (
                  <tr key={loan.id}>
                    <td><strong>{loan.reference_id}</strong></td>
                    <td><span className="badge-type">{loan.loan_type.toUpperCase()}</span></td>
                    <td>
                      <strong>
                        ₹{parseFloat(loan.amount).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                      </strong>
                    </td>
                    <td>{loan.term_months} mos @ {loan.interest_rate}%</td>
                    <td>{loan.account_number ? `#${loan.account_number}` : '—'}</td>
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
                        <span className="text-muted">Awaiting officer review</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

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

      {showTransferModal && (
        <div className="modal-overlay">
          <div className="modal-content">
            <h3>Transfer Funds Between Accounts</h3>
            <p className="subtitle">Atomic transfer from your active account to any active destination account.</p>
            {transferError && <div className="alert alert-danger">{transferError}</div>}
            <form onSubmit={handleTransferSubmit}>
              <div className="form-group">
                <label>Source Account</label>
                <select
                  className="input-control"
                  value={transferSourceId}
                  onChange={(e) => setTransferSourceId(e.target.value)}
                  disabled={transferLoading}
                  required
                >
                  {activeAccounts.map((a) => (
                    <option key={a.id} value={a.id}>
                      #{a.account_number} ({a.account_type.toUpperCase()}) — Bal: ₹{a.balance}
                    </option>
                  ))}
                </select>
              </div>

              <div className="form-group">
                <label>Destination Account Number</label>
                <input
                  type="text"
                  className="input-control"
                  placeholder="Enter 12-digit account number (e.g. 200987654321)"
                  value={transferDestNumber}
                  onChange={(e) => setTransferDestNumber(e.target.value)}
                  disabled={transferLoading}
                  required
                />
              </div>

              <div className="form-group">
                <label>Amount (₹)</label>
                <input
                  type="number"
                  step="0.01"
                  min="0.01"
                  className="input-control"
                  placeholder="e.g. 1000.00"
                  value={transferAmount}
                  onChange={(e) => setTransferAmount(e.target.value)}
                  disabled={transferLoading}
                  required
                />
              </div>

              <div className="form-group">
                <label>Description / Reference (Optional)</label>
                <input
                  type="text"
                  className="input-control"
                  placeholder="e.g. Rent payment, savings transfer"
                  value={transferDesc}
                  onChange={(e) => setTransferDesc(e.target.value)}
                  disabled={transferLoading}
                />
              </div>

              <div className="modal-actions">
                <button
                  type="button"
                  className="btn btn-outline"
                  onClick={() => setShowTransferModal(false)}
                  disabled={transferLoading}
                >
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary" disabled={transferLoading}>
                  {transferLoading ? 'Transferring...' : 'Confirm Transfer'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {showLoanModal && (
        <div className="modal-overlay">
          <div className="modal-content">
            <h3>Apply for a Bank Loan</h3>
            <p className="subtitle">Submit an online loan application for review by a bank loan officer.</p>
            {loanError && <div className="alert alert-danger">{loanError}</div>}
            <form onSubmit={handleLoanSubmit}>
              <div className="form-group">
                <label>Loan Type</label>
                <select
                  className="input-control"
                  value={loanType}
                  onChange={(e) => setLoanType(e.target.value)}
                  disabled={loanLoading}
                >
                  <option value="personal">Personal Loan (11.5% p.a.)</option>
                  <option value="home">Home Loan (8.5% p.a.)</option>
                  <option value="education">Education Loan (9.0% p.a.)</option>
                  <option value="vehicle">Vehicle Loan (9.5% p.a.)</option>
                  <option value="business">Business Loan (12.0% p.a.)</option>
                </select>
              </div>

              <div className="form-group">
                <label>Requested Amount (₹)</label>
                <input
                  type="number"
                  step="0.01"
                  min="1"
                  className="input-control"
                  placeholder="e.g. 50000.00"
                  value={loanAmount}
                  onChange={(e) => setLoanAmount(e.target.value)}
                  disabled={loanLoading}
                  required
                />
              </div>

              <div className="form-group">
                <label>Repayment Term (Months)</label>
                <input
                  type="number"
                  min="1"
                  max="360"
                  className="input-control"
                  placeholder="e.g. 24"
                  value={loanTermMonths}
                  onChange={(e) => setLoanTermMonths(e.target.value)}
                  disabled={loanLoading}
                  required
                />
              </div>

              <div className="form-group">
                <label>Linked Active Account (Optional)</label>
                <select
                  className="input-control"
                  value={loanAccountId}
                  onChange={(e) => setLoanAccountId(e.target.value)}
                  disabled={loanLoading}
                >
                  <option value="">-- No linked account --</option>
                  {activeAccounts.map((a) => (
                    <option key={a.id} value={a.id}>
                      #{a.account_number} ({a.account_type.toUpperCase()}) — Bal: ₹{a.balance}
                    </option>
                  ))}
                </select>
              </div>

              <div className="form-group">
                <label>Loan Purpose</label>
                <input
                  type="text"
                  className="input-control"
                  placeholder="Describe the purpose of the loan"
                  value={loanPurpose}
                  onChange={(e) => setLoanPurpose(e.target.value)}
                  disabled={loanLoading}
                  required
                />
              </div>

              <div className="modal-actions">
                <button
                  type="button"
                  className="btn btn-outline"
                  onClick={() => setShowLoanModal(false)}
                  disabled={loanLoading}
                >
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary" disabled={loanLoading}>
                  {loanLoading ? 'Submitting...' : 'Submit Application'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
