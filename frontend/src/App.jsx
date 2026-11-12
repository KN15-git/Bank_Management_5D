import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { Navbar } from './components/Navbar';
import { ProtectedRoute } from './components/ProtectedRoute';
import { LoginPage } from './pages/LoginPage';
import { RegisterPage } from './pages/RegisterPage';
import { CustomerDashboard } from './pages/CustomerDashboard';
import { AccountDetailPage } from './pages/AccountDetailPage';
import { EmployeeDashboard } from './pages/EmployeeDashboard';
import { AdminDashboard } from './pages/AdminDashboard';
import { UnauthorizedPage } from './pages/UnauthorizedPage';
import { ProfileSettingsPage } from './pages/ProfileSettingsPage';
import { useAuth } from './context/AuthContext';
import './styles/App.css';

const HomeRedirect = () => {
  const { user, loading } = useAuth();
  if (loading) {
    return <div className="center-container"><div className="spinner"></div></div>;
  }
  if (!user) return <Navigate to="/login" replace />;
  if (user.role === 'customer') return <Navigate to="/customer" replace />;
  if (user.role === 'employee') return <Navigate to="/employee" replace />;
  if (user.role === 'admin') return <Navigate to="/admin" replace />;
  return <Navigate to="/login" replace />;
};

export const App = () => {
  return (
    <div className="app-container">
      <Navbar />
      <main className="main-content">
        <Routes>
          <Route path="/" element={<HomeRedirect />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route path="/unauthorized" element={<UnauthorizedPage />} />
          <Route
            path="/profile"
            element={
              <ProtectedRoute roles={['customer', 'employee', 'admin']}>
                <ProfileSettingsPage />
              </ProtectedRoute>
            }
          />

          {/* Customer Routes */}
          <Route
            path="/customer"
            element={
              <ProtectedRoute roles={['customer']}>
                <CustomerDashboard />
              </ProtectedRoute>
            }
          />
          <Route
            path="/accounts/:id"
            element={
              <ProtectedRoute roles={['customer', 'employee', 'admin']}>
                <AccountDetailPage />
              </ProtectedRoute>
            }
          />

          {/* Employee & Admin Routes */}
          <Route
            path="/employee"
            element={
              <ProtectedRoute roles={['employee', 'admin']}>
                <EmployeeDashboard />
              </ProtectedRoute>
            }
          />

          {/* Admin Exclusive Routes */}
          <Route
            path="/admin"
            element={
              <ProtectedRoute roles={['admin']}>
                <AdminDashboard />
              </ProtectedRoute>
            }
          />

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  );
};
