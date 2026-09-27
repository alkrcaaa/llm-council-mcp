import React, { useState, useEffect } from 'react';
import { api } from '../api';
import './AccountModal.css';

export default function AccountModal({ isOpen, onClose, currentUser = 'admin' }) {
  const [oldPassword, setOldPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);

  useEffect(() => {
    if (isOpen) {
      setOldPassword('');
      setNewPassword('');
      setConfirmPassword('');
      setError(null);
      setSuccess(null);
    }
  }, [isOpen]);

  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setSuccess(null);

    if (!oldPassword) {
      setError('Please enter your current password.');
      return;
    }

    if (newPassword.length < 6) {
      setError('New password must be at least 6 characters.');
      return;
    }

    if (newPassword !== confirmPassword) {
      setError('New passwords do not match.');
      return;
    }

    setLoading(true);
    try {
      await api.changePassword(oldPassword, newPassword);
      setSuccess('Password updated successfully! New session token saved.');
      setOldPassword('');
      setNewPassword('');
      setConfirmPassword('');
      setTimeout(() => {
        onClose();
      }, 1800);
    } catch (err) {
      setError(err.message || 'An error occurred while updating the password.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="account-modal-backdrop" onClick={onClose}>
      <div
        className="account-modal-card"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-labelledby="account-modal-title"
        aria-modal="true"
      >
        <div className="account-modal-header">
          <div className="account-modal-title-row">
            <div>
              <h2 id="account-modal-title">Account & Password Management</h2>
              <p className="account-subtitle">Active user: <strong>{currentUser}</strong></p>
            </div>
          </div>
          <button className="account-close-btn" onClick={onClose} title="Close (Esc)">✕</button>
        </div>

        {error && (
          <div className="account-alert account-alert-error" role="alert">
            <span>{error}</span>
          </div>
        )}

        {success && (
          <div className="account-alert account-alert-success" role="status">
            <span>{success}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="account-form">
          <div className="account-form-group">
            <label htmlFor="old-password">Current Password</label>
            <input
              id="old-password"
              type="password"
              value={oldPassword}
              onChange={(e) => setOldPassword(e.target.value)}
              placeholder="Enter current password"
              autoComplete="current-password"
              required
              disabled={loading}
            />
          </div>

          <div className="account-form-group">
            <label htmlFor="new-password">New Password</label>
            <input
              id="new-password"
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              placeholder="At least 6 characters"
              autoComplete="new-password"
              required
              disabled={loading}
            />
          </div>

          <div className="account-form-group">
            <label htmlFor="confirm-password">Confirm New Password</label>
            <input
              id="confirm-password"
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              placeholder="Re-enter new password"
              autoComplete="new-password"
              required
              disabled={loading}
            />
          </div>

          <div className="account-modal-actions">
            <button
              type="button"
              className="account-btn-cancel"
              onClick={onClose}
              disabled={loading}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="account-btn-submit"
              disabled={loading}
            >
              {loading ? 'Updating...' : 'Update Password'}
            </button>
          </div>
        </form>

        <div className="account-modal-footer">
          <span className="footer-hint">
            Your new password is encrypted and securely stored using PBKDF2 hashing.
          </span>
        </div>
      </div>
    </div>
  );
}
