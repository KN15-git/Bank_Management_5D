import React from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export const Navbar = () => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  return (
    <nav className="navbar">
      <div className="nav-container">
        <Link to="/" className="nav-logo">
          🏦 PES Bank
        </Link>
        <div className="nav-links">
          {user ? (
            <>
              {user.role === 'customer' && (
                <Link to="/customer" className="nav-item">My Accounts</Link>
              )}
              {(user.role === 'employee' || user.role === 'admin') && (
                <Link to="/employee" className="nav-item">Manage Accounts</Link>
              )}
              {user.role === 'admin' && (
                <Link to="/admin" className="nav-item">User Management</Link>
              )}
              <div className="user-badge">
                <span className="user-name">{user.full_name}</span>
                <span className={`role-pill role-${user.role}`}>{user.role}</span>
              </div>
              <button onClick={handleLogout} className="btn btn-outline btn-sm">
                Logout
              </button>
            </>
          ) : (
            <>
              <Link to="/login" className="nav-item">Login</Link>
              <Link to="/register" className="btn btn-primary btn-sm">Register</Link>
            </>
          )}
        </div>
      </div>
    </nav>
  );
};
