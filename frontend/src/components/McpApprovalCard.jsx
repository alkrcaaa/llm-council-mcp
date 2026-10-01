import { useEffect, useState } from 'react';
import { api } from '../api';
import './McpApprovalCard.css';

// Mirrors APPROVAL_TIMEOUT_S in backend/tools/mcp_client.py; past it the call is denied server-side.
const APPROVAL_WINDOW_MS = 120000;

function McpApprovalCard({ approval }) {
  const [status, setStatus] = useState('pending'); // pending | sending | approved | denied | expired | failed
  const [error, setError] = useState('');
  const [now, setNow] = useState(() => Date.now());

  const remaining = Math.max(0, Math.ceil((approval.received_at + APPROVAL_WINDOW_MS - now) / 1000));
  const live = status === 'pending' || status === 'sending';

  useEffect(() => {
    if (!live) return undefined;
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, [live]);

  const timedOut = live && remaining === 0;
  const shown = timedOut ? 'expired' : status;

  const decide = async (approve) => {
    setStatus('sending');
    setError('');
    try {
      await api.decideMcpApproval(approval.approval_id, approve);
      setStatus(approve ? 'approved' : 'denied');
    } catch (e) {
      if (e.status === 404) {
        setStatus('expired'); // already decided, timed out, or the backend restarted
      } else {
        setStatus('pending');
        setError(e.message);
      }
    }
  };

  const args =
    typeof approval.arguments === 'string'
      ? approval.arguments
      : JSON.stringify(approval.arguments ?? {}, null, 2);

  return (
    <div className={`mcp-approval ${shown}`}>
      <div className="mcp-approval-head">
        <span className="mcp-approval-label">Approval needed</span>
        <span className="mcp-approval-model">{approval.model}</span>
        {live && <span className="mcp-approval-timer">{remaining}s</span>}
      </div>
      <div className="mcp-approval-body">
        <span className="mcp-approval-tool">{approval.tool}</span>
        <pre className="mcp-approval-args">{args}</pre>
      </div>
      {live && !timedOut ? (
        <div className="mcp-approval-actions">
          <button type="button" className="mcp-approval-btn approve" disabled={status === 'sending'} onClick={() => decide(true)}>
            Approve
          </button>
          <button type="button" className="mcp-approval-btn" disabled={status === 'sending'} onClick={() => decide(false)}>
            Deny
          </button>
          {error && <span className="mcp-approval-error">{error}</span>}
        </div>
      ) : (
        <div className="mcp-approval-result">
          {shown === 'approved' && 'Approved. The call is running.'}
          {shown === 'denied' && 'Denied. The model was told you declined.'}
          {shown === 'expired' && 'Expired. The call was denied automatically.'}
        </div>
      )}
    </div>
  );
}

export default McpApprovalCard;
