/**
 * API Service wrapper for PES Bank Management System.
 * Handles fetch requests with credentials, CSRF token header, and JSON error parsing.
 */
let csrfToken = null;

export const setCsrfToken = (token) => {
  csrfToken = token;
};

export const getCsrfToken = () => csrfToken;

export const fetchCsrfToken = async () => {
  try {
    const res = await fetch('/api/auth/csrf', { credentials: 'include' });
    if (res.ok) {
      const data = await res.json();
      csrfToken = data.csrf_token;
      return csrfToken;
    }
  } catch (err) {
    console.warn('Could not fetch CSRF token:', err);
  }
  return null;
};

export const apiRequest = async (url, options = {}) => {
  const headers = {
    'Content-Type': 'application/json',
    ...(options.headers || {}),
  };

  const method = (options.method || 'GET').toUpperCase();
  if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(method)) {
    if (!csrfToken) {
      await fetchCsrfToken();
    }
    if (csrfToken) {
      headers['X-CSRF-Token'] = csrfToken;
    }
  }

  const response = await fetch(url, {
    ...options,
    headers,
    credentials: 'include', // Ensures Flask session cookies are sent
  });

  if (response.status === 401 && !url.includes('/api/auth/login') && !url.includes('/api/auth/me')) {
    // Globally handle unauthenticated state
    window.dispatchEvent(new CustomEvent('auth:unauthorized'));
  }

  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    const errorMsg = data.error || `Request failed with status ${response.status}`;
    const error = new Error(errorMsg);
    error.status = response.status;
    error.data = data;
    throw error;
  }

  return data;
};
