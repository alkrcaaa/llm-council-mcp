import { useEffect, useRef, useState } from 'react';
import { api } from '../api';
import { ACCEPT, classify, formatSize } from '../attachments';
import './Attachments.css';

const KIND_TAG = { image: 'IMG', pdf: 'PDF', text: 'TXT' };

// The attach control. A hidden file input keeps the browser's own picker.
export function AttachButton({ onFiles, disabled = false }) {
  const inputRef = useRef(null);
  return (
    <>
      <input
        ref={inputRef}
        type="file"
        multiple
        accept={ACCEPT}
        className="attach-file-input"
        onChange={(e) => {
          onFiles(e.target.files);
          e.target.value = '';
        }}
      />
      <button
        type="button"
        className="attach-btn"
        disabled={disabled}
        onClick={() => inputRef.current?.click()}
        title="Attach images, PDF or text files (you can also drop or paste)"
        aria-label="Attach files"
      >
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48" />
        </svg>
      </button>
    </>
  );
}

// Strip of files chosen for the next message, shown above the text box.
export function AttachmentTray({ items, error, onRemove }) {
  if (items.length === 0 && !error) return null;
  return (
    <div className="attach-tray">
      {items.length > 0 && (
        <div className="attach-tray-items">
          {items.map(({ key, file, previewUrl }) => (
            <div className={`attach-item ${previewUrl ? 'has-thumb' : ''}`} key={key}>
              {previewUrl ? (
                <img className="attach-thumb" src={previewUrl} alt={file.name} />
              ) : (
                <span className="attach-kind">{KIND_TAG[classify(file)]}</span>
              )}
              <span className="attach-name" title={file.name}>{file.name}</span>
              <span className="attach-size">{formatSize(file.size)}</span>
              <button type="button" className="attach-remove" onClick={() => onRemove(key)} title="Remove">
                ×
              </button>
            </div>
          ))}
        </div>
      )}
      {error && <div className="attach-error">{error}</div>}
    </div>
  );
}

// Thumbnails need the bearer token, which an <img src> cannot send, so images are fetched as blobs.
function AuthImage({ conversationId, attachment }) {
  const [url, setUrl] = useState(attachment.previewUrl || null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    if (attachment.previewUrl || !attachment.id || !conversationId) return undefined;
    let revoked = false;
    let objectUrl = null;
    api
      .getAttachmentBlob(conversationId, attachment.id)
      .then((blob) => {
        if (revoked) return;
        objectUrl = URL.createObjectURL(blob);
        setUrl(objectUrl);
      })
      .catch(() => !revoked && setFailed(true));
    return () => {
      revoked = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [conversationId, attachment.id, attachment.previewUrl]);

  if (failed) return <span className="attach-chip"><span className="attach-kind">IMG</span>{attachment.name}</span>;
  if (!url) return <span className="attach-thumb-loading" aria-label={attachment.name} />;
  return (
    <a href={url} target="_blank" rel="noreferrer" className="attach-bubble-thumb-link" title={attachment.name}>
      <img className="attach-bubble-thumb" src={url} alt={attachment.name} />
    </a>
  );
}

// Attachments of a sent message, shown inside the bubble.
export function MessageAttachments({ attachments, conversationId }) {
  if (!Array.isArray(attachments) || attachments.length === 0) return null;
  return (
    <div className="attach-bubble">
      {attachments.map((a, idx) =>
        a.kind === 'image' ? (
          <AuthImage key={a.id || idx} conversationId={conversationId} attachment={a} />
        ) : (
          <span className="attach-chip" key={a.id || idx} title={a.name}>
            <span className="attach-kind">{KIND_TAG[a.kind] || 'FILE'}</span>
            <span className="attach-name">{a.name}</span>
          </span>
        )
      )}
    </div>
  );
}
