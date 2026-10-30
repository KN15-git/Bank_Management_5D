import React, { useState, useEffect } from 'react';
import { apiRequest } from '../services/api';
import { useAuth } from '../context/AuthContext';

export const AdminDashboard = () => {
  const { user: currentUser } = useAuth();
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // Backup & Disaster Recovery state (Issue #24)
  const [backups, setBackups] = useState([]);
  const [backupLoading, setBackupLoading] = useState(false);
  const [backupMsg, setBackupMsg] = useState('');
  const [backupError, setBackupError] = useState('');
  const [verifyingId, setVerifyingId] = useState(null);
  const [restoringId, setRestoringId] = useState(null);

  // Audit Logging & Compliance state (Issue #22)
  const [auditLogs, setAuditLogs] = useState([]);
  const [auditPagination, setAuditPagination] = useState({
    page: 1,
    per_page: 15,
    total: 0,
    total_pages: 0,
    has_next: false,
    has_previous: false,
  });
  const [auditSummary, setAuditSummary] = useState({
    total_matching: 0,
    security_alerts_count: 0,
    available_actions: [],
  });
  const [auditSearch, setAuditSearch] = useState('');
  const [auditCategory, setAuditCategory] = useState('');
  const [auditSeverity, setAuditSeverity] = useState('');
  const [auditAction, setAuditAction] = useState('');
  const [auditLoading, setAuditLoading] = useState(false);
  const [auditError, setAuditError] = useState('');

  const fetchUsers = async () => {
    setLoading(true);
    setError('');
    try {
      const data = await apiRequest('/api/users');
      setUsers(data.users || []);
    } catch (err) {
      setError(err.message || 'Failed to fetch users list.');
    } finally {
      setLoading(false);
    }
  };

  const fetchBackups = async () => {
    try {
      const data = await apiRequest('/api/admin/backups');
      setBackups(data.backups || []);
    } catch (err) {
      console.warn('Failed to fetch backups:', err);
    }
  };

  const buildAuditQuery = (page = 1, overrides = {}) => {
    const params = new URLSearchParams();
    params.set('page', String(page));
    params.set('per_page', '15');

    const qSearch = overrides.search !== undefined ? overrides.search : auditSearch;
    const qCat = overrides.category !== undefined ? overrides.category : auditCategory;
    const qSev = overrides.severity !== undefined ? overrides.severity : auditSeverity;
    const qAct = overrides.action !== undefined ? overrides.action : auditAction;

    if (qSearch && qSearch.trim()) params.set('search', qSearch.trim());
    if (qCat) params.set('category', qCat);
    if (qSev) params.set('severity', qSev);
    if (qAct) params.set('action', qAct);

    return params.toString();
  };

  const fetchAuditLogs = async (page = 1, overrides = {}) => {
    setAuditLoading(true);
    setAuditError('');
    try {
      const qs = buildAuditQuery(page, overrides);
      const data = await apiRequest(`/api/audit-logs?${qs}`);
      setAuditLogs(data.audit_logs || []);
      if (data.pagination) setAuditPagination(data.pagination);
      if (data.summary) setAuditSummary(data.summary);
    } catch (err) {
      setAuditError(err.message || 'Failed to load audit logs.');
    } finally {
      setAuditLoading(false);
    }
  };

  useEffect(() => {
    fetchUsers();
    fetchBackups();
    fetchAuditLogs(1);
  }, []);

  const handleRoleChange = async (targetUserId, newRole) => {
    if (currentUser.id === targetUserId && newRole !== 'admin') {
      alert('You cannot change or demote your own administrator role.');
      return;
    }

    try {
      await apiRequest(`/api/users/${targetUserId}/role`, {
        method: 'PATCH',
        body: JSON.stringify({ role: newRole }),
      });
      await fetchUsers();
      await fetchAuditLogs(auditPagination.page);
    } catch (err) {
      alert(`Role change failed: ${err.message}`);
    }
  };

  const handleStatusChange = async (targetUserId, currentActive) => {
    if (currentUser.id === targetUserId && currentActive) {
      alert('You cannot deactivate your own administrator account.');
      return;
    }

    const nextState = !currentActive;
    if (!window.confirm(`Are you sure you want to ${nextState ? 'activate' : 'deactivate'} this user account?`)) {
      return;
    }

    try {
      await apiRequest(`/api/users/${targetUserId}/status`, {
        method: 'PATCH',
        body: JSON.stringify({ is_active: nextState }),
      });
      await fetchUsers();
      await fetchAuditLogs(auditPagination.page);
    } catch (err) {
      alert(`Status update failed: ${err.message}`);
    }
  };

  // Issue #24: Create On-Demand Database Backup
  const handleCreateBackup = async () => {
    setBackupLoading(true);
    setBackupMsg('');
    setBackupError('');
    try {
      const data = await apiRequest('/api/admin/backups', {
        method: 'POST',
        body: JSON.stringify({ note: 'Manual backup triggered from Admin Dashboard' }),
      });
      setBackupMsg(`✅ Backup created successfully: ${data.backup.filename} (${(data.backup.file_size_bytes / 1024).toFixed(1)} KB)`);
      await fetchBackups();
      await fetchAuditLogs(1);
    } catch (err) {
      setBackupError(err.message || 'Failed to generate database backup.');
    } finally {
      setBackupLoading(false);
    }
  };

  // Issue #24: Verify SHA-256 Checksum & SQLite PRAGMA Integrity
  const handleVerifyBackup = async (backup) => {
    setVerifyingId(backup.id || backup.filename);
    setBackupMsg('');
    setBackupError('');
    try {
      const targetId = backup.id || backup.filename;
      const data = await apiRequest(`/api/admin/backups/${targetId}/verify`);
      if (data.valid) {
        alert(
          `✅ Backup Integrity Check Passed!\n\n` +
          `File: ${data.filename}\n` +
          `SHA-256 Checksum: ${data.current_sha256}\n` +
          `Integrity Check: ${data.integrity_check}\n` +
          `Checksum Matches: ${data.checksum_verified ? 'Yes' : 'No'}`
        );
      } else {
        alert(`❌ Backup Verification FAILED: ${data.error || data.integrity_check}`);
      }
    } catch (err) {
      alert(`Verification error: ${err.message}`);
    } finally {
      setVerifyingId(null);
    }
  };

  // Issue #24: Restore Live System from Backup with Pre-Restore Safety Snapshot
  const handleRestoreBackup = async (backup) => {
    const confirmMsg =
      `⚠️ CRITICAL WARNING: DISASTER RECOVERY RESTORATION\n\n` +
      `Restoring from "${backup.filename}" will revert the live database to this snapshot.\n\n` +
      `• An automatic PRE-RESTORE SAFETY SNAPSHOT will be created first.\n` +
      `• Any transactions created after this backup will be rolled back.\n\n` +
      `Are you sure you want to proceed with system restoration?`;

    if (!window.confirm(confirmMsg)) {
      return;
    }

    setRestoringId(backup.id || backup.filename);
    setBackupMsg('');
    setBackupError('');

    try {
      const targetId = backup.id || backup.filename;
      const data = await apiRequest(`/api/admin/backups/${targetId}/restore`, {
        method: 'POST',
      });
      setBackupMsg(
        `🔄 Database successfully restored from ${data.result.restored_filename}!\n` +
        `(Safety snapshot created: ${data.result.safety_snapshot})`
      );
      await fetchBackups();
      await fetchUsers();
      await fetchAuditLogs(1);
    } catch (err) {
      setBackupError(err.message || 'Disaster recovery restoration failed.');
    } finally {
      setRestoringId(null);
    }
  };

  const handleAuditFilterSubmit = (e) => {
    e.preventDefault();
    fetchAuditLogs(1);
  };

  const handleClearAuditFilters = () => {
    setAuditSearch('');
    setAuditCategory('');
    setAuditSeverity('');
    setAuditAction('');
    fetchAuditLogs(1, { search: '', category: '', severity: '', action: '' });
  };

  const getExportAuditUrl = () => {
    const qs = buildAuditQuery(1);
    return `/api/audit-logs/export?${qs}`;
  };

  return (
    <div className="dashboard-layout">
      <header className="page-header">
        <div>
          <h1>System Administration</h1>
          <p className="subtitle">Role-Based Access Control, Backups &amp; Security Audit Trail</p>
        </div>
      </header>

      {error && <div className="alert alert-danger">{error}</div>}

      {loading ? (
        <div className="center-container">
          <div className="spinner"></div>
          <p>Loading system users...</p>
        </div>
      ) : (
        <div className="table-responsive">
          <table className="data-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Full Name</th>
                <th>Username</th>
                <th>Email</th>
                <th>Assigned Role</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => {
                const isSelf = currentUser.id === u.id;
                return (
                  <tr key={u.id} className={isSelf ? 'row-self' : ''}>
                    <td>{u.id}</td>
                    <td>
                      <strong>{u.full_name}</strong> {isSelf && <span className="badge-self">(You)</span>}
                    </td>
                    <td>{u.username}</td>
                    <td>{u.email}</td>
                    <td>
                      <select
                        className="select-role"
                        value={u.role}
                        disabled={isSelf}
                        onChange={(e) => handleRoleChange(u.id, e.target.value)}
                      >
                        <option value="customer">customer</option>
                        <option value="employee">employee</option>
                        <option value="admin">admin</option>
                      </select>
                    </td>
                    <td>
                      <span className={`status-badge badge-${u.is_active ? 'active' : 'closed'}`}>
                        {u.is_active ? 'Active' : 'Deactivated'}
                      </span>
                    </td>
                    <td>
                      <button
                        className={`btn btn-xs ${u.is_active ? 'btn-danger' : 'btn-success'}`}
                        disabled={isSelf}
                        onClick={() => handleStatusChange(u.id, u.is_active)}
                      >
                        {u.is_active ? 'Deactivate' : 'Activate'}
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Issue #24: Database Backup & Disaster Recovery Section */}
      <div className="backup-card">
        <div className="backup-header-row">
          <div>
            <h2>💾 Database Backup &amp; Disaster Recovery</h2>
            <p className="subtitle">
              Online SQLite snapshots, SHA-256 integrity verification, and atomic rollback (Issue #24, SEC-07, SEC-10)
            </p>
          </div>
          <button
            className="btn btn-primary"
            onClick={handleCreateBackup}
            disabled={backupLoading}
          >
            {backupLoading ? 'Creating Backup...' : '➕ Create Instant Backup'}
          </button>
        </div>

        {backupMsg && <div className="alert alert-success" style={{ whiteSpace: 'pre-line' }}>{backupMsg}</div>}
        {backupError && <div className="alert alert-danger">{backupError}</div>}

        <div className="table-responsive" style={{ marginTop: '16px' }}>
          <table className="data-table">
            <thead>
              <tr>
                <th>Backup File</th>
                <th>Created At</th>
                <th>Size</th>
                <th>Type</th>
                <th>SHA-256 Checksum</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {backups.length === 0 ? (
                <tr>
                  <td colSpan="7" style={{ textAlign: 'center', padding: '24px', color: '#718096' }}>
                    No database snapshots recorded yet. Click "Create Instant Backup" above to generate one.
                  </td>
                </tr>
              ) : (
                backups.map((b) => {
                  const isVerifying = verifyingId === (b.id || b.filename);
                  const isRestoring = restoringId === (b.id || b.filename);
                  const isSafety = b.trigger_type === 'pre_restore_safety';
                  return (
                    <tr key={b.filename}>
                      <td>
                        <strong>{b.filename}</strong>
                      </td>
                      <td>{b.created_at || '—'}</td>
                      <td>{(b.file_size_bytes / 1024).toFixed(1)} KB</td>
                      <td>
                        <span className={`status-badge ${isSafety ? 'badge-safety' : 'badge-active'}`}>
                          {b.trigger_type || 'manual'}
                        </span>
                      </td>
                      <td>
                        <span className="checksum-hash" title={b.sha256_checksum}>
                          {b.sha256_checksum ? `${b.sha256_checksum.slice(0, 12)}...` : '—'}
                        </span>
                      </td>
                      <td>
                        <span className={`status-badge badge-${b.status === 'restored' ? 'closed' : 'active'}`}>
                          {b.status || 'valid'}
                        </span>
                      </td>
                      <td>
                        <div style={{ display: 'flex', gap: '6px' }}>
                          <button
                            className="btn btn-xs btn-outline"
                            onClick={() => handleVerifyBackup(b)}
                            disabled={isVerifying || isRestoring}
                            title="Verify Checksum and SQLite Integrity"
                          >
                            {isVerifying ? 'Verifying...' : '🔍 Verify'}
                          </button>
                          <button
                            className="btn btn-xs btn-danger"
                            onClick={() => handleRestoreBackup(b)}
                            disabled={isVerifying || isRestoring}
                            title="Restore live system to this snapshot"
                          >
                            {isRestoring ? 'Restoring...' : '🔄 Restore'}
                          </button>
                          {b.id && (
                            <a
                              href={`/api/admin/backups/${b.id}/download`}
                              className="btn btn-xs btn-outline"
                              download
                              title="Download backup database file"
                              style={{ textDecoration: 'none', display: 'inline-flex', alignItems: 'center' }}
                            >
                              ⬇️
                            </a>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Issue #22: System Audit Logs & Security Trail Section */}
      <div className="backup-card" style={{ marginTop: '28px' }}>
        <div className="backup-header-row">
          <div>
            <h2>🛡️ System Audit Logs &amp; Security Trail</h2>
            <p className="subtitle">
              Immutable compliance log of authentication, RBAC, account, transaction, and loan events (Issue #22) &bull;{' '}
              <strong>{auditSummary.total_matching}</strong> matching events ({auditSummary.security_alerts_count} warnings/critical)
            </p>
          </div>
          <div className="action-buttons">
            <a
              href={getExportAuditUrl()}
              className="btn btn-outline"
              download="system_audit_logs.csv"
              style={{ textDecoration: 'none' }}
            >
              ⬇️ Export Audit CSV
            </a>
          </div>
        </div>

        {auditError && <div className="alert alert-danger">{auditError}</div>}

        <form onSubmit={handleAuditFilterSubmit} className="search-form" style={{ marginTop: '12px', flexWrap: 'wrap', gap: '10px' }}>
          <input
            type="text"
            className="input-control"
            style={{ flex: '1 1 220px' }}
            placeholder="Search by username, action, IP, or details..."
            value={auditSearch}
            onChange={(e) => setAuditSearch(e.target.value)}
          />
          <select
            className="input-control"
            style={{ width: 'auto', minWidth: '150px' }}
            value={auditCategory}
            onChange={(e) => {
              setAuditCategory(e.target.value);
              fetchAuditLogs(1, { category: e.target.value });
            }}
          >
            <option value="">All Categories</option>
            <option value="authentication">Authentication</option>
            <option value="access_control">Access Control / RBAC</option>
            <option value="account">Account Lifecycle</option>
            <option value="transaction">Financial Transactions</option>
            <option value="loan">Loan Management</option>
            <option value="beneficiary">Beneficiaries</option>
            <option value="system">System &amp; Backups</option>
          </select>
          <select
            className="input-control"
            style={{ width: 'auto', minWidth: '140px' }}
            value={auditSeverity}
            onChange={(e) => {
              setAuditSeverity(e.target.value);
              fetchAuditLogs(1, { severity: e.target.value });
            }}
          >
            <option value="">All Severities</option>
            <option value="info">Info</option>
            <option value="warning">Warning</option>
            <option value="critical">Critical</option>
          </select>
          <select
            className="input-control"
            style={{ width: 'auto', minWidth: '170px' }}
            value={auditAction}
            onChange={(e) => {
              setAuditAction(e.target.value);
              fetchAuditLogs(1, { action: e.target.value });
            }}
          >
            <option value="">All Actions</option>
            {(auditSummary.available_actions || []).map((act) => (
              <option key={act} value={act}>
                {act}
              </option>
            ))}
          </select>
          <button type="submit" className="btn btn-primary" disabled={auditLoading}>
            Filter
          </button>
          {(auditSearch || auditCategory || auditSeverity || auditAction) && (
            <button type="button" className="btn btn-outline" onClick={handleClearAuditFilters}>
              Clear
            </button>
          )}
        </form>

        <div className="table-responsive" style={{ marginTop: '16px' }}>
          <table className="data-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Timestamp</th>
                <th>Actor (User)</th>
                <th>Action</th>
                <th>Category</th>
                <th>Severity</th>
                <th>Details</th>
                <th>IP Address</th>
              </tr>
            </thead>
            <tbody>
              {auditLoading ? (
                <tr>
                  <td colSpan="8" style={{ textAlign: 'center', padding: '24px' }}>
                    Loading audit trail...
                  </td>
                </tr>
              ) : auditLogs.length === 0 ? (
                <tr>
                  <td colSpan="8" style={{ textAlign: 'center', padding: '24px', color: '#718096' }}>
                    No audit log entries match the selected filters.
                  </td>
                </tr>
              ) : (
                auditLogs.map((log) => (
                  <tr key={log.id}>
                    <td>#{log.id}</td>
                    <td>{log.created_at}</td>
                    <td>
                      <div><strong>{log.username}</strong></div>
                      <small className="text-muted">
                        {log.user_id ? `ID: ${log.user_id} (${log.user_role})` : 'System'}
                      </small>
                    </td>
                    <td><strong>{log.action}</strong></td>
                    <td><span className="badge-type">{log.category.toUpperCase()}</span></td>
                    <td>
                      <span
                        className={`status-badge badge-${
                          log.severity === 'critical'
                            ? 'closed'
                            : log.severity === 'warning'
                            ? 'frozen'
                            : 'active'
                        }`}
                      >
                        {log.severity.toUpperCase()}
                      </span>
                    </td>
                    <td style={{ maxWidth: '340px', wordBreak: 'break-word' }}>{log.details}</td>
                    <td><code>{log.ip_address}</code></td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {auditPagination.total_pages > 1 && (
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '14px' }}>
            <small className="text-muted">
              Page {auditPagination.page} of {auditPagination.total_pages} ({auditPagination.total} total events)
            </small>
            <div className="action-buttons">
              <button
                type="button"
                className="btn btn-outline btn-xs"
                disabled={!auditPagination.has_previous || auditLoading}
                onClick={() => fetchAuditLogs(auditPagination.page - 1)}
              >
                &larr; Previous
              </button>
              <button
                type="button"
                className="btn btn-outline btn-xs"
                disabled={!auditPagination.has_next || auditLoading}
                onClick={() => fetchAuditLogs(auditPagination.page + 1)}
              >
                Next &rarr;
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
