import React, { useState, useEffect } from 'react';
import './SettingsModal.css';

const PRESETS = [
  {
    id: 'fast',
    label: 'Fast',
    desc: 'Skip synthesis when the council agrees; reuse cached answers.',
    flags: { useWeightedConsensus: true, useEarlyConsensus: true, useCache: true },
  },
  {
    id: 'balanced',
    label: 'Balanced',
    desc: 'Full 3-stage council with weighted votes. The default.',
    flags: { useWeightedConsensus: true, useResearch: true },
  },
  {
    id: 'deep',
    label: 'Deep',
    desc: 'Structured reasoning, critique-and-revise, then a devil’s advocate pass.',
    flags: { useCot: true, useWeightedConsensus: true, useRefinement: true, useAdversary: true, useResearch: true },
  },
  {
    id: 'debate',
    label: 'Debate',
    desc: 'Models argue positions, rebut critiques, and the chairman judges.',
    flags: { useDebate: true, useWeightedConsensus: true, useResearch: true },
  },
];

/**
 * SettingsModal - Deliberation & System Settings Modal
 * Replaces the buggy half-screen inline drawer with a dedicated, focused modal.
 */
export default function SettingsModal({
  isOpen,
  onClose,
  systemPrompt,
  onSystemPromptChange,
  useCot,
  onCotChange,
  useMultiChairman,
  onMultiChairmanChange,
  useWeightedConsensus,
  onWeightedConsensusChange,
  useEarlyConsensus,
  onEarlyConsensusChange,
  useDynamicRouting,
  onDynamicRoutingChange,
  useEscalation,
  onEscalationChange,
  useRefinement,
  onRefinementChange,
  refinementMaxIterations,
  onRefinementMaxIterationsChange,
  useAdversary,
  onAdversaryChange,
  useDebate,
  onDebateChange,
  includeRebuttal,
  onIncludeRebuttalChange,
  useDecomposition,
  onDecompositionChange,
  useCache,
  onCacheChange,
  useResearch,
  onResearchChange,
}) {
  const [activeTab, setActiveTab] = useState('prompt');

  // Close on Escape key
  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  // Active flags counters
  const promptActive = !!systemPrompt || useCot || useDecomposition;
  const consensusActive = useMultiChairman || useWeightedConsensus || useEarlyConsensus || useDebate;
  const advancedActive = useDynamicRouting || useEscalation || useRefinement || useAdversary || useCache || useResearch;

  const totalActiveCount = [
    !!systemPrompt,
    useCot,
    useDecomposition,
    useMultiChairman,
    useWeightedConsensus,
    useEarlyConsensus,
    useDebate,
    useDynamicRouting,
    useEscalation,
    useRefinement,
    useAdversary,
    useCache,
    useResearch,
  ].filter(Boolean).length;

  // Presets set every mode flag at once; the system prompt is left alone.
  const setters = {
    useCot: onCotChange,
    useDecomposition: onDecompositionChange,
    useMultiChairman: onMultiChairmanChange,
    useWeightedConsensus: onWeightedConsensusChange,
    useEarlyConsensus: onEarlyConsensusChange,
    useDebate: onDebateChange,
    useDynamicRouting: onDynamicRoutingChange,
    useEscalation: onEscalationChange,
    useRefinement: onRefinementChange,
    useAdversary: onAdversaryChange,
    useCache: onCacheChange,
    useResearch: onResearchChange,
  };
  const current = {
    useCot,
    useDecomposition,
    useMultiChairman,
    useWeightedConsensus,
    useEarlyConsensus,
    useDebate,
    useDynamicRouting,
    useEscalation,
    useRefinement,
    useAdversary,
    useCache,
    useResearch,
  };
  const activePreset = PRESETS.find((p) =>
    Object.keys(setters).every((key) => Boolean(p.flags[key]) === Boolean(current[key]))
  );

  const applyPreset = (preset) => {
    Object.entries(setters).forEach(([key, set]) => set(Boolean(preset.flags[key])));
    if (preset.flags.useDebate) onIncludeRebuttalChange(true);
    if (preset.flags.useRefinement) onRefinementMaxIterationsChange(2);
  };

  const handleResetDefaults = () => {
    onSystemPromptChange('');
    onCotChange(false);
    onDecompositionChange(false);
    onMultiChairmanChange(false);
    onWeightedConsensusChange(true);
    onEarlyConsensusChange(false);
    onDebateChange(false);
    onIncludeRebuttalChange(true);
    onDynamicRoutingChange(false);
    onEscalationChange(false);
    onRefinementChange(false);
    onRefinementMaxIterationsChange(2);
    onAdversaryChange(false);
    onCacheChange(false);
    onResearchChange(true);
  };

  return (
    <div className="settings-modal-backdrop" onClick={onClose}>
      <div className="settings-modal-card" onClick={(e) => e.stopPropagation()}>
        {/* Modal Header */}
        <div className="settings-modal-header">
          <div className="settings-header-left">
            <div>
              <div className="settings-header-title-row">
                <h2>Deliberation Settings</h2>
                {totalActiveCount > 0 && (
                  <span className="settings-count-badge">
                    {totalActiveCount} Active Mode{totalActiveCount > 1 ? 's' : ''}
                  </span>
                )}
              </div>
              <p className="settings-header-subtitle">
                Configure reasoning modes, consensus algorithms, and routing strategies
              </p>
            </div>
          </div>
          <button
            type="button"
            className="settings-modal-close-btn"
            onClick={onClose}
            aria-label="Close settings"
          >
            &times;
          </button>
        </div>

        {/* Presets: the common path. Tabs below are for fine-tuning. */}
        <div className="settings-presets" role="radiogroup" aria-label="Deliberation preset">
          {PRESETS.map((preset) => (
            <button
              key={preset.id}
              type="button"
              role="radio"
              aria-checked={activePreset?.id === preset.id}
              className={`settings-preset ${activePreset?.id === preset.id ? 'active' : ''}`}
              onClick={() => applyPreset(preset)}
            >
              <span className="settings-preset-label">{preset.label}</span>
              <span className="settings-preset-desc">{preset.desc}</span>
            </button>
          ))}
          {!activePreset && <div className="settings-preset-custom">Custom mix — fine-tune below</div>}
        </div>

        {/* Modal Tabs */}
        <div className="settings-modal-tabs">
          <button
            type="button"
            className={`settings-tab-btn ${activeTab === 'prompt' ? 'active' : ''}`}
            onClick={() => setActiveTab('prompt')}
          >
            <span>Prompt & Reasoning</span>
            {promptActive && <span className="tab-active-dot" />}
          </button>
          <button
            type="button"
            className={`settings-tab-btn ${activeTab === 'consensus' ? 'active' : ''}`}
            onClick={() => setActiveTab('consensus')}
          >
            <span>Consensus & Deliberation</span>
            {consensusActive && <span className="tab-active-dot" />}
          </button>
          <button
            type="button"
            className={`settings-tab-btn ${activeTab === 'advanced' ? 'active' : ''}`}
            onClick={() => setActiveTab('advanced')}
          >
            <span>Routing & Optimization</span>
            {advancedActive && <span className="tab-active-dot" />}
          </button>
        </div>

        {/* Modal Body */}
        <div className="settings-modal-body">
          {/* TAB 1: PROMPT & REASONING */}
          {activeTab === 'prompt' && (
            <div className="settings-tab-content">
              <div className="settings-group-card">
                <div className="settings-group-header">
                  <label htmlFor="system-prompt-input">System Prompt</label>
                  {systemPrompt && (
                    <button
                      type="button"
                      className="settings-clear-btn"
                      onClick={() => onSystemPromptChange('')}
                    >
                      Clear
                    </button>
                  )}
                </div>
                <textarea
                  id="system-prompt-input"
                  className="settings-textarea"
                  value={systemPrompt}
                  onChange={(e) => onSystemPromptChange(e.target.value)}
                  placeholder="Inject a system prompt across all council models (e.g. 'You are a senior systems architect. Prioritize memory safety and latency.')..."
                  rows={4}
                />
                <div className="settings-field-hint">
                  Applied to Stage 1 generation, Stage 2 peer reviews, and Stage 3 synthesis.
                </div>
              </div>

              <div className="settings-toggles-grid">
                {/* Chain-of-Thought */}
                <label className="settings-toggle-card">
                  <div className="settings-toggle-left">
                    <input
                      type="checkbox"
                      checked={useCot}
                      onChange={(e) => onCotChange(e.target.checked)}
                    />
                    <span className="settings-slider" />
                  </div>
                  <div className="settings-toggle-info">
                    <div className="settings-toggle-title">
                      Chain-of-Thought (CoT)
                      <span className="badge-tag tag-blue">CoT</span>
                    </div>
                    <div className="settings-toggle-desc">
                      Forces models to output structured reasoning (Thinking → Analysis → Conclusion) before decisions.
                    </div>
                  </div>
                </label>

                {/* Sub-Question Decomposition */}
                <label className="settings-toggle-card">
                  <div className="settings-toggle-left">
                    <input
                      type="checkbox"
                      checked={useDecomposition}
                      onChange={(e) => onDecompositionChange(e.target.checked)}
                    />
                    <span className="settings-slider" />
                  </div>
                  <div className="settings-toggle-info">
                    <div className="settings-toggle-title">
                      Sub-Question Decomposition
                      <span className="badge-tag tag-purple">DQ</span>
                    </div>
                    <div className="settings-toggle-desc">
                      Breaks complex prompts into sub-questions, runs map-reduce across models, and merges answers.
                    </div>
                  </div>
                </label>
              </div>
            </div>
          )}

          {/* TAB 2: CONSENSUS & DELIBERATION */}
          {activeTab === 'consensus' && (
            <div className="settings-tab-content">
              <div className="settings-toggles-grid">
                {/* Multi-Chairman Mode */}
                <label className="settings-toggle-card">
                  <div className="settings-toggle-left">
                    <input
                      type="checkbox"
                      checked={useMultiChairman}
                      onChange={(e) => onMultiChairmanChange(e.target.checked)}
                    />
                    <span className="settings-slider" />
                  </div>
                  <div className="settings-toggle-info">
                    <div className="settings-toggle-title">
                      Multi-Chairman Mode
                      <span className="badge-tag tag-orange">MC</span>
                    </div>
                    <div className="settings-toggle-desc">
                      Ensemble synthesis: runs multiple distinct chairmen in parallel and performs supreme synthesis.
                    </div>
                  </div>
                </label>

                {/* Weighted Consensus */}
                <label className="settings-toggle-card">
                  <div className="settings-toggle-left">
                    <input
                      type="checkbox"
                      checked={useWeightedConsensus}
                      onChange={(e) => onWeightedConsensusChange(e.target.checked)}
                    />
                    <span className="settings-slider" />
                  </div>
                  <div className="settings-toggle-info">
                    <div className="settings-toggle-title">
                      Weighted Consensus
                      <span className="badge-tag tag-emerald">WC</span>
                    </div>
                    <div className="settings-toggle-desc">
                      Weights peer-review votes by historical win-rate and board performance instead of equal 1:1 voting.
                    </div>
                  </div>
                </label>

                {/* Early Consensus Exit */}
                <label className="settings-toggle-card">
                  <div className="settings-toggle-left">
                    <input
                      type="checkbox"
                      checked={useEarlyConsensus}
                      onChange={(e) => onEarlyConsensusChange(e.target.checked)}
                    />
                    <span className="settings-slider" />
                  </div>
                  <div className="settings-toggle-info">
                    <div className="settings-toggle-title">
                      Early Consensus Exit
                      <span className="badge-tag tag-cyan">EC</span>
                    </div>
                    <div className="settings-toggle-desc">
                      Short-circuits Stage 3 synthesis if peer rankings show unanimous consensus, saving time and cost.
                    </div>
                  </div>
                </label>

                {/* Debate Mode */}
                <div className="settings-toggle-card-wrapper">
                  <label className="settings-toggle-card">
                    <div className="settings-toggle-left">
                      <input
                        type="checkbox"
                        checked={useDebate}
                        onChange={(e) => onDebateChange(e.target.checked)}
                      />
                      <span className="settings-slider" />
                    </div>
                    <div className="settings-toggle-info">
                      <div className="settings-toggle-title">
                        Debate Mode
                        <span className="badge-tag tag-red">DB</span>
                      </div>
                      <div className="settings-toggle-desc">
                        Multi-round structured debate: Position → Direct Critique → Rebuttal → Chairman Judgment.
                      </div>
                    </div>
                  </label>
                  {useDebate && (
                    <div className="settings-sub-option">
                      <label className="settings-sub-checkbox-label">
                        <input
                          type="checkbox"
                          checked={includeRebuttal}
                          onChange={(e) => onIncludeRebuttalChange(e.target.checked)}
                        />
                        <span>Include Round 3 Rebuttals (panelists defend and challenge critiques)</span>
                      </label>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* TAB 3: ROUTING & ADVANCED */}
          {activeTab === 'advanced' && (
            <div className="settings-tab-content">
              <div className="settings-toggles-grid">
                {/* Dynamic Model Routing */}
                <label className="settings-toggle-card">
                  <div className="settings-toggle-left">
                    <input
                      type="checkbox"
                      checked={useDynamicRouting}
                      onChange={(e) => onDynamicRoutingChange(e.target.checked)}
                    />
                    <span className="settings-slider" />
                  </div>
                  <div className="settings-toggle-info">
                    <div className="settings-toggle-title">
                      Dynamic Model Routing
                      <span className="badge-tag tag-blue">DR</span>
                    </div>
                    <div className="settings-toggle-desc">
                      Classifies prompt intent (coding, math, creative, ops) and dynamically selects matching model pools.
                    </div>
                  </div>
                </label>

                {/* Confidence-Gated Escalation */}
                <label className="settings-toggle-card">
                  <div className="settings-toggle-left">
                    <input
                      type="checkbox"
                      checked={useEscalation}
                      onChange={(e) => onEscalationChange(e.target.checked)}
                    />
                    <span className="settings-slider" />
                  </div>
                  <div className="settings-toggle-info">
                    <div className="settings-toggle-title">
                      Confidence-Gated Escalation
                      <span className="badge-tag tag-orange">CG</span>
                    </div>
                    <div className="settings-toggle-desc">
                      Begins with fast, cost-effective models and escalates to flagship tiers only if confidence is low.
                    </div>
                  </div>
                </label>

                {/* Iterative Refinement */}
                <div className="settings-toggle-card-wrapper">
                  <label className="settings-toggle-card">
                    <div className="settings-toggle-left">
                      <input
                        type="checkbox"
                        checked={useRefinement}
                        onChange={(e) => onRefinementChange(e.target.checked)}
                      />
                      <span className="settings-slider" />
                    </div>
                    <div className="settings-toggle-info">
                      <div className="settings-toggle-title">
                        Iterative Refinement
                        <span className="badge-tag tag-emerald">IR</span>
                      </div>
                      <div className="settings-toggle-desc">
                        Post-Stage 3 loop: Council critiques the chairman draft and refines until quality score converges.
                      </div>
                    </div>
                  </label>
                  {useRefinement && (
                    <div className="settings-sub-option">
                      <label className="settings-sub-select-label">
                        <span>Max refinement iterations:</span>
                        <select
                          className="settings-select"
                          value={refinementMaxIterations}
                          onChange={(e) => onRefinementMaxIterationsChange(parseInt(e.target.value, 10))}
                        >
                          <option value="1">1 round</option>
                          <option value="2">2 rounds (recommended)</option>
                          <option value="3">3 rounds</option>
                          <option value="4">4 rounds</option>
                          <option value="5">5 rounds</option>
                        </select>
                      </label>
                    </div>
                  )}
                </div>

                {/* Adversarial Validation */}
                <label className="settings-toggle-card">
                  <div className="settings-toggle-left">
                    <input
                      type="checkbox"
                      checked={useAdversary}
                      onChange={(e) => onAdversaryChange(e.target.checked)}
                    />
                    <span className="settings-slider" />
                  </div>
                  <div className="settings-toggle-info">
                    <div className="settings-toggle-title">
                      Adversarial Validation (Red Team)
                      <span className="badge-tag tag-red">AV</span>
                    </div>
                    <div className="settings-toggle-desc">
                      Assigns an adversarial devil's advocate model to scrutinize flaws, edge-cases, and security risks.
                    </div>
                  </div>
                </label>

                {/* Semantic Response Caching */}
                <label className="settings-toggle-card">
                  <div className="settings-toggle-left">
                    <input
                      type="checkbox"
                      checked={useCache}
                      onChange={(e) => onCacheChange(e.target.checked)}
                    />
                    <span className="settings-slider" />
                  </div>
                  <div className="settings-toggle-info">
                    <div className="settings-toggle-title">
                      Semantic Response Caching
                      <span className="badge-tag tag-purple">CA</span>
                    </div>
                    <div className="settings-toggle-desc">
                      Re-uses cached deliberation graphs for highly similar queries (&gt;0.92 cosine similarity).
                    </div>
                  </div>
                </label>

                {/* Autonomous Tech Scouting */}
                <label className="settings-toggle-card">
                  <div className="settings-toggle-left">
                    <input
                      type="checkbox"
                      checked={useResearch}
                      onChange={(e) => onResearchChange(e.target.checked)}
                    />
                    <span className="settings-slider" />
                  </div>
                  <div className="settings-toggle-info">
                    <div className="settings-toggle-title">
                      Autonomous Tech Scouting
                      <span className="badge-tag tag-cyan">TS</span>
                    </div>
                    <div className="settings-toggle-desc">
                      Scouts GitHub, PyPI, and dev-agent-kit skills in parallel to inject real packages into deliberation.
                    </div>
                  </div>
                </label>
              </div>
            </div>
          )}
        </div>

        {/* Modal Footer */}
        <div className="settings-modal-footer">
          <button
            type="button"
            className="settings-footer-reset-btn"
            onClick={handleResetDefaults}
          >
            Reset to Defaults
          </button>
          <button
            type="button"
            className="settings-footer-done-btn"
            onClick={onClose}
          >
            Done
          </button>
        </div>
      </div>
    </div>
  );
}
