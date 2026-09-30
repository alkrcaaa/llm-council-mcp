import { useState } from 'react';
import SafeMarkdown from './SafeMarkdown.jsx';
import './RefinementView.css';

/**
 * RefinementView - Displays the iterative refinement process and results.
 *
 * Shows the critique-and-revise cycles including:
 * - Each iteration with critiques from council models
 * - Chairman revisions based on feedback
 * - Convergence status and final refined response
 *
 * @param {Object} props
 * @param {Array} props.iterations - Array of iteration objects
 *   Each iteration has: { iteration, draft_before, critiques, revision, substantive_critique_count }
 * @param {string} props.finalResponse - The final refined response text
 * @param {number} props.totalIterations - Total number of iterations performed
 * @param {boolean} props.converged - Whether refinement converged (vs hit max)
 * @param {Object} props.totalCost - Total cost of refinement
 * @param {boolean} props.isRefining - Whether refinement is in progress
 * @param {number} props.currentIteration - Current iteration being processed
 * @param {Array} props.streamingCritiques - Critiques being collected for current iteration
 * @param {string} props.streamingRevision - Partial revision text during streaming
 * @param {number} props.maxIterations - Maximum iterations configured
 */
export default function RefinementView({
  iterations = [],
  finalResponse = '',
  totalIterations = 0,
  converged = false,
  totalCost = null,
  isRefining = false,
  currentIteration = 0,
  streamingCritiques = [],
  streamingRevision = '',
  maxIterations = 2,
}) {
  const [expandedIterations, setExpandedIterations] = useState({});
  const [showAllCritiques, setShowAllCritiques] = useState({});

  const toggleIteration = (iteration) => {
    setExpandedIterations((prev) => ({
      ...prev,
      [iteration]: !prev[iteration],
    }));
  };

  const toggleCritiques = (iteration) => {
    setShowAllCritiques((prev) => ({
      ...prev,
      [iteration]: !prev[iteration],
    }));
  };

  // Don't render if no iterations and not refining
  if (iterations.length === 0 && !isRefining) {
    return null;
  }

  return (
    <div className="refinement-view">
      <div className="refinement-header">
        <h4 className="refinement-title">
          <span className="refinement-icon">&#8635;</span>
          Iterative Refinement
        </h4>
        {isRefining ? (
          <span className="refinement-status refining">
            <span className="spinner-small"></span>
            Iteration {currentIteration} of {maxIterations}
          </span>
        ) : (
          <span className={`refinement-status ${converged ? 'converged' : 'completed'}`}>
            {converged ? 'Converged' : 'Completed'} ({totalIterations} iteration{totalIterations !== 1 ? 's' : ''})
          </span>
        )}
      </div>

      {/* Progress indicator */}
      {isRefining && (
        <div className="refinement-progress">
          <div className="progress-steps">
            {Array.from({ length: maxIterations }, (_, i) => (
              <div
                key={i}
                className={`progress-step ${i + 1 < currentIteration ? 'completed' : ''} ${i + 1 === currentIteration ? 'active' : ''}`}
              >
                <div className="step-dot">
                  {i + 1 < currentIteration ? '✓' : i + 1}
                </div>
                <span className="step-label">
                  {i + 1 === currentIteration && isRefining ? 'In Progress' : `Iteration ${i + 1}`}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Iterations list */}
      <div className="iterations-list">
        {iterations.map((iter) => (
          <div key={iter.iteration} className="iteration-card">
            <button
              className={`iteration-header ${expandedIterations[iter.iteration] ? 'expanded' : ''}`}
              onClick={() => toggleIteration(iter.iteration)}
            >
              <span className="iteration-number">Iteration {iter.iteration}</span>
              <span className="iteration-summary">
                <span className={`critique-count ${iter.substantive_critique_count > 0 ? 'has-critiques' : 'no-critiques'}`}>
                  {iter.substantive_critique_count} substantive critique{iter.substantive_critique_count !== 1 ? 's' : ''}
                </span>
                {iter.stopped && (
                  <span className="converged-badge">Converged</span>
                )}
              </span>
              <span className="expand-icon">
                {expandedIterations[iter.iteration] ? '▼' : '▶'}
              </span>
            </button>

            {expandedIterations[iter.iteration] && (
              <div className="iteration-content">
                {/* Critiques section */}
                <div className="critiques-section">
                  <div className="section-header">
                    <span className="section-title">Council Critiques</span>
                    {iter.critiques && iter.critiques.length > 2 && (
                      <button
                        className="toggle-all-btn"
                        onClick={() => toggleCritiques(iter.iteration)}
                      >
                        {showAllCritiques[iter.iteration] ? 'Show Less' : `Show All (${iter.critiques.length})`}
                      </button>
                    )}
                  </div>
                  <div className="critiques-list">
                    {(iter.critiques || [])
                      .slice(0, showAllCritiques[iter.iteration] ? undefined : 2)
                      .map((critique, idx) => (
                        <div
                          key={idx}
                          className={`critique-item ${critique.is_substantive ? 'substantive' : 'non-substantive'}`}
                        >
                          <div className="critique-header">
                            <span className="critique-model">
                              {critique.model?.split('/')[1] || critique.model}
                            </span>
                            <span className={`substantive-badge ${critique.is_substantive ? 'yes' : 'no'}`}>
                              {critique.is_substantive ? 'Substantive' : 'Non-substantive'}
                            </span>
                          </div>
                          <div className="critique-text markdown-content">
                            <SafeMarkdown>{critique.critique || ''}</SafeMarkdown>
                          </div>
                        </div>
                      ))}
                  </div>
                </div>

                {/* Revision section */}
                {iter.revision && (
                  <div className="revision-section">
                    <div className="section-header">
                      <span className="section-title">Chairman Revision</span>
                    </div>
                    <div className="revision-text markdown-content">
                      <SafeMarkdown>{iter.revision}</SafeMarkdown>
                    </div>
                  </div>
                )}

                {/* Stop reason if converged */}
                {iter.stopped && iter.stop_reason && (
                  <div className="stop-reason">
                    <span className="stop-icon">&#10003;</span>
                    {iter.stop_reason}
                  </div>
                )}
              </div>
            )}
          </div>
        ))}

        {/* Streaming iteration (in progress) */}
        {isRefining && currentIteration > 0 && !iterations.find(i => i.iteration === currentIteration) && (
          <div className="iteration-card in-progress">
            <div className="iteration-header expanded">
              <span className="iteration-number">
                <span className="spinner-small"></span>
                Iteration {currentIteration}
              </span>
              <span className="iteration-summary">In Progress</span>
            </div>
            <div className="iteration-content">
              {/* Streaming critiques */}
              {streamingCritiques.length > 0 && (
                <div className="critiques-section">
                  <div className="section-header">
                    <span className="section-title">Collecting Critiques...</span>
                  </div>
                  <div className="critiques-list">
                    {streamingCritiques.map((critique, idx) => (
                      <div
                        key={idx}
                        className={`critique-item ${critique.is_substantive ? 'substantive' : 'non-substantive'}`}
                      >
                        <div className="critique-header">
                          <span className="critique-model">
                            {critique.model?.split('/')[1] || critique.model}
                          </span>
                          <span className={`substantive-badge ${critique.is_substantive ? 'yes' : 'no'}`}>
                            {critique.is_substantive ? 'Substantive' : 'Non-substantive'}
                          </span>
                        </div>
                        <div className="critique-text markdown-content">
                          <SafeMarkdown>{critique.critique || ''}</SafeMarkdown>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Streaming revision */}
              {streamingRevision && (
                <div className="revision-section">
                  <div className="section-header">
                    <span className="section-title">
                      <span className="spinner-small"></span>
                      Chairman Revising...
                    </span>
                  </div>
                  <div className="revision-text markdown-content streaming">
                    <SafeMarkdown>{streamingRevision}</SafeMarkdown>
                    <span className="streaming-cursor"></span>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Summary */}
      {!isRefining && totalIterations > 0 && (
        <div className="refinement-summary">
          <div className="summary-icon">{converged ? '✓' : '→'}</div>
          <div className="summary-text">
            {converged
              ? `Refinement converged after ${totalIterations} iteration${totalIterations !== 1 ? 's' : ''} - no further improvements needed`
              : `Completed ${totalIterations} refinement iteration${totalIterations !== 1 ? 's' : ''}`}
          </div>
          {totalCost && totalCost.total > 0 && (
            <div className="summary-cost">
              ${totalCost.total.toFixed(4)}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/**
 * RefinementBadge - Small badge indicator for refinement status
 */
export function RefinementBadge({ iterations, converged }) {
  if (!iterations || iterations === 0) return null;

  return (
    <span className={`refinement-badge-small ${converged ? 'converged' : ''}`} title={converged ? 'Refinement converged' : `${iterations} refinement iterations`}>
      R{iterations}{converged ? '✓' : ''}
    </span>
  );
}

/**
 * RefinementToggle - Toggle control for enabling refinement mode
 */
export function RefinementToggle({ enabled, onChange, maxIterations, onMaxIterationsChange }) {
  return (
    <div className="refinement-toggle-control">
      <label className="toggle-label">
        <span className="toggle-text">Iterative Refinement</span>
        <div className={`toggle-switch ${enabled ? 'enabled' : ''}`} onClick={() => onChange(!enabled)}>
          <div className="toggle-slider"></div>
        </div>
      </label>
      {enabled && onMaxIterationsChange && (
        <div className="max-iterations-control">
          <label>Max iterations:</label>
          <select value={maxIterations} onChange={(e) => onMaxIterationsChange(Number(e.target.value))}>
            <option value={1}>1</option>
            <option value={2}>2</option>
            <option value={3}>3</option>
            <option value={4}>4</option>
            <option value={5}>5</option>
          </select>
        </div>
      )}
    </div>
  );
}
