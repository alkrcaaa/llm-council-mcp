import { useState } from 'react';
import SafeMarkdown from './SafeMarkdown.jsx';
import './AdversaryReview.css';

/**
 * AdversaryReview - Displays the adversarial validation process and results.
 *
 * Shows the devil's advocate review including:
 * - Adversary critique of the synthesis
 * - Severity level of any issues found
 * - Chairman revision if issues were significant
 * - Final validated/revised response
 *
 * @param {Object} props
 * @param {string} props.critique - The adversary's critical review
 * @param {boolean} props.hasIssues - Whether issues were found
 * @param {string} props.severity - Severity level: critical, major, minor, none
 * @param {boolean} props.revised - Whether a revision was made
 * @param {string} props.revision - The revised response (if applicable)
 * @param {string} props.adversaryModel - The adversary model used
 * @param {boolean} props.isReviewing - Whether adversary is currently reviewing
 * @param {boolean} props.isRevising - Whether chairman is currently revising
 * @param {string} props.streamingCritique - Partial critique during streaming
 * @param {string} props.streamingRevision - Partial revision during streaming
 */
export default function AdversaryReview({
  critique = '',
  hasIssues = false,
  severity = 'none',
  revised = false,
  revision = '',
  adversaryModel = '',
  isReviewing = false,
  isRevising = false,
  streamingCritique = '',
  streamingRevision = '',
}) {
  const [expanded, setExpanded] = useState(false);

  // Determine display values
  const displayCritique = critique || streamingCritique;
  const displayRevision = revision || streamingRevision;

  // Don't render if nothing to show
  if (!displayCritique && !isReviewing && !hasIssues) {
    return null;
  }

  // Get severity display info
  const severityInfo = SEVERITY_INFO[severity] || SEVERITY_INFO.none;

  return (
    <div className={`adversary-review ${severity !== 'none' ? 'has-issues' : 'no-issues'}`}>
      <div className="adversary-header">
        <div className="adversary-title">
          <span className="adversary-icon">&#9888;</span>
          <h4>Adversarial Validation</h4>
          {isReviewing && (
            <span className="adversary-status reviewing">
              <span className="spinner-small"></span>
              Reviewing...
            </span>
          )}
          {isRevising && (
            <span className="adversary-status revising">
              <span className="spinner-small"></span>
              Revising...
            </span>
          )}
          {!isReviewing && !isRevising && (
            <span className={`severity-badge ${severity}`}>
              {severityInfo.label}
            </span>
          )}
        </div>
        <button
          className="toggle-btn"
          onClick={() => setExpanded(!expanded)}
          aria-label={expanded ? 'Collapse' : 'Expand'}
        >
          {expanded ? '▼' : '▶'}
        </button>
      </div>

      {/* Summary line - always visible */}
      <div className="adversary-summary">
        {isReviewing ? (
          <span>Devil's advocate reviewing synthesis...</span>
        ) : isRevising ? (
          <span>Chairman revising based on critique...</span>
        ) : hasIssues ? (
          <span>
            <strong>{severityInfo.label}</strong> issues found
            {revised && ' — response was revised'}
          </span>
        ) : (
          <span>No significant issues found — validation passed</span>
        )}
      </div>

      {/* Expanded content */}
      {expanded && (
        <div className="adversary-content">
          {/* Adversary Model */}
          {adversaryModel && (
            <div className="adversary-model-info">
              <span className="model-label">Adversary:</span>
              <span className="model-name">{adversaryModel.split('/')[1] || adversaryModel}</span>
            </div>
          )}

          {/* Critique Section */}
          <div className="critique-section">
            <div className="section-title">
              <span className="section-icon">&#128269;</span>
              Critical Review
            </div>
            <div className={`critique-text markdown-content ${isReviewing ? 'streaming' : ''}`}>
              <SafeMarkdown>{displayCritique || 'Analyzing...'}</SafeMarkdown>
              {isReviewing && <span className="streaming-cursor"></span>}
            </div>
          </div>

          {/* Revision Section (only if issues found and revised) */}
          {(displayRevision || isRevising) && (
            <div className="revision-section">
              <div className="section-title">
                <span className="section-icon">&#9998;</span>
                Chairman Revision
              </div>
              <div className={`revision-text markdown-content ${isRevising ? 'streaming' : ''}`}>
                <SafeMarkdown>{displayRevision || 'Revising...'}</SafeMarkdown>
                {isRevising && <span className="streaming-cursor"></span>}
              </div>
            </div>
          )}

          {/* Result indicator */}
          {!isReviewing && !isRevising && (
            <div className={`result-indicator ${revised ? 'revised' : hasIssues ? 'issues-noted' : 'passed'}`}>
              <span className="result-icon">
                {revised ? '&#10003;' : hasIssues ? '&#9888;' : '&#10003;'}
              </span>
              <span className="result-text">
                {revised
                  ? 'Response was revised to address issues'
                  : hasIssues
                    ? 'Minor issues noted (no revision needed)'
                    : 'Validation passed — no issues found'}
              </span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/**
 * AdversaryBadge - Small badge indicator for adversary validation status
 */
export function AdversaryBadge({ hasIssues, severity, revised }) {
  if (severity === 'none' && !hasIssues) {
    return (
      <span className="adversary-badge-small passed" title="Adversarial validation passed">
        AV &#10003;
      </span>
    );
  }

  if (revised) {
    return (
      <span className="adversary-badge-small revised" title="Revised after adversarial review">
        AV R
      </span>
    );
  }

  return (
    <span className={`adversary-badge-small ${severity}`} title={`${severity} issues found`}>
      AV &#9888;
    </span>
  );
}

/**
 * AdversaryToggle - Toggle control for enabling adversary mode
 */
export function AdversaryToggle({ enabled, onChange }) {
  return (
    <div className="adversary-toggle-control">
      <label className="toggle-label">
        <span className="toggle-text">Adversarial Validation</span>
        <div className={`toggle-switch ${enabled ? 'enabled' : ''}`} onClick={() => onChange(!enabled)}>
          <div className="toggle-slider"></div>
        </div>
      </label>
    </div>
  );
}

// Severity display info
const SEVERITY_INFO = {
  critical: {
    label: 'Critical',
    description: 'Serious errors that must be corrected',
    color: '#dc2626',
  },
  major: {
    label: 'Major',
    description: 'Significant issues that should be addressed',
    color: '#ea580c',
  },
  minor: {
    label: 'Minor',
    description: 'Small improvements possible',
    color: '#ca8a04',
  },
  none: {
    label: 'Passed',
    description: 'No issues found',
    color: '#16a34a',
  },
};
