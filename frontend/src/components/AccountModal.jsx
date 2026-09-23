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
      setError('Lütfen mevcut şifrenizi girin.');
      return;
    }

    if (newPassword.length < 6) {
      setError('Yeni şifre en az 6 karakter olmalıdır.');
      return;
    }

    if (newPassword !== confirmPassword) {
      setError('Yeni şifreler birbiriyle eşleşmiyor.');
      return;
    }

    setLoading(true);
    try {
      await api.changePassword(oldPassword, newPassword);
      setSuccess('Şifreniz başarıyla güncellendi! Yeni oturum anahtarınız kaydedildi.');
      setOldPassword('');
      setNewPassword('');
      setConfirmPassword('');
      setTimeout(() => {
        onClose();
      }, 1800);
    } catch (err) {
      setError(err.message || 'Şifre güncellenirken bir hata oluştu.');
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
              <h2 id="account-modal-title">Hesap & Şifre Yönetimi</h2>
              <p className="account-subtitle">Aktif kullanıcı: <strong>{currentUser}</strong></p>
            </div>
          </div>
          <button className="account-close-btn" onClick={onClose} title="Kapat (Esc)">✕</button>
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
            <label htmlFor="old-password">Mevcut Şifre</label>
            <input
              id="old-password"
              type="password"
              value={oldPassword}
              onChange={(e) => setOldPassword(e.target.value)}
              placeholder="Mevcut şifrenizi girin"
              autoComplete="current-password"
              required
              disabled={loading}
            />
          </div>

          <div className="account-form-group">
            <label htmlFor="new-password">Yeni Şifre</label>
            <input
              id="new-password"
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              placeholder="En az 6 karakter"
              autoComplete="new-password"
              required
              disabled={loading}
            />
          </div>

          <div className="account-form-group">
            <label htmlFor="confirm-password">Yeni Şifre (Tekrar)</label>
            <input
              id="confirm-password"
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              placeholder="Yeni şifrenizi tekrar girin"
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
              İptal
            </button>
            <button
              type="submit"
              className="account-btn-submit"
              disabled={loading}
            >
              {loading ? 'Güncelleniyor...' : 'Şifreyi Güncelle'}
            </button>
          </div>
        </form>

        <div className="account-modal-footer">
          <span className="footer-hint">
            Yeni şifreniz kalıcı depolama birimine (data volume) güvenli PBKDF2 hash ile kaydedilir.
          </span>
        </div>
      </div>
    </div>
  );
}
