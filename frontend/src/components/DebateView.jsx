import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import './DebateView.css';

/**
 * DebateView - Displays the structured debate visualization.
 *
 * Shows the multi-round debate with:
 * - Round 1: Position statements from all models
 * - Round 2: Critiques (each model critiques another)
 * - Round 3: Rebuttals (each model defends their position)
 * - Judgment: Chairman evaluates and synthesizes
 *
 * @param {Object} props
 * @param {Array} props.positions - Round 1 position statements
 * @param {Array} props.critiques - Round 2 critiques
 * @param {Array} props.rebuttals - Round 3 rebuttals
 * @param {string} props.judgment - Chairman's final judgment
 * @param {Object} props.modelToLabel - Mapping of model IDs to labels (Position A, B, C)
 * @param {Object} props.labelToModel - Mapping of labels to model IDs
 * @param {number} props.numRounds - Number of debate rounds (2 or 3)
 * @param {boolean} props.isDebating - Whether debate is in progress
 * @param {number} props.currentRound - Current round number during streaming
 * @param {string} props.judgmentStreaming - Partial judgment during streaming
 * @param {boolean} props.isJudging - Whether judgment is being generated
 */
export default function DebateView({
  positions = [],
  critiques = [],
  rebuttals = [],
  judgment = '',
  modelToLabel = {},
  labelToModel = {},
  numRounds = 3,
  isDebating = false,
  currentRound = 0,
  judgmentStreaming = '',
  isJudging = false,
}) {
  const [expandedRounds, setExpandedRounds] = useState({
    1: true,
    2: true,
    3: true,
    judgment: true,
  });

  const toggleRound = (round) => {
    setExpandedRounds(prev => ({
      ...prev,
      [round]: !prev[round],
    }));
  };

  const getModelDetails = (modelStr) => {
    if (!modelStr) return { name: 'Unknown', skill: '', colorClass: 'model-neutral' };
    const [baseModel, skill] = modelStr.split('@');
    const rawName = baseModel.split('/').pop() || baseModel;
    let colorClass = 'model-neutral';
    if (rawName.includes('claude')) colorClass = 'model-claude';
    else if (rawName.includes('qwen')) colorClass = 'model-qwen';
    else if (rawName.includes('antigravity') || rawName.includes('gemini')) colorClass = 'model-antigravity';
    else if (rawName.includes('gpt') || rawName.includes('openai')) colorClass = 'model-openai';

    return { name: rawName, skill, colorClass };
  };

  const getModelShortName = (model) => {
    return getModelDetails(model).name;
  };

  const getLabel = (model) => {
    return modelToLabel[model] || getModelShortName(model);
  };

  const hasRound1 = positions.length > 0;
  const hasRound2 = critiques.length > 0;
  const hasRound3 = rebuttals.length > 0 && numRounds >= 3;
  const hasJudgment = judgment || judgmentStreaming;

  if (!hasRound1 && !isDebating) {
    return null;
  }

  return (
    <div className="debate-view">
      <div className="debate-header">
        <div className="debate-title">
          <span className="debate-icon">&#9878;</span>
          <h4>Structured Debate</h4>
        </div>
        <div className="debate-progress">
          <span className={`round-indicator ${currentRound >= 1 || hasRound1 ? 'complete' : ''} ${currentRound === 1 ? 'active' : ''}`}>
            R1
          </span>
          <span className="round-connector"></span>
          <span className={`round-indicator ${currentRound >= 2 || hasRound2 ? 'complete' : ''} ${currentRound === 2 ? 'active' : ''}`}>
            R2
          </span>
          {numRounds >= 3 && (
            <>
              <span className="round-connector"></span>
              <span className={`round-indicator ${currentRound >= 3 || hasRound3 ? 'complete' : ''} ${currentRound === 3 ? 'active' : ''}`}>
                R3
              </span>
            </>
          )}
          <span className="round-connector"></span>
          <span className={`round-indicator judgment ${hasJudgment ? 'complete' : ''} ${isJudging ? 'active' : ''}`}>
            J
          </span>
        </div>
      </div>

      {/* Round 1: Positions */}
      {(hasRound1 || currentRound === 1) && (
        <div className="debate-round">
          <div
            className="round-header"
            onClick={() => toggleRound(1)}
          >
            <div className="round-info">
              <span className="round-number">Round 1</span>
              <span className="round-name">Position Statements</span>
              {currentRound === 1 && isDebating && (
                <span className="round-status streaming">Collecting...</span>
              )}
              {hasRound1 && currentRound !== 1 && (
                <span className="round-status complete">{positions.length} positions</span>
              )}
            </div>
            <span className={`toggle-icon ${expandedRounds[1] ? 'expanded' : ''}`}>
              &#9660;
            </span>
          </div>
          {expandedRounds[1] && (
            <div className="round-content">
              <div className="positions-grid">
                {positions.map((pos, idx) => {
                  const details = getModelDetails(pos.model);
                  return (
                    <div key={idx} className={`position-card card-${details.colorClass}`}>
                      <div className="position-header">
                        <div className="speaker-identity">
                          <span className={`model-avatar-tag ${details.colorClass}`}>
                            {details.name}
                          </span>
                          {details.skill && <span className="speaker-skill-tag">@{details.skill}</span>}
                        </div>
                        <span className="position-label-pill">{modelToLabel[pos.model] || `Position ${String.fromCharCode(65 + idx)}`}</span>
                      </div>
                      <div className="position-content markdown-content">
                        <ReactMarkdown>{pos.position}</ReactMarkdown>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Round 2: Critiques */}
      {(hasRound2 || currentRound === 2) && (
        <div className="debate-round">
          <div
            className="round-header"
            onClick={() => toggleRound(2)}
          >
            <div className="round-info">
              <span className="round-number">Round 2</span>
              <span className="round-name">Critiques</span>
              {currentRound === 2 && isDebating && (
                <span className="round-status streaming">Collecting...</span>
              )}
              {hasRound2 && currentRound !== 2 && (
                <span className="round-status complete">{critiques.length} critiques</span>
              )}
            </div>
            <span className={`toggle-icon ${expandedRounds[2] ? 'expanded' : ''}`}>
              &#9660;
            </span>
          </div>
          {expandedRounds[2] && (
            <div className="round-content">
              <div className="critiques-list">
                {critiques.map((crit, idx) => {
                  const criticDetails = getModelDetails(crit.critic);
                  const targetDetails = getModelDetails(crit.target);
                  return (
                    <div key={idx} className="critique-card">
                      <div className="critique-header">
                        <div className="critique-flow">
                          <div className={`participant-chip chip-${criticDetails.colorClass}`}>
                            <span className="chip-model-name">{criticDetails.name}</span>
                            <span className="chip-role-tag">{modelToLabel[crit.critic] || 'Critic'}</span>
                          </div>
                          <div className="flow-direction-indicator">
                            <span className="flow-action-text">critiques</span>
                            <span className="critique-arrow">&#10132;</span>
                          </div>
                          <div className={`participant-chip chip-${targetDetails.colorClass}`}>
                            <span className="chip-model-name">{targetDetails.name}</span>
                            <span className="chip-role-tag">{modelToLabel[crit.target] || 'Target'}</span>
                          </div>
                        </div>
                      </div>
                      <div className="critique-content markdown-content">
                        <ReactMarkdown>{crit.critique}</ReactMarkdown>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Round 3: Rebuttals */}
      {numRounds >= 3 && (hasRound3 || currentRound === 3) && (
        <div className="debate-round">
          <div
            className="round-header"
            onClick={() => toggleRound(3)}
          >
            <div className="round-info">
              <span className="round-number">Round 3</span>
              <span className="round-name">Rebuttals</span>
              {currentRound === 3 && isDebating && (
                <span className="round-status streaming">Collecting...</span>
              )}
              {hasRound3 && currentRound !== 3 && (
                <span className="round-status complete">{rebuttals.length} rebuttals</span>
              )}
            </div>
            <span className={`toggle-icon ${expandedRounds[3] ? 'expanded' : ''}`}>
              &#9660;
            </span>
          </div>
          {expandedRounds[3] && (
            <div className="round-content">
              <div className="rebuttals-list">
                {rebuttals.map((reb, idx) => {
                  const defenderDetails = getModelDetails(reb.model);
                  return (
                    <div key={idx} className={`rebuttal-card card-${defenderDetails.colorClass}`}>
                      <div className="rebuttal-header">
                        <div className="speaker-identity">
                          <span className={`model-avatar-tag ${defenderDetails.colorClass}`}>
                            {defenderDetails.name}
                          </span>
                          {defenderDetails.skill && <span className="speaker-skill-tag">@{defenderDetails.skill}</span>}
                          <span className="position-label-pill">{getLabel(reb.model)}</span>
                        </div>
                        <span className="rebuttal-badge">Rebuttal</span>
                      </div>
                      <div className="rebuttal-content markdown-content">
                        <ReactMarkdown>{reb.rebuttal}</ReactMarkdown>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Judgment */}
      {(hasJudgment || isJudging) && (
        <div className="debate-round judgment-round">
          <div
            className="round-header judgment-header"
            onClick={() => toggleRound('judgment')}
          >
            <div className="round-info">
              <span className="round-number">Final</span>
              <span className="round-name">Judgment</span>
              {isJudging && (
                <span className="round-status streaming">Generating...</span>
              )}
              {hasJudgment && !isJudging && (
                <span className="round-status complete">Complete</span>
              )}
            </div>
            <span className={`toggle-icon ${expandedRounds.judgment ? 'expanded' : ''}`}>
              &#9660;
            </span>
          </div>
          {expandedRounds.judgment && (
            <div className="round-content judgment-content">
              <div className={`judgment-text markdown-content ${isJudging ? 'streaming' : ''}`}>
                <ReactMarkdown>{judgment || judgmentStreaming}</ReactMarkdown>
                {isJudging && <span className="streaming-cursor"></span>}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/**
 * DebateBadge - Small badge for Stage 3 header indicating debate mode
 */
export function DebateBadge({ numRounds = 3 }) {
  return (
    <span className="debate-badge-small">
      <span className="debate-badge-icon">&#9878;</span>
      {numRounds}R Debate
    </span>
  );
}

/**
 * DebateToggle - Toggle control for enabling/disabling debate mode
 */
export function DebateToggle({ enabled, onChange, includeRebuttal, onRebuttalChange }) {
  return (
    <div className="debate-toggle-control">
      <label className="toggle-label">
        <span className="toggle-text">Debate Mode</span>
        <div
          className={`toggle-switch ${enabled ? 'enabled' : ''}`}
          onClick={() => onChange(!enabled)}
        >
          <div className="toggle-slider"></div>
        </div>
      </label>
      {enabled && (
        <label className="toggle-label sub-toggle">
          <span className="toggle-text-small">Include Rebuttals</span>
          <input
            type="checkbox"
            checked={includeRebuttal}
            onChange={(e) => onRebuttalChange(e.target.checked)}
          />
        </label>
      )}
    </div>
  );
}
