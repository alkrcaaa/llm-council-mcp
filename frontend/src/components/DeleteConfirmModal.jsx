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
        <div className="delete-modal-content">
          <h3 id="delete-dialog-title" className="delete-modal-title">Delete chat?</h3>
          <p className="delete-modal-desc">
            This will permanently delete <strong>"{conversation.title || 'New Conversation'}"</strong> and its entire message history.
          </p>
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
              {isDeleting ? 'Deleting...' : 'Delete'}
            </button>
          </div>
        </div>
      </div>
    </>
  );
}
