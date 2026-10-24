import React, { useState, useEffect } from 'react';
import { apiRequest } from '../services/api';
import { useAuth } from '../context/AuthContext';

export const AdminDashboard = () => {
  const { user: currentUser } = useAuth();
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

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

  useEffect(() => {
    fetchUsers();
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
    </div>
  );
};
