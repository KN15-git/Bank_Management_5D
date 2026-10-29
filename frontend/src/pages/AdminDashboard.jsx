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

  useEffect(() => {
    fetchUsers();
    fetchBackups();
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
    } catch (err) {
      setBackupError(err.message || 'Disaster recovery restoration failed.');
    } finally {
      setRestoringId(null);
    }
  };

  return (
    <div className="dashboard-layout">
      <header className="page-header">
        <div>
          <h1>System Administration</h1>
          <p className="subtitle">Role-Based Access Control & User Lifecycle</p>
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
            <h2>💾 Database Backup & Disaster Recovery</h2>
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
    </div>
  );
};
