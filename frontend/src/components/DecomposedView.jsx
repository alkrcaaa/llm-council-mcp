import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import './DecomposedView.css';

/**
 * DecomposedView - Displays sub-question decomposition visualization.
 *
 * Shows the map-reduce pattern with:
 * - Complexity analysis result
 * - Sub-questions generated from the original question
 * - Individual answers for each sub-question (mini-council results)
 * - Merged final response from chairman
 *
 * @param {Object} props
 * @param {Array} props.subQuestions - Array of sub-questions generated
 * @param {Array} props.subResults - Array of sub-council results with best answers
 * @param {string} props.finalResponse - Merged final response from chairman
 * @param {string} props.chairmanModel - Model used for merging
 * @param {boolean} props.isDecomposing - Whether decomposition is in progress
 * @param {number} props.currentSubQuestion - Current sub-question index during streaming
 * @param {number} props.totalSubQuestions - Total number of sub-questions
 * @param {string} props.mergeStreaming - Partial merge response during streaming
 * @param {boolean} props.isMerging - Whether merge is in progress
 * @param {Object} props.complexityInfo - Complexity analysis result
 * @param {boolean} props.wasSkipped - Whether decomposition was skipped (question too simple)
 */
export default function DecomposedView({
  subQuestions = [],
  subResults = [],
  finalResponse = '',
  chairmanModel = '',
  isDecomposing = false,
  currentSubQuestion = -1,
  totalSubQuestions = 0,
  mergeStreaming = '',
  isMerging = false,
  complexityInfo = null,
  wasSkipped = false,
}) {
  const [expandedSections, setExpandedSections] = useState({
    subQuestions: true,
    subAnswers: true,
    merge: true,
  });

  const toggleSection = (section) => {
    setExpandedSections(prev => ({
      ...prev,
      [section]: !prev[section],
    }));
  };

  const getModelShortName = (model) => {
    if (!model) return 'Unknown';
    const parts = model.split('/');
    return parts[parts.length - 1];
  };

  const hasSubQuestions = subQuestions.length > 0;
  const hasSubResults = subResults.length > 0;
  const hasFinalResponse = finalResponse || mergeStreaming;
  const progressPercentage = totalSubQuestions > 0
    ? Math.round(((currentSubQuestion + 1) / totalSubQuestions) * 100)
    : 0;

  if (!hasSubQuestions && !isDecomposing && !wasSkipped) {
    return null;
  }

  // If decomposition was skipped, show a simple message
  if (wasSkipped) {
    return (
      <div className="decomposed-view skipped">
        <div className="decomposed-header">
          <div className="decomposed-title">
            <span className="decomposed-icon">&#9881;</span>
            <h4>Sub-Question Decomposition</h4>
          </div>
          <span className="skipped-badge">Skipped</span>
        </div>
        <div className="skip-notice">
          <p>Question was not complex enough for decomposition. Using standard council flow.</p>
          {complexityInfo && (
            <p className="skip-reason">Confidence: {(complexityInfo.confidence * 100).toFixed(0)}%</p>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="decomposed-view">
      <div className="decomposed-header">
        <div className="decomposed-title">
          <span className="decomposed-icon">&#9881;</span>
          <h4>Sub-Question Decomposition</h4>
        </div>
        <div className="decomposed-progress">
          {isDecomposing && !isMerging && totalSubQuestions > 0 && (
            <span className="progress-indicator">
              {currentSubQuestion + 1}/{totalSubQuestions} sub-questions
            </span>
          )}
          {isMerging && (
            <span className="progress-indicator merging">Merging...</span>
          )}
          {hasFinalResponse && !isMerging && (
            <span className="progress-indicator complete">Complete</span>
          )}
        </div>
      </div>

      {/* Progress bar during decomposition */}
      {isDecomposing && totalSubQuestions > 0 && !hasFinalResponse && (
        <div className="decomposition-progress-bar">
          <div
            className="progress-fill"
            style={{ width: `${progressPercentage}%` }}
          />
        </div>
      )}

      {/* Sub-Questions Section */}
      {hasSubQuestions && (
        <div className="decomposed-section">
          <div
            className="section-header"
            onClick={() => toggleSection('subQuestions')}
            role="button"
            tabIndex={0}
            aria-expanded={Boolean(expandedSections.subQuestions)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                toggleSection('subQuestions');
              }
            }}
          >
            <div className="section-info">
              <span className="section-number">1</span>
              <span className="section-name">Sub-Questions ({subQuestions.length})</span>
            </div>
            <span className={`toggle-icon ${expandedSections.subQuestions ? 'expanded' : 'collapsed'}`}>
              &#9660;
            </span>
          </div>
          {expandedSections.subQuestions && (
            <div className="section-content">
              <div className="sub-questions-list">
                {subQuestions.map((sq, index) => (
                  <div
                    key={index}
                    className={`sub-question-card ${
                      currentSubQuestion === index ? 'active' : ''
                    } ${
                      subResults[index] ? 'answered' : ''
                    }`}
                  >
                    <div className="sub-question-header">
                      <span className="sub-question-number">Q{index + 1}</span>
                      {subResults[index] && (
                        <span className="answered-badge">&#10003;</span>
                      )}
                      {currentSubQuestion === index && !subResults[index] && (
                        <span className="processing-badge">Processing...</span>
                      )}
                    </div>
                    <div className="sub-question-text">{sq}</div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Sub-Answers Section */}
      {hasSubResults && (
        <div className="decomposed-section">
          <div
            className="section-header"
            onClick={() => toggleSection('subAnswers')}
            role="button"
            tabIndex={0}
            aria-expanded={Boolean(expandedSections.subAnswers)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                toggleSection('subAnswers');
              }
            }}
          >
            <div className="section-info">
              <span className="section-number">2</span>
              <span className="section-name">Sub-Answers ({subResults.length})</span>
            </div>
            <span className={`toggle-icon ${expandedSections.subAnswers ? 'expanded' : 'collapsed'}`}>
              &#9660;
            </span>
          </div>
          {expandedSections.subAnswers && (
            <div className="section-content">
              <div className="sub-answers-list">
                {subResults.map((result, index) => (
                  <div key={index} className="sub-answer-card">
                    <div className="sub-answer-header">
                      <div className="sub-answer-info">
                        <span className="sub-answer-number">A{index + 1}</span>
                        <span className="sub-answer-question">
                          {result.sub_question || subQuestions[index] || `Sub-question ${index + 1}`}
                        </span>
                      </div>
                      <span className="sub-answer-model">
                        {getModelShortName(result.best_model)}
                      </span>
                    </div>
                    <div className="sub-answer-content markdown-content">
                      <ReactMarkdown>{result.best_answer || 'No answer available'}</ReactMarkdown>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Merged Response Section */}
      {(hasFinalResponse || isMerging) && (
        <div className="decomposed-section merge-section">
          <div
            className="section-header merge-header"
            onClick={() => toggleSection('merge')}
            role="button"
            tabIndex={0}
            aria-expanded={Boolean(expandedSections.merge)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                toggleSection('merge');
              }
            }}
          >
            <div className="section-info">
              <span className="section-number merge">&#8721;</span>
              <span className="section-name">Merged Response</span>
            </div>
            {chairmanModel && (
              <span className="merge-model">
                by {getModelShortName(chairmanModel)}
              </span>
            )}
            <span className={`toggle-icon ${expandedSections.merge ? 'expanded' : 'collapsed'}`}>
              &#9660;
            </span>
          </div>
          {expandedSections.merge && (
            <div className="section-content merge-content">
              <div className={`merge-text markdown-content ${isMerging ? 'streaming' : ''}`}>
                <ReactMarkdown>{finalResponse || mergeStreaming}</ReactMarkdown>
                {isMerging && <span className="streaming-cursor"></span>}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/**
 * DecompositionBadge - Small badge for Stage 3 header showing decomposition was applied.
 */
export function DecompositionBadge({ subQuestionCount }) {
  return (
    <span className="decomposition-badge-small">
      <span className="decomposition-badge-icon">&#9881;</span>
      <span>{subQuestionCount} Sub-Q</span>
    </span>
  );
}

/**
 * DecompositionToggle - Toggle control for enabling/disabling decomposition mode.
 */
export function DecompositionToggle({ enabled, onChange }) {
  return (
    <div className="decomposition-toggle-control">
      <label className="toggle-label">
        <span className="toggle-text">Sub-Question Decomposition</span>
        <div
          className={`toggle-switch ${enabled ? 'enabled' : ''}`}
          onClick={() => onChange(!enabled)}
        >
          <div className="toggle-slider"></div>
        </div>
      </label>
    </div>
  );
}
