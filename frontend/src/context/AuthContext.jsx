import React, { createContext, useContext, useState, useEffect } from 'react';
import { apiRequest, setCsrfToken } from '../services/api';

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Load current user from /api/auth/me on app load
  useEffect(() => {
    const checkAuth = async () => {
      try {
        const data = await apiRequest('/api/auth/me');
        if (data.user) {
          setUser(data.user);
          if (data.csrf_token) {
            setCsrfToken(data.csrf_token);
          }
        }
      } catch (err) {
        // Unauthenticated is expected if no session cookie exists
        setUser(null);
      } finally {
        setLoading(false);
      }
    };

    checkAuth();

    // Listen to global 401 events to clear auth state
    const handleUnauthorized = () => {
      setUser(null);
    };
    window.addEventListener('auth:unauthorized', handleUnauthorized);
    return () => window.removeEventListener('auth:unauthorized', handleUnauthorized);
  }, []);

  const login = async (username, password) => {
    setError(null);
    try {
      const data = await apiRequest('/api/auth/login', {
        method: 'POST',
        body: JSON.stringify({ username, password }),
      });
      setUser(data.user);
      if (data.csrf_token) {
        setCsrfToken(data.csrf_token);
      }
      return data.user;
    } catch (err) {
      setError(err.message);
      throw err;
    }
  };

  const register = async (username, email, fullName, password) => {
    setError(null);
    try {
      const data = await apiRequest('/api/auth/register', {
        method: 'POST',
        body: JSON.stringify({
          username,
          email,
          full_name: fullName,
          password,
        }),
      });
      return data;
    } catch (err) {
      setError(err.message);
      throw err;
    }
  };

  const updateUser = (updatedUser) => {
    setUser(updatedUser);
  };

  const logout = async () => {
    try {
      await apiRequest('/api/auth/logout', { method: 'POST' });
    } catch (err) {
      console.warn('Logout API error:', err);
    } finally {
      setUser(null);
      setCsrfToken(null);
    }
  };

  return (
    <AuthContext.Provider value={{ user, loading, error, login, register, logout, updateUser }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => useContext(AuthContext);
