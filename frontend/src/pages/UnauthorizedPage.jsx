import React from 'react';
import { Link } from 'react-router-dom';

export const UnauthorizedPage = () => {
  return (
    <div className="center-container error-page">
      <div className="error-card">
        <h1>403</h1>
        <h2>Access Denied / Not Authorized</h2>
        <p>Your current user role does not possess the permissions required to view or modify this resource.</p>
        <div className="error-actions">
          <Link to="/" className="btn btn-primary">Return to Home</Link>
          <Link to="/login" className="btn btn-outline">Switch Account</Link>
        </div>
      </div>
    </div>
  );
};
