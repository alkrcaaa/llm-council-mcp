import { useState, useEffect } from 'react';
import { api } from '../api';
import './ConfigPanel.css';

function formatModelDisplay(model, skillsList = []) {
  const [baseModel, skillId] = model.split('@');
  const parts = baseModel.split('/');
  const skill = skillsList.find((s) => s.id === skillId);

  let modelContent;
  if (parts.length === 2) {
    const isLocal = parts[0] === 'local';
    modelContent = (
      <span className="config-model-name">
        <span className={`model-provider-tag ${isLocal ? 'provider-local' : 'provider-remote'}`}>
          {parts[0]}
        </span>
        <span className="model-slash">/</span>
        <span className="model-basename">{parts[1]}</span>
      </span>
    );
  } else {
    modelContent = <span className="config-model-name"><span className="model-basename">{baseModel}</span></span>;
  }

  return (
    <div className="model-display-wrap">
      {modelContent}
      {skill && (
        <span className="seat-skill-badge" title={skill.description}>
          <span className="skill-badge-tag">{skill.badge || 'SKILL'}</span>
          <span className="skill-badge-title">{skill.title}</span>
        </span>
      )}
    </div>
  );
}

/**
 * ConfigPanel - UI for managing council and chairman model configuration.
 */
export default function ConfigPanel({ onClose, onCouncilsUpdated }) {
  // Current configuration state
  const [councilModels, setCouncilModels] = useState([]);
  const [chairmanModel, setChairmanModel] = useState('');

  // Available models for suggestions
  const [availableModels, setAvailableModels] = useState([]);
  // Available skills from dev-agent-kit
  const [availableSkills, setAvailableSkills] = useState([]);

  // Council Profiles state
  const [savedCouncils, setSavedCouncils] = useState([]);
  const [activeCouncilId, setActiveCouncilId] = useState('');
  const [showSaveModal, setShowSaveModal] = useState(false);
  const [newCouncilName, setNewCouncilName] = useState('');
  const [newCouncilIcon, setNewCouncilIcon] = useState('🛡️');
  const [newCouncilDesc, setNewCouncilDesc] = useState('');

  // UI state
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState(null);
  const [successMessage, setSuccessMessage] = useState(null);

  // New model input
  const [newModelInput, setNewModelInput] = useState('');
  const [newModelSkill, setNewModelSkill] = useState('');
  const [showModelDropdown, setShowModelDropdown] = useState(false);

  // Load configuration, available models, skills, and council profiles on mount
  useEffect(() => {
    loadConfig();
    loadAvailableModels();
    loadSkills();
    loadCouncils();
  }, []);

  const loadConfig = async () => {
    try {
      setIsLoading(true);
      const config = await api.getConfig();
      setCouncilModels(config.council_models);
      setChairmanModel(config.chairman_model);
      setError(null);
    } catch (err) {
      setError('Failed to load configuration');
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  };

  const loadAvailableModels = async () => {
    try {
      const result = await api.getAvailableModels();
      // Ensure local models are always offered in suggestions
      const suggested = [...result.models];
      if (!suggested.includes('local/qwen3.6-27b')) suggested.unshift('local/qwen3.6-27b');
      if (!suggested.includes('local/antigravity')) suggested.unshift('local/antigravity');
      if (!suggested.includes('local/claude-code')) suggested.unshift('local/claude-code');
      setAvailableModels(suggested);
    } catch (err) {
      console.error('Failed to load available models:', err);
    }
  };

  const loadSkills = async () => {
    try {
      const result = await api.getSkills();
      setAvailableSkills(result.skills || []);
    } catch (err) {
      console.error('Failed to load skills from dev-agent-kit:', err);
    }
  };

  const loadCouncils = async () => {
    try {
      const res = await api.getCouncils();
      setSavedCouncils(res.councils || []);
      setActiveCouncilId(res.active_council_id || '');
    } catch (err) {
      console.error('Failed to load councils in ConfigPanel:', err);
    }
  };

  const handleLoadCouncil = async (council) => {
    setCouncilModels(council.council_models);
    setChairmanModel(council.chairman_model);
    setActiveCouncilId(council.id);
    try {
      await api.activateCouncil(council.id);
      onCouncilsUpdated?.();
      setSuccessMessage(`Activated "${council.name}" council profile.`);
      setTimeout(() => setSuccessMessage(null), 3000);
    } catch (err) {
      console.error(err);
    }
  };

  const handleCreateCouncilSubmit = async () => {
    if (!newCouncilName.trim()) return;
    if (councilModels.length < 2) {
      setError('At least 2 council models are required');
      return;
    }
    try {
      setIsSaving(true);
      const newCouncil = await api.createCouncil({
        name: newCouncilName.trim(),
        icon: newCouncilIcon,
        description: newCouncilDesc.trim(),
        council_models: councilModels,
        chairman_model: chairmanModel,
      });
      await api.activateCouncil(newCouncil.id);
      await loadCouncils();
      onCouncilsUpdated?.();
      setShowSaveModal(false);
      setNewCouncilName('');
      setNewCouncilDesc('');
      setSuccessMessage(`Created and activated "${newCouncil.name}"!`);
      setTimeout(() => setSuccessMessage(null), 3500);
    } catch (err) {
      setError(err.message || 'Failed to create council profile');
    } finally {
      setIsSaving(false);
    }
  };

  const handleDeleteCouncil = async (council) => {
    if (!window.confirm(`Delete "${council.name}" council profile?`)) return;
    try {
      await api.deleteCouncil(council.id);
      await loadCouncils();
      onCouncilsUpdated?.();
      setSuccessMessage(`Deleted "${council.name}".`);
      setTimeout(() => setSuccessMessage(null), 3000);
    } catch (err) {
      setError(err.message || 'Failed to delete council');
    }
  };

  const applyPreset = (models, chairman) => {
    setCouncilModels(models);
    setChairmanModel(chairman);
    setSuccessMessage('Preset loaded. Click "Save Configuration" to apply.');
    setTimeout(() => setSuccessMessage(null), 3500);
  };

  const handleAllQwenPreset = () => {
    applyPreset(
      [
        'local/qwen3.6-27b@owasp-security',
        'local/qwen3.6-27b@karpathy-guidelines',
        'local/qwen3.6-27b@devops',
        'local/qwen3.6-27b@testing-handbook',
      ],
      'local/qwen3.6-27b'
    );
  };

  const handleHybridPreset = () => {
    applyPreset(
      [
        'local/qwen3.6-27b@owasp-security',
        'local/antigravity@karpathy-guidelines',
        'local/qwen3.6-27b@devops',
      ],
      'local/antigravity'
    );
  };

  const handleLocalDuoPreset = () => {
    applyPreset(
      ['local/antigravity', 'local/qwen3.6-27b'],
      'local/antigravity'
    );
  };

  const handleModelSkillChange = (index, newSkillId) => {
    const current = councilModels[index];
    const baseModel = current.split('@')[0];
    const updatedModel = newSkillId ? `${baseModel}@${newSkillId}` : baseModel;
    const updated = [...councilModels];
    updated[index] = updatedModel;
    setCouncilModels(updated);

    // If this was chairman, update chairman reference if matching
    if (chairmanModel === current) {
      setChairmanModel(updatedModel);
    }
  };

  const handleSave = async () => {
    // Validate
    if (councilModels.length < 2) {
      setError('At least 2 council models are required');
      return;
    }

    if (!chairmanModel.trim()) {
      setError('Chairman model is required');
      return;
    }

    try {
      setIsSaving(true);
      setError(null);
      await api.updateConfig(councilModels, chairmanModel);

      // If a council profile is currently active, sync its models in councils.json
      if (activeCouncilId) {
        await api.updateCouncil(activeCouncilId, {
          council_models: councilModels,
          chairman_model: chairmanModel,
        }).catch(() => {});
        await loadCouncils();
        onCouncilsUpdated?.();
      }

      setSuccessMessage('Configuration saved successfully!');
      setTimeout(() => setSuccessMessage(null), 3000);
    } catch (err) {
      setError(err.message || 'Failed to save configuration');
    } finally {
      setIsSaving(false);
    }
  };

  const handleReset = async () => {
    if (!window.confirm('Reset configuration to defaults?')) {
      return;
    }

    try {
      setIsSaving(true);
      setError(null);
      const config = await api.resetConfig();
      setCouncilModels(config.council_models);
      setChairmanModel(config.chairman_model);
      setSuccessMessage('Configuration reset to defaults');
      setTimeout(() => setSuccessMessage(null), 3000);
    } catch (err) {
      setError('Failed to reset configuration');
    } finally {
      setIsSaving(false);
    }
  };

  const addModel = (model, skillId = '') => {
    const trimmed = model.trim();
    if (!trimmed) return;

    const fullModel = skillId ? `${trimmed}@${skillId}` : trimmed;

    // Don't add duplicates of exact same seat
    if (councilModels.includes(fullModel)) {
      setError('This exact model seat is already in council');
      setTimeout(() => setError(null), 2000);
      return;
    }

    setCouncilModels([...councilModels, fullModel]);
    setNewModelInput('');
    setNewModelSkill('');
    setShowModelDropdown(false);
  };

  const removeModel = (index) => {
    if (councilModels.length <= 2) {
      setError('At least 2 council models are required');
      setTimeout(() => setError(null), 2000);
      return;
    }

    const removed = councilModels[index];
    const newModels = councilModels.filter((_, i) => i !== index);
    setCouncilModels(newModels);

    // If chairman was removed, update to first model
    if (removed === chairmanModel) {
      setChairmanModel(newModels[0] || '');
    }
  };

  const moveModel = (index, direction) => {
    const newIndex = index + direction;
    if (newIndex < 0 || newIndex >= councilModels.length) return;

    const newModels = [...councilModels];
    [newModels[index], newModels[newIndex]] = [newModels[newIndex], newModels[index]];
    setCouncilModels(newModels);
  };

  // Filter available models for dropdown
  const filteredModels = availableModels.filter(
    (model) => model.toLowerCase().includes(newModelInput.toLowerCase())
  );

  if (isLoading) {
    return (
      <div className="config-panel">
        <div className="config-panel-header">
          <h2>Model Configuration</h2>
          <button className="close-btn" onClick={onClose}>
            &times;
          </button>
        </div>
        <div className="config-loading">Loading configuration...</div>
      </div>
    );
  }

  return (
    <div className="config-panel">
      <div className="config-panel-header">
        <h2>Model Configuration</h2>
        <button className="close-btn" onClick={onClose}>
          &times;
        </button>
      </div>

      {error && <div className="config-error">{error}</div>}
      {successMessage && <div className="config-success">{successMessage}</div>}

      {/* Council Profiles Section */}
      <div className="config-section council-profiles-section">
        <div className="section-header-row">
          <h3>Council Profiles</h3>
          <button
            type="button"
            className="save-as-council-btn"
            onClick={() => setShowSaveModal(true)}
            title="Save current model configuration as a custom named council profile"
          >
            + Save as New Council
          </button>
        </div>
        <p className="config-help">
          Switch between predefined expert councils or save your current customized lineup.
        </p>

        <div className="council-cards-grid">
          {savedCouncils.map((c) => {
            const isActive = c.id === activeCouncilId;
            return (
              <div
                key={c.id}
                className={`council-card ${isActive ? 'active' : ''}`}
                onClick={() => handleLoadCouncil(c)}
                title="Click to activate this council profile"
              >
                <div className="council-card-top">
                  <span className="council-card-icon">{c.icon || '🏛️'}</span>
                  <div className="council-card-meta">
                    <span className="council-card-name">{c.name}</span>
                    {c.is_builtin ? (
                      <span className="council-type-tag builtin">Built-in</span>
                    ) : (
                      <span className="council-type-tag custom">Custom</span>
                    )}
                  </div>
                  {isActive && <span className="active-tag">Active</span>}
                  {!c.is_builtin && (
                    <button
                      type="button"
                      className="delete-council-card-btn"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleDeleteCouncil(c);
                      }}
                      title="Delete this custom council"
                    >
                      &times;
                    </button>
                  )}
                </div>
                <p className="council-card-desc">{c.description || `${c.council_models?.length} seats configured`}</p>
                <div className="council-card-seats">
                  <span className="seats-count">{c.council_models?.length} seats</span>
                  <span className="chairman-tag">Chairman: {c.chairman_model?.split('/')[1]?.split('@')[0] || c.chairman_model}</span>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      <div className="config-section">
        <div className="section-header-row">
          <h3>Council Models</h3>
          <span className="section-subtitle">Min 2 required</span>
        </div>
        <p className="config-help">
          Models that participate in Stage 1 responses and Stage 2 peer review.
          Assign dev-agent-kit domain skills to create specialized expert personas.
        </p>

        {/* 1-Click Specialist Presets */}
        <div className="presets-container">
          <span className="presets-label">⚡ Specialist Presets:</span>
          <div className="preset-buttons">
            <button
              type="button"
              className="preset-btn"
              onClick={handleAllQwenPreset}
              title="4-seat specialized Qwen council: Security, Architecture, DevOps, Quality"
            >
              <span className="preset-icon">🛡️</span> All-Qwen Specialists
            </button>
            <button
              type="button"
              className="preset-btn"
              onClick={handleHybridPreset}
              title="Hybrid Local: Qwen (Security & Ops) + Antigravity (Architecture)"
            >
              <span className="preset-icon">⚡</span> Hybrid Local
            </button>
            <button
              type="button"
              className="preset-btn"
              onClick={handleLocalDuoPreset}
              title="Standard dual local council: Antigravity + Qwen"
            >
              <span className="preset-icon">👥</span> Local Duo
            </button>
          </div>
        </div>

        <ul className="model-list">
          {councilModels.map((model, index) => {
            const [, currentSkillId = ''] = model.split('@');
            return (
              <li key={`${model}-${index}`} className="model-item">
                <div className="model-info">
                  <span className="model-index">{index + 1}.</span>
                  {formatModelDisplay(model, availableSkills)}
                  {model === chairmanModel && (
                    <span className="chairman-badge">Chairman</span>
                  )}
                </div>

                <div className="model-controls">
                  <select
                    className="model-skill-select"
                    value={currentSkillId}
                    onChange={(e) => handleModelSkillChange(index, e.target.value)}
                    title="Assign domain skill specialization"
                  >
                    <option value="">No Skill (General)</option>
                    {availableSkills.map((s) => (
                      <option key={s.id} value={s.id}>
                        {s.badge ? `[${s.badge}] ` : ''}{s.title}
                      </option>
                    ))}
                  </select>

                  <div className="model-actions">
                    <button
                      className="move-btn"
                      onClick={() => moveModel(index, -1)}
                      disabled={index === 0}
                      title="Move up"
                    >
                      ▲
                    </button>
                    <button
                      className="move-btn"
                      onClick={() => moveModel(index, 1)}
                      disabled={index === councilModels.length - 1}
                      title="Move down"
                    >
                      ▼
                    </button>
                    <button
                      className="remove-btn"
                      onClick={() => removeModel(index)}
                      title="Remove model"
                    >
                      &times;
                    </button>
                  </div>
                </div>
              </li>
            );
          })}
        </ul>

        <div className="add-model-container">
          <div className="add-model-input-wrapper">
            <input
              type="text"
              className="add-model-input"
              placeholder="Enter model ID (e.g. local/qwen3.6-27b)"
              value={newModelInput}
              onChange={(e) => {
                setNewModelInput(e.target.value);
                setShowModelDropdown(true);
              }}
              onFocus={() => setShowModelDropdown(true)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault();
                  addModel(newModelInput, newModelSkill);
                }
              }}
            />
            {showModelDropdown && newModelInput && filteredModels.length > 0 && (
              <ul className="model-dropdown">
                {filteredModels.slice(0, 8).map((model) => (
                  <li
                    key={model}
                    onClick={() => {
                      setNewModelInput(model);
                      setShowModelDropdown(false);
                    }}
                    className="model-dropdown-item"
                  >
                    {model}
                  </li>
                ))}
              </ul>
            )}
          </div>
          <select
            className="add-model-skill-select"
            value={newModelSkill}
            onChange={(e) => setNewModelSkill(e.target.value)}
            title="Choose initial specialization"
          >
            <option value="">Skill: General</option>
            {availableSkills.map((s) => (
              <option key={s.id} value={s.id}>
                {s.badge ? `[${s.badge}] ` : ''}{s.title}
              </option>
            ))}
          </select>
          <button
            className="add-model-btn"
            onClick={() => addModel(newModelInput, newModelSkill)}
            disabled={!newModelInput.trim()}
          >
            Add Model
          </button>
        </div>

        {availableModels.length > 0 && (
          <div className="suggested-models">
            <span className="suggested-label">Quick add:</span>
            {availableModels
              .slice(0, 6)
              .map((model) => (
                <button
                  key={model}
                  type="button"
                  className="suggested-model-btn"
                  onClick={() => addModel(model, newModelSkill)}
                >
                  + {model.split('/')[1] || model}
                </button>
              ))}
          </div>
        )}
      </div>

      <div className="config-section">
        <h3>Chairman Model</h3>
        <p className="config-help">
          The model that synthesizes the final council verdict in Stage 3.
        </p>

        <select
          className="chairman-select"
          value={chairmanModel}
          onChange={(e) => setChairmanModel(e.target.value)}
        >
          {councilModels.map((model) => {
            const [base, sId] = model.split('@');
            const skill = availableSkills.find((s) => s.id === sId);
            const label = skill ? `${base} [${skill.title}]` : model;
            return (
              <option key={model} value={model}>
                {label}
              </option>
            );
          })}
          <option value="" disabled>
            ─────────────
          </option>
          {availableModels
            .filter((m) => !councilModels.some((cm) => cm.split('@')[0] === m))
            .map((model) => (
              <option key={model} value={model}>
                {model} (not in council)
              </option>
            ))}
        </select>

        <p className="config-note">
          Tip: The chairman can be one of the specialized council members or a separate generalist model.
        </p>
      </div>

      <div className="config-actions">
        <button className="reset-btn" onClick={handleReset} disabled={isSaving}>
          Reset to Defaults
        </button>
        <div className="config-actions-right">
          <button className="cancel-btn" onClick={onClose} disabled={isSaving}>
            Cancel
          </button>
          <button
            className="save-btn"
            onClick={handleSave}
            disabled={isSaving || councilModels.length < 2}
          >
            {isSaving ? 'Saving...' : 'Save Configuration'}
          </button>
        </div>
      </div>

      {/* Save Custom Council Modal */}
      {showSaveModal && (
        <div className="council-modal-overlay" onClick={() => setShowSaveModal(false)}>
          <div className="custom-council-modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h4>Create Custom Council Profile</h4>
              <button className="close-btn" onClick={() => setShowSaveModal(false)}>
                &times;
              </button>
            </div>
            <div className="modal-body">
              <label className="modal-label">Council Profile Name</label>
              <input
                type="text"
                className="modal-input"
                placeholder="e.g. Architecture & Security Council"
                value={newCouncilName}
                onChange={(e) => setNewCouncilName(e.target.value)}
                autoFocus
              />

              <div className="icon-select-row">
                <label className="modal-label">Council Icon / Emoji</label>
                <div className="icon-options">
                  {['🛡️', '⚡', '🏛️', '🔒', '👥', '🎨', '🚀', '🧠', '🔬', '⚙️'].map((ico) => (
                    <button
                      key={ico}
                      type="button"
                      className={`icon-opt-btn ${newCouncilIcon === ico ? 'selected' : ''}`}
                      onClick={() => setNewCouncilIcon(ico)}
                    >
                      {ico}
                    </button>
                  ))}
                </div>
              </div>

              <label className="modal-label">Description (Optional)</label>
              <input
                type="text"
                className="modal-input"
                placeholder="e.g. Focused on OWASP standards and minimalist system design"
                value={newCouncilDesc}
                onChange={(e) => setNewCouncilDesc(e.target.value)}
              />

              <div className="current-roster-preview">
                <span className="roster-preview-title">
                  Configured Seats ({councilModels.length} models):
                </span>
                <div className="roster-pills">
                  {councilModels.map((m, i) => {
                    const [b, s] = m.split('@');
                    return (
                      <span key={i} className="roster-pill">
                        {b.split('/')[1] || b}
                        {s ? ` [${s}]` : ''}
                      </span>
                    );
                  })}
                </div>
              </div>
            </div>
            <div className="modal-actions">
              <button className="cancel-btn" onClick={() => setShowSaveModal(false)}>
                Cancel
              </button>
              <button
                className="save-btn"
                onClick={handleCreateCouncilSubmit}
                disabled={!newCouncilName.trim() || councilModels.length < 2 || isSaving}
              >
                {isSaving ? 'Creating...' : 'Create Council Profile'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
