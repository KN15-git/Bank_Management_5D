import React, { useState, useEffect, useRef } from 'react';
import { apiRequest } from '../services/api';

export const NotificationBell = () => {
  const [isOpen, setIsOpen] = useState(false);
  const [unreadCount, setUnreadCount] = useState(0);
  const [notifications, setNotifications] = useState([]);
  const [activeTab, setActiveTab] = useState('all');
  const [loading, setLoading] = useState(false);
  const dropdownRef = useRef(null);

  const fetchSummary = async () => {
    try {
      const data = await apiRequest('/api/notifications/summary');
      setUnreadCount(data.unread_count || 0);
    } catch (err) {
      // Silently fail if unauthenticated or offline
    }
  };

  const fetchFullNotifications = async (tab = activeTab) => {
    setLoading(true);
    try {
      let url = '/api/notifications?limit=25';
      if (tab === 'unread') url += '&unread_only=true';
      else if (tab === 'transaction') url += '&type=transaction';
      else if (tab === 'loan') url += '&type=loan';

      const data = await apiRequest(url);
      setNotifications(data.notifications || []);
      setUnreadCount(data.unread_count || 0);
    } catch (err) {
      console.warn('Could not load notifications:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSummary();
    const interval = setInterval(fetchSummary, 15000); // 15-second background sync
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (isOpen) {
      fetchFullNotifications(activeTab);
    }
  }, [isOpen, activeTab]);

  // Click outside listener
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleMarkAsRead = async (notifId, isRead) => {
    if (isRead) return;
    try {
      await apiRequest(`/api/notifications/${notifId}/read`, { method: 'PATCH' });
      setNotifications((prev) =>
        prev.map((n) => (n.id === notifId ? { ...n, is_read: true } : n))
      );
      setUnreadCount((c) => Math.max(0, c - 1));
    } catch (err) {
      console.error('Failed to mark read:', err);
    }
  };

  const handleMarkAllRead = async () => {
    try {
      await apiRequest('/api/notifications/mark-all-read', { method: 'POST' });
      setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })));
      setUnreadCount(0);
    } catch (err) {
      console.error('Failed to mark all read:', err);
    }
  };

  const getEventIcon = (eventType) => {
    switch (eventType) {
      case 'deposit': return '💰';
      case 'withdrawal': return '🏧';
      case 'transfer_out': return '📤';
      case 'transfer_in': return '📥';
      case 'loan_applied': return '📋';
      case 'loan_approved': return '✅';
      case 'loan_rejected': return '❌';
      default: return '🔔';
    }
  };

  return (
    <div className="notification-bell-container" ref={dropdownRef}>
      <button
        className="notification-bell-btn"
        onClick={() => setIsOpen(!isOpen)}
        title="View Notifications"
        aria-label="Notifications"
      >
        🔔
        {unreadCount > 0 && (
          <span className="notification-badge">{unreadCount > 99 ? '99+' : unreadCount}</span>
        )}
      </button>

      {isOpen && (
        <div className="notification-dropdown">
          <div className="notification-header">
            <h3>Notifications</h3>
            {unreadCount > 0 && (
              <button
                className="btn btn-xs btn-outline"
                onClick={handleMarkAllRead}
                style={{ fontSize: '0.75rem', padding: '2px 8px' }}
              >
                Mark all read
              </button>
            )}
          </div>

          <div className="notification-filter-tabs">
            {['all', 'unread', 'transaction', 'loan'].map((tab) => (
              <button
                key={tab}
                className={`notif-tab ${activeTab === tab ? 'active' : ''}`}
                onClick={() => setActiveTab(tab)}
              >
                {tab.charAt(0).toUpperCase() + tab.slice(1)}
              </button>
            ))}
          </div>

          <div className="notification-list">
            {loading ? (
              <div style={{ padding: '20px', textAlign: 'center', fontSize: '0.85rem' }}>
                Loading updates...
              </div>
            ) : notifications.length === 0 ? (
              <div className="notif-empty">No notifications in this view.</div>
            ) : (
              notifications.map((n) => (
                <div
                  key={n.id}
                  className={`notification-item ${!n.is_read ? 'unread' : ''}`}
                  onClick={() => handleMarkAsRead(n.id, n.is_read)}
                >
                  <div className="notif-icon">{getEventIcon(n.event_type)}</div>
                  <div className="notif-body">
                    <div className="notif-title-row">
                      <span className="notif-title">{n.title}</span>
                      <span className="notif-time">{n.created_at ? n.created_at.slice(0, 16) : ''}</span>
                    </div>
                    <p className="notif-message">{n.message}</p>
                    {n.reference_id && <span className="notif-ref">{n.reference_id}</span>}
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
};
