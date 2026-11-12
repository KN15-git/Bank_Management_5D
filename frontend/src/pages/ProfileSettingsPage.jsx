import React, { useEffect, useState } from 'react';
import { apiRequest } from '../services/api';
import { useAuth } from '../context/AuthContext';

export const ProfileSettingsPage = () => {
  const { user, updateUser } = useAuth();
  const [profile, setProfile] = useState({ full_name: '', email: '' });
  const [passwords, setPasswords] = useState({ current_password: '', new_password: '', confirm_password: '' });
  const [profileStatus, setProfileStatus] = useState({ loading: false, error: '', success: '' });
  const [passwordStatus, setPasswordStatus] = useState({ loading: false, error: '', success: '' });

  useEffect(() => {
    setProfile({ full_name: user?.full_name || '', email: user?.email || '' });
  }, [user]);

  const handleProfileChange = (event) => {
    const { name, value } = event.target;
    setProfile((current) => ({ ...current, [name]: value }));
  };

  const saveProfile = async (event) => {
    event.preventDefault();
    setProfileStatus({ loading: true, error: '', success: '' });
    if (!profile.full_name.trim() || !profile.email.trim()) {
      setProfileStatus({ loading: false, error: 'Full name and email are required.', success: '' });
      return;
    }
    try {
      const data = await apiRequest('/api/auth/profile', {
        method: 'PATCH',
        body: JSON.stringify(profile),
      });
      updateUser(data.user);
      setProfileStatus({ loading: false, error: '', success: data.message || 'Profile updated successfully.' });
    } catch (error) {
      setProfileStatus({ loading: false, error: error.message, success: '' });
    }
  };

  const changePassword = async (event) => {
    event.preventDefault();
    setPasswordStatus({ loading: true, error: '', success: '' });
    if (passwords.new_password !== passwords.confirm_password) {
      setPasswordStatus({ loading: false, error: 'New password and confirmation do not match.', success: '' });
      return;
    }
    try {
      const data = await apiRequest('/api/auth/password', {
        method: 'PATCH',
        body: JSON.stringify({
          current_password: passwords.current_password,
          new_password: passwords.new_password,
        }),
      });
      setPasswords({ current_password: '', new_password: '', confirm_password: '' });
      setPasswordStatus({ loading: false, error: '', success: data.message || 'Password changed successfully.' });
    } catch (error) {
      setPasswordStatus({ loading: false, error: error.message, success: '' });
    }
  };

  return (
    <section className="profile-settings-page" aria-labelledby="profile-settings-title">
      <header className="page-header profile-page-header">
        <div>
          <h1 id="profile-settings-title">Profile &amp; Account Settings</h1>
          <p className="subtitle">Manage your personal information and keep your account secure.</p>
        </div>
        <span className={`role-pill role-${user?.role || 'customer'}`}>{user?.role}</span>
      </header>

      <div className="profile-settings-grid">
        <section className="card" aria-labelledby="personal-information-title">
          <h2 id="personal-information-title">Personal information</h2>
          <p className="subtitle">Your username and role are managed by the bank and cannot be edited here.</p>
          <div className="profile-readonly-grid">
            <div><span className="label">Username</span><strong>{user?.username || '—'}</strong></div>
            <div><span className="label">Account role</span><strong>{user?.role || '—'}</strong></div>
          </div>
          <form onSubmit={saveProfile} noValidate>
            <div className="form-group">
              <label htmlFor="profile-full-name">Full name</label>
              <input id="profile-full-name" name="full_name" className="input-control" value={profile.full_name} onChange={handleProfileChange} maxLength={100} autoComplete="name" required />
            </div>
            <div className="form-group">
              <label htmlFor="profile-email">Email address</label>
              <input id="profile-email" name="email" type="email" className="input-control" value={profile.email} onChange={handleProfileChange} maxLength={254} autoComplete="email" required />
            </div>
            {profileStatus.error && <div className="alert alert-danger" role="alert">{profileStatus.error}</div>}
            {profileStatus.success && <div className="alert alert-success" role="status">{profileStatus.success}</div>}
            <button className="btn btn-primary" type="submit" disabled={profileStatus.loading}>
              {profileStatus.loading ? 'Saving...' : 'Save profile'}
            </button>
          </form>
        </section>

        <section className="card" aria-labelledby="security-title">
          <h2 id="security-title">Password &amp; security</h2>
          <p className="subtitle">Verify your current password before choosing a new one.</p>
          <form onSubmit={changePassword}>
            <div className="form-group">
              <label htmlFor="current-password">Current password</label>
              <input id="current-password" type="password" className="input-control" autoComplete="current-password" value={passwords.current_password} onChange={(e) => setPasswords({ ...passwords, current_password: e.target.value })} required />
            </div>
            <div className="form-group">
              <label htmlFor="new-password">New password</label>
              <input id="new-password" type="password" className="input-control" autoComplete="new-password" minLength={8} value={passwords.new_password} onChange={(e) => setPasswords({ ...passwords, new_password: e.target.value })} aria-describedby="password-guidance" required />
              <small id="password-guidance" className="field-help">At least 8 characters, including a letter and a number.</small>
            </div>
            <div className="form-group">
              <label htmlFor="confirm-password">Confirm new password</label>
              <input id="confirm-password" type="password" className="input-control" autoComplete="new-password" minLength={8} value={passwords.confirm_password} onChange={(e) => setPasswords({ ...passwords, confirm_password: e.target.value })} required />
            </div>
            {passwordStatus.error && <div className="alert alert-danger" role="alert">{passwordStatus.error}</div>}
            {passwordStatus.success && <div className="alert alert-success" role="status">{passwordStatus.success}</div>}
            <button className="btn btn-primary" type="submit" disabled={passwordStatus.loading}>
              {passwordStatus.loading ? 'Updating...' : 'Change password'}
            </button>
          </form>
        </section>
      </div>
    </section>
  );
};
