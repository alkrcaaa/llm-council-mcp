import { useEffect } from 'react';
import './DeleteConfirmModal.css';

/**
 * DeleteConfirmModal - In-app confirmation dialog for deleting conversations.
 *
 * @param {Object} props
 * @param {Object} props.conversation - The conversation being deleted ({ id, title, message_count })
 * @param {function} props.onConfirm - Callback to execute deletion
 * @param {function} props.onCancel - Callback to dismiss modal
 * @param {boolean} props.isDeleting - Whether deletion is in flight
 */
export default function DeleteConfirmModal({
  conversation,
  onConfirm,
  onCancel,
  isDeleting = false,
}) {
  // Close on Escape
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape' && !isDeleting) {
        onCancel();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onCancel, isDeleting]);

  if (!conversation) return null;

  return (
    <>
      <div className="delete-modal-overlay" onClick={!isDeleting ? onCancel : undefined} />
      <div className="delete-modal" role="dialog" aria-modal="true" aria-labelledby="delete-dialog-title">
        <div className="delete-modal-header">
          <div className="delete-modal-icon-wrap">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="3 6 5 6 21 6"></polyline>
              <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
              <line x1="10" y1="11" x2="10" y2="17"></line>
              <line x1="14" y1="11" x2="14" y2="17"></line>
            </svg>
          </div>
          <div className="delete-modal-title-group">
            <h3 id="delete-dialog-title">Delete Conversation</h3>
            <span className="delete-modal-subtitle">Irreversible Action</span>
          </div>
          <button
            className="delete-modal-close"
            onClick={onCancel}
            disabled={isDeleting}
            aria-label="Close"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <line x1="18" y1="6" x2="6" y2="18"></line>
              <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
          </button>
        </div>

        <div className="delete-modal-body">
          <p className="delete-modal-desc">
            Are you sure you want to permanently delete this council deliberation and all associated deliberation records?
          </p>
          <div className="delete-target-preview">
            <span className="delete-target-glyph">◈</span>
            <span className="delete-target-title">
              {conversation.title || 'Untitled Conversation'}
            </span>
            {conversation.message_count !== undefined && (
              <span className="delete-target-meta">
                {conversation.message_count} {conversation.message_count === 1 ? 'message' : 'messages'}
              </span>
            )}
          </div>
        </div>

        <div className="delete-modal-actions">
          <button
            type="button"
            className="delete-btn-cancel"
            onClick={onCancel}
            disabled={isDeleting}
          >
            Cancel
          </button>
          <button
            type="button"
            className="delete-btn-confirm"
            onClick={onConfirm}
            disabled={isDeleting}
            autoFocus
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="3 6 5 6 21 6"></polyline>
              <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
            </svg>
            {isDeleting ? 'Deleting...' : 'Delete Conversation'}
          </button>
        </div>
      </div>
    </>
  );
}
