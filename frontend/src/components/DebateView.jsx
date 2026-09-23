import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import { getAgentProfile } from '../agentProfiles';
import './DebateView.css';

/**
 * ModelBadge - Renders a rich model chip with avatar, display name, color, and role.
 */
function ModelBadge({ model, roleLabel, customSkill }) {
  if (!model) return null;
  const [baseModel, skillFromModel = ''] = model.split('@');
  const skill = customSkill || skillFromModel;
  const profile = getAgentProfile(baseModel);

  return (
    <div className="debate-model-badge" style={{ '--agent-color': profile.color }}>
      <div className="debate-avatar-circle">
        {profile.avatarUrl ? (
          <img src={profile.avatarUrl} alt={profile.displayName} />
        ) : (
          <span>{profile.initials}</span>
        )}
      </div>
      <div className="debate-model-meta">
        <span className="debate-display-name" style={{ color: profile.color }}>
          {profile.displayName}
        </span>
        <span className="debate-model-id">{baseModel}</span>
      </div>
      {skill && <span className="debate-skill-pill">@{skill}</span>}
      {roleLabel && <span className="debate-role-pill">{roleLabel}</span>}
    </div>
  );
}

/**
 * DebateView - Displays the structured debate visualization.
 *
 * Shows the multi-round debate with:
 * - Round 1: Position statements from all models
 * - Round 2: Critiques (each model critiques another)
 * - Round 3: Rebuttals (each model defends their position)
 * - Judgment: Chairman evaluates and synthesizes
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
  chairmanModel = '',
}) {
  const [viewMode, setViewMode] = useState('all'); // 'all' | '1' | '2' | '3' | 'judgment'
  const [expandedRounds, setExpandedRounds] = useState({
    1: true,
    2: true,
    3: true,
    judgment: true,
  });

  const toggleRound = (round) => {
    setExpandedRounds((prev) => ({
      ...prev,
      [round]: !prev[round],
    }));
  };

  const hasRound1 = positions.length > 0;
  const hasRound2 = critiques.length > 0;
  const hasRound3 = rebuttals.length > 0 && numRounds >= 3;
  const hasJudgment = Boolean(judgment || judgmentStreaming);

  if (!hasRound1 && !isDebating) {
    return null;
  }

  const shouldShowRound = (roundKey) => {
    if (viewMode === 'all') return true;
    return viewMode === roundKey;
  };

  return (
    <div className="debate-view">
      {/* Header & Protocol Stepper */}
      <div className="debate-header">
        <div className="debate-title-group">
          <span className="debate-protocol-tag">DEBATE PROTOCOL</span>
          <h4 className="debate-main-heading">Structured Deliberation</h4>
        </div>

        {/* Stepper Navigation / Filter */}
        <div className="debate-stepper">
          <button
            type="button"
            className={`stepper-pill ${viewMode === 'all' ? 'active' : ''}`}
            onClick={() => setViewMode('all')}
          >
            <span>Tümü</span>
          </button>

          {/* R1 Step */}
          <button
            type="button"
            className={`stepper-pill ${viewMode === '1' ? 'active' : ''} ${
              currentRound === 1 && isDebating ? 'streaming' : hasRound1 ? 'complete' : ''
            }`}
            onClick={() => setViewMode(viewMode === '1' ? 'all' : '1')}
            title="Round 1: Position Statements"
          >
            <span className="step-tag">R1</span>
            <span className="step-label">Pozisyonlar</span>
            {hasRound1 && <span className="step-count">{positions.length}</span>}
            {currentRound === 1 && isDebating && <span className="pulse-dot"></span>}
          </button>

          {/* R2 Step */}
          <button
            type="button"
            className={`stepper-pill ${viewMode === '2' ? 'active' : ''} ${
              currentRound === 2 && isDebating ? 'streaming' : hasRound2 ? 'complete' : ''
            }`}
            onClick={() => setViewMode(viewMode === '2' ? 'all' : '2')}
            title="Round 2: Cross Critiques"
          >
            <span className="step-tag">R2</span>
            <span className="step-label">Eleştiriler</span>
            {hasRound2 && <span className="step-count">{critiques.length}</span>}
            {currentRound === 2 && isDebating && <span className="pulse-dot"></span>}
          </button>

          {/* R3 Step */}
          {numRounds >= 3 && (
            <button
              type="button"
              className={`stepper-pill ${viewMode === '3' ? 'active' : ''} ${
                currentRound === 3 && isDebating ? 'streaming' : hasRound3 ? 'complete' : ''
              }`}
              onClick={() => setViewMode(viewMode === '3' ? 'all' : '3')}
              title="Round 3: Rebuttals & Defense"
            >
              <span className="step-tag">R3</span>
              <span className="step-label">Savunmalar</span>
              {hasRound3 && <span className="step-count">{rebuttals.length}</span>}
              {currentRound === 3 && isDebating && <span className="pulse-dot"></span>}
            </button>
          )}

          {/* Judgment Step */}
          <button
            type="button"
            className={`stepper-pill judgment-pill ${viewMode === 'judgment' ? 'active' : ''} ${
              isJudging ? 'streaming' : hasJudgment ? 'complete' : ''
            }`}
            onClick={() => setViewMode(viewMode === 'judgment' ? 'all' : 'judgment')}
            title="Final Chairman Judgment"
          >
            <span className="step-tag">J</span>
            <span className="step-label">Hüküm</span>
            {isJudging && <span className="pulse-dot"></span>}
          </button>
        </div>
      </div>

      {/* Round 1: Positions */}
      {(hasRound1 || currentRound === 1) && shouldShowRound('1') && (
        <div className="debate-round-card">
          <div
            className="round-card-header"
            onClick={() => toggleRound(1)}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                toggleRound(1);
              }
            }}
          >
            <div className="round-header-left">
              <span className="round-stage-badge">ROUND 1</span>
              <span className="round-stage-title">Initial Positions</span>
              {currentRound === 1 && isDebating && (
                <span className="round-status-pill streaming">Collecting positions...</span>
              )}
              {hasRound1 && currentRound !== 1 && (
                <span className="round-status-pill complete">{positions.length} model</span>
              )}
            </div>
            <span className={`toggle-caret ${expandedRounds[1] ? 'expanded' : ''}`}></span>
          </div>

          {expandedRounds[1] && (
            <div className="round-card-body">
              <div className="positions-grid">
                {positions.map((pos, idx) => {
                  const roleLabel = modelToLabel[pos.model] || `Position ${String.fromCharCode(65 + idx)}`;
                  return (
                    <div key={idx} className="position-card">
                      <div className="position-card-header">
                        <ModelBadge model={pos.model} roleLabel={roleLabel} />
                      </div>
                      <div className="card-markdown-content">
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
      {(hasRound2 || currentRound === 2) && shouldShowRound('2') && (
        <div className="debate-round-card">
          <div
            className="round-card-header"
            onClick={() => toggleRound(2)}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                toggleRound(2);
              }
            }}
          >
            <div className="round-header-left">
              <span className="round-stage-badge">ROUND 2</span>
              <span className="round-stage-title">Direct Cross-Critiques</span>
              {currentRound === 2 && isDebating && (
                <span className="round-status-pill streaming">Critiques in progress...</span>
              )}
              {hasRound2 && currentRound !== 2 && (
                <span className="round-status-pill complete">{critiques.length} critiques</span>
              )}
            </div>
            <span className={`toggle-caret ${expandedRounds[2] ? 'expanded' : ''}`}></span>
          </div>

          {expandedRounds[2] && (
            <div className="round-card-body">
              <div className="critiques-list">
                {critiques.map((crit, idx) => (
                  <div key={idx} className="critique-card">
                    <div className="critique-card-header">
                      <div className="critique-flow">
                        <ModelBadge
                          model={crit.critic}
                          roleLabel={crit.critic_label || modelToLabel[crit.critic] || 'Critic'}
                        />
                        <div className="flow-direction-badge">
                          <span>CRITIQUES</span>
                          <span className="flow-arrow">&rarr;</span>
                        </div>
                        <ModelBadge
                          model={crit.target}
                          roleLabel={crit.target_label || modelToLabel[crit.target] || 'Target'}
                        />
                      </div>
                    </div>
                    <div className="card-markdown-content">
                      <ReactMarkdown>{crit.critique}</ReactMarkdown>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Round 3: Rebuttals */}
      {numRounds >= 3 && (hasRound3 || currentRound === 3) && shouldShowRound('3') && (
        <div className="debate-round-card">
          <div
            className="round-card-header"
            onClick={() => toggleRound(3)}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                toggleRound(3);
              }
            }}
          >
            <div className="round-header-left">
              <span className="round-stage-badge">ROUND 3</span>
              <span className="round-stage-title">Rebuttals &amp; Defense</span>
              {currentRound === 3 && isDebating && (
                <span className="round-status-pill streaming">Defending positions...</span>
              )}
              {hasRound3 && currentRound !== 3 && (
                <span className="round-status-pill complete">{rebuttals.length} rebuttals</span>
              )}
            </div>
            <span className={`toggle-caret ${expandedRounds[3] ? 'expanded' : ''}`}></span>
          </div>

          {expandedRounds[3] && (
            <div className="round-card-body">
              <div className="rebuttals-list">
                {rebuttals.map((reb, idx) => (
                  <div key={idx} className="rebuttal-card">
                    <div className="rebuttal-card-header">
                      <ModelBadge model={reb.model} roleLabel={modelToLabel[reb.model] || 'Defender'} />
                      <span className="rebuttal-tag">REBUTTAL</span>
                    </div>
                    <div className="card-markdown-content">
                      <ReactMarkdown>{reb.rebuttal}</ReactMarkdown>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Final Judgment */}
      {(hasJudgment || isJudging) && shouldShowRound('judgment') && (
        <div className="debate-round-card judgment-card">
          <div
            className="round-card-header judgment-card-header"
            onClick={() => toggleRound('judgment')}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                toggleRound('judgment');
              }
            }}
          >
            <div className="round-header-left">
              <span className="round-stage-badge judgment-badge">FINAL</span>
              <span className="round-stage-title">Chairman Verdict &amp; Judgment</span>
              {isJudging && <span className="round-status-pill streaming">Synthesizing verdict...</span>}
              {hasJudgment && !isJudging && <span className="round-status-pill complete">Verdict Reached</span>}
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              {chairmanModel && <ModelBadge model={chairmanModel} roleLabel="Chairman" />}
              <span className={`toggle-caret ${expandedRounds.judgment ? 'expanded' : ''}`}></span>
            </div>
          </div>

          {expandedRounds.judgment && (
            <div className="round-card-body judgment-card-body">
              <div className="card-markdown-content judgment-markdown">
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
 * DebateBadge - Small badge indicating debate mode in header
 */
export function DebateBadge({ numRounds = 3 }) {
  return (
    <span className="debate-badge-pill">
      <span className="debate-badge-num">{numRounds}R</span>
      <span className="debate-badge-text">Structured Debate</span>
    </span>
  );
}

/**
 * DebateToggle - Modern toggle switch for debate mode
 */
export function DebateToggle({ enabled, onChange, includeRebuttal, onRebuttalChange }) {
  return (
    <div className="debate-toggle-control">
      <label className="toggle-row">
        <span className="toggle-title">Debate Mode</span>
        <button
          type="button"
          className={`toggle-switch-btn ${enabled ? 'active' : ''}`}
          onClick={() => onChange(!enabled)}
          aria-label="Toggle Debate Mode"
        >
          <span className="toggle-switch-thumb"></span>
        </button>
      </label>
      {enabled && (
        <label className="toggle-sub-row">
          <input
            type="checkbox"
            checked={includeRebuttal}
            onChange={(e) => onRebuttalChange(e.target.checked)}
          />
          <span className="toggle-sub-text">Include Rebuttals (Round 3)</span>
        </label>
      )}
    </div>
  );
}
