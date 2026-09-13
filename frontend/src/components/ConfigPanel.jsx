import React, { useState, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import { api } from '../api';
import './ConfigPanel.css';

function formatModelDisplay(model, skillsList = []) {
  const [baseModel, skillId] = model.split('@');
  const parts = baseModel.split('/');
  const skill = skillsList.find((s) => s.id === skillId);

  let modelContent;
  if (parts.length === 2) {
    const isLocal = parts[0] === 'local';
    const isCustom = parts[0] === 'custom';
    const tagClass = isCustom ? 'provider-custom' : isLocal ? 'provider-local' : 'provider-remote';
    modelContent = (
      <span className="config-model-name">
        <span className={`model-provider-tag ${tagClass}`}>
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

const getLatencyClass = (latencyMs) => {
  if (latencyMs == null) return '';
  if (latencyMs < 100) return 'status-latency-fast';
  if (latencyMs <= 350) return 'status-latency-medium';
  return 'status-latency-slow';
};

/**
 * ConfigPanel - Comprehensive Model Studio, Custom Providers Hub & Skills Library
 */
export default function ConfigPanel({
  onClose,
  onCouncilsUpdated,
  initialTab = 'seats',
  initialSkillId = null,
}) {
  const [activeTab, setActiveTab] = useState(initialTab);

  // -------------------------------------------------------------------------
  // 1. Council & Seats State
  // -------------------------------------------------------------------------
  const [councilModels, setCouncilModels] = useState([]);
  const [chairmanModel, setChairmanModel] = useState('');
  const [availableModels, setAvailableModels] = useState([]);
  const [availableSkills, setAvailableSkills] = useState([]);
  const [savedCouncils, setSavedCouncils] = useState([]);
  const [activeCouncilId, setActiveCouncilId] = useState('');
  const [showSaveModal, setShowSaveModal] = useState(false);
  const [newCouncilName, setNewCouncilName] = useState('');
  const [newCouncilDesc, setNewCouncilDesc] = useState('');
  const [newModelInput, setNewModelInput] = useState('');
  const [newModelSkill, setNewModelSkill] = useState('');
  const [showModelDropdown, setShowModelDropdown] = useState(false);

  // -------------------------------------------------------------------------
  // 2. Custom & System Providers State
  // -------------------------------------------------------------------------
  const [systemProviders, setSystemProviders] = useState([]);
  const [customProviders, setCustomProviders] = useState([]);
  const [providerStatuses, setProviderStatuses] = useState({});
  const [isPingingAll, setIsPingingAll] = useState(false);
  const [pingingId, setPingingId] = useState(null);
  const [providerName, setProviderName] = useState('');
  const [providerType, setProviderType] = useState('local');
  const [providerBaseUrl, setProviderBaseUrl] = useState('http://host.docker.internal:11434/v1');
  const [providerModelId, setProviderModelId] = useState('');
  const [providerApiKey, setProviderApiKey] = useState('');
  const [providerSkill, setProviderSkill] = useState('');
  const [isTestingProvider, setIsTestingProvider] = useState(false);
  const [providerTestResult, setProviderTestResult] = useState(null);
  const [isSavingProvider, setIsSavingProvider] = useState(false);

  // -------------------------------------------------------------------------
  // 3. Skills Library State
  // -------------------------------------------------------------------------
  const [selectedSkillId, setSelectedSkillId] = useState(initialSkillId);
  const [skillDetails, setSkillDetails] = useState(null);
  const [isLoadingSkillDetails, setIsLoadingSkillDetails] = useState(false);
  const [skillSearchQuery, setSkillSearchQuery] = useState('');

  // -------------------------------------------------------------------------
  // Common UI State
  // -------------------------------------------------------------------------
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState(null);
  const [successMessage, setSuccessMessage] = useState(null);

  // Load everything on mount
  useEffect(() => {
    loadAllData();
  }, []);

  // Update tab if initialTab prop changes
  useEffect(() => {
    if (initialTab) setActiveTab(initialTab);
  }, [initialTab]);

  // Load skill details when selectedSkillId changes
  useEffect(() => {
    if (!selectedSkillId) return;
    const fetchSkill = async () => {
      try {
        setIsLoadingSkillDetails(true);
        const data = await api.getSkillDetails(selectedSkillId);
        setSkillDetails(data);
      } catch (e) {
        console.error('Failed to load skill details:', e);
      } finally {
        setIsLoadingSkillDetails(false);
      }
    };
    fetchSkill();
  }, [selectedSkillId]);

  // Handle ESC key to close
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  const loadAllData = async () => {
    try {
      setIsLoading(true);
      await Promise.all([
        loadConfig(),
        loadAvailableModels(),
        loadSkills(),
        loadCouncils(),
        loadProviders(),
      ]);
      setError(null);
    } catch (err) {
      setError('Failed to load configuration data');
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  };

  const loadConfig = async () => {
    try {
      const activeCouncil = await api.getActiveCouncil().catch(() => null);
      if (activeCouncil && activeCouncil.council_models?.length) {
        setCouncilModels(activeCouncil.council_models);
        setChairmanModel(activeCouncil.chairman_model);
      } else {
        const config = await api.getConfig();
        setCouncilModels(config.council_models);
        setChairmanModel(config.chairman_model);
      }
    } catch (err) {
      console.error(err);
    }
  };

  const loadAvailableModels = async () => {
    try {
      const result = await api.getAvailableModels();
      setAvailableModels(result.models || []);
    } catch (err) {
      console.error('Failed to load models:', err);
    }
  };

  const loadSkills = async () => {
    try {
      const result = await api.getSkills();
      const list = result.skills || [];
      setAvailableSkills(list);
      if (!selectedSkillId && list.length > 0) {
        setSelectedSkillId(list[0].id);
      }
    } catch (err) {
      console.error('Failed to load skills:', err);
    }
  };

  const loadCouncils = async () => {
    try {
      const res = await api.getCouncils();
      setSavedCouncils(res.councils || []);
      setActiveCouncilId(res.active_council_id || '');
    } catch (err) {
      console.error('Failed to load councils:', err);
    }
  };

  const loadProviders = async () => {
    try {
      const res = await api.getProviders();
      setSystemProviders(res.system_providers || []);
      setCustomProviders(res.custom_providers || []);
    } catch (err) {
      console.error('Failed to load providers:', err);
    }
  };

  const handlePingAll = async () => {
    try {
      setIsPingingAll(true);
      const res = await api.pingAllProviders();
      if (res && res.results) {
        setProviderStatuses((prev) => ({ ...prev, ...res.results }));
      }
    } catch (err) {
      console.error('Failed to ping all providers:', err);
    } finally {
      setIsPingingAll(false);
    }
  };

  const handlePingSingle = async (providerId) => {
    try {
      setPingingId(providerId);
      const res = await api.pingProvider(providerId);
      setProviderStatuses((prev) => ({ ...prev, [providerId]: res }));
    } catch (err) {
      setProviderStatuses((prev) => ({
        ...prev,
        [providerId]: { id: providerId, online: false, error: err.message },
      }));
    } finally {
      setPingingId(null);
    }
  };

  // Automatically check provider connectivity when opening Providers tab
  useEffect(() => {
    if (activeTab === 'providers') {
      handlePingAll();
    }
  }, [activeTab]);

  const showNotification = (msg) => {
    setSuccessMessage(msg);
    setTimeout(() => setSuccessMessage(null), 3500);
  };

  // -------------------------------------------------------------------------
  // Council Operations
  // -------------------------------------------------------------------------
  const handleLoadCouncil = async (council) => {
    setCouncilModels(council.council_models);
    setChairmanModel(council.chairman_model);
    setActiveCouncilId(council.id);
    try {
      await api.activateCouncil(council.id);
      onCouncilsUpdated?.();
      showNotification(`Activated "${council.name}" council profile.`);
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
        icon: '',
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
      showNotification(`Saved and activated "${newCouncil.name}" profile.`);
    } catch (err) {
      setError(err.message || 'Failed to save council profile');
    } finally {
      setIsSaving(false);
    }
  };

  const handleDeleteCouncil = async (councilId, e) => {
    e.stopPropagation();
    if (!window.confirm('Delete this council profile?')) return;
    try {
      await api.deleteCouncil(councilId);
      await loadCouncils();
      onCouncilsUpdated?.();
      showNotification('Council profile deleted.');
    } catch (err) {
      setError(err.message || 'Failed to delete council');
    }
  };

  const handleSaveConfig = async () => {
    if (councilModels.length < 2) {
      setError('At least 2 council models are required');
      return;
    }
    if (!chairmanModel) {
      setError('A chairman model must be selected');
      return;
    }

    try {
      setIsSaving(true);
      setError(null);

      if (activeCouncilId) {
        await api.updateCouncil(activeCouncilId, {
          council_models: councilModels,
          chairman_model: chairmanModel,
        });
      }
      await api.saveConfig({
        council_models: councilModels,
        chairman_model: chairmanModel,
      });

      showNotification('Configuration saved successfully');
      onCouncilsUpdated?.();
    } catch (err) {
      setError(err.message || 'Failed to save configuration');
    } finally {
      setIsSaving(false);
    }
  };

  const handleReset = async () => {
    try {
      setIsSaving(true);
      setError(null);
      const config = await api.resetConfig();
      setCouncilModels(config.council_models);
      setChairmanModel(config.chairman_model);
      showNotification('Configuration reset to defaults');
      onCouncilsUpdated?.();
    } catch (err) {
      setError('Failed to reset configuration');
    } finally {
      setIsSaving(false);
    }
  };

  const handleAddModel = (modelToAdd = null, skillToAttach = null) => {
    const raw = (modelToAdd || newModelInput).trim();
    if (!raw) return;

    const skillId = skillToAttach || newModelSkill;
    const modelString = skillId ? `${raw}@${skillId}` : raw;

    if (!councilModels.includes(modelString)) {
      const updated = [...councilModels, modelString];
      setCouncilModels(updated);
      if (!chairmanModel) {
        setChairmanModel(modelString);
      }
    }
    setNewModelInput('');
    setNewModelSkill('');
    setShowModelDropdown(false);
  };

  const handleRemoveModel = (index) => {
    const modelToRemove = councilModels[index];
    const updated = councilModels.filter((_, i) => i !== index);
    setCouncilModels(updated);
    if (chairmanModel === modelToRemove) {
      setChairmanModel(updated[0] || '');
    }
  };

  const handleSkillChange = (index, newSkillId) => {
    const currentModel = councilModels[index];
    const [baseModel] = currentModel.split('@');
    const newModelString = newSkillId ? `${baseModel}@${newSkillId}` : baseModel;
    const updated = [...councilModels];
    updated[index] = newModelString;
    setCouncilModels(updated);
    if (chairmanModel === currentModel) {
      setChairmanModel(newModelString);
    }
  };

  const handleModelChange = (index, newBaseModel) => {
    const currentModel = councilModels[index];
    const [, currentSkillId] = currentModel.split('@');
    const newModelString = currentSkillId ? `${newBaseModel}@${currentSkillId}` : newBaseModel;
    const updated = [...councilModels];
    updated[index] = newModelString;
    setCouncilModels(updated);
    if (chairmanModel === currentModel) {
      setChairmanModel(newModelString);
    }
  };

  const handleMoveUp = (index) => {
    if (index === 0) return;
    const updated = [...councilModels];
    [updated[index - 1], updated[index]] = [updated[index], updated[index - 1]];
    setCouncilModels(updated);
  };

  const handleMoveDown = (index) => {
    if (index === councilModels.length - 1) return;
    const updated = [...councilModels];
    [updated[index], updated[index + 1]] = [updated[index + 1], updated[index]];
    setCouncilModels(updated);
  };

  const handleJumpToSkill = (skillId) => {
    setSelectedSkillId(skillId);
    setActiveTab('skills');
  };

  // -------------------------------------------------------------------------
  // Provider Operations
  // -------------------------------------------------------------------------
  const handleProviderTypeChange = (type) => {
    setProviderType(type);
    if (type === 'local' && (!providerBaseUrl || providerBaseUrl.includes('deepseek') || providerBaseUrl.includes('openai'))) {
      setProviderBaseUrl('http://host.docker.internal:11434/v1');
    } else if (type === 'remote' && providerBaseUrl.includes('host.docker.internal')) {
      setProviderBaseUrl('https://api.deepseek.com/v1');
    }
  };

  const handleTestProvider = async () => {
    if (!providerBaseUrl || !providerModelId) {
      setProviderTestResult({
        success: false,
        error: 'Please enter both Base URL and Model ID before testing.',
      });
      return;
    }

    try {
      setIsTestingProvider(true);
      setProviderTestResult(null);
      const res = await api.testProvider({
        base_url: providerBaseUrl.trim(),
        model_id: providerModelId.trim(),
        api_key: providerApiKey.trim(),
      });
      setProviderTestResult(res);
    } catch (e) {
      setProviderTestResult({
        success: false,
        error: e.message || 'Connection test failed',
      });
    } finally {
      setIsTestingProvider(false);
    }
  };

  const handleSaveProvider = async (e) => {
    e.preventDefault();
    if (!providerName.trim() || !providerBaseUrl.trim() || !providerModelId.trim()) {
      setError('Provider Name, Base URL, and Model ID are required.');
      return;
    }

    try {
      setIsSavingProvider(true);
      setError(null);
      const res = await api.saveProvider({
        name: providerName.trim(),
        provider_type: providerType,
        base_url: providerBaseUrl.trim(),
        model_id: providerModelId.trim(),
        api_key: providerApiKey.trim(),
        default_skill: providerSkill || null,
      });

      await loadProviders();
      await loadAvailableModels();
      showNotification(`Saved provider "${res.provider.name}".`);

      // Optionally offer to add it to the council immediately
      const customModelId = res.provider.id;
      if (window.confirm(`Provider registered successfully! Would you like to add "${customModelId}" as a seat in your active council?`)) {
        handleAddModel(customModelId, providerSkill || null);
        setActiveTab('seats');
      }

      // Reset form
      setProviderName('');
      setProviderModelId('');
      setProviderApiKey('');
      setProviderTestResult(null);
    } catch (err) {
      setError(err.message || 'Failed to save provider');
    } finally {
      setIsSavingProvider(false);
    }
  };

  const handleDeleteProvider = async (providerId) => {
    if (!window.confirm(`Delete provider "${providerId}"?`)) return;
    try {
      await api.deleteProvider(providerId);
      await loadProviders();
      await loadAvailableModels();
      showNotification(`Provider deleted.`);
    } catch (err) {
      setError(err.message || 'Failed to delete provider');
    }
  };

  // -------------------------------------------------------------------------
  // Skills Library Operations
  // -------------------------------------------------------------------------
  const filteredSkills = availableSkills.filter((s) => {
    if (!skillSearchQuery) return true;
    const q = skillSearchQuery.toLowerCase();
    return (
      s.title?.toLowerCase().includes(q) ||
      s.id?.toLowerCase().includes(q) ||
      s.description?.toLowerCase().includes(q) ||
      s.badge?.toLowerCase().includes(q)
    );
  });

  const handleAssignSkillToActiveCouncil = (skillId) => {
    // Pick the first seat without a skill, or append a seat
    const firstUnassignedIdx = councilModels.findIndex((m) => !m.includes('@'));
    if (firstUnassignedIdx !== -1) {
      handleSkillChange(firstUnassignedIdx, skillId);
      showNotification(`Assigned skill to Seat ${firstUnassignedIdx + 1}`);
    } else {
      // Append with default Qwen or local model
      const base = availableModels[0] || 'local/qwen3.6-27b';
      handleAddModel(base, skillId);
      showNotification(`Added new seat with ${skillId}`);
    }
    setActiveTab('seats');
  };

  return (
    <div className="config-panel-container">
      <div className="config-panel">
        {/* Header */}
        <div className="config-panel-header">
          <div className="header-left">
            <div>
              <h2>Model Studio &amp; Providers</h2>
              <span className="header-sub">Configure council seats, custom LLM providers, and domain skills</span>
            </div>
          </div>
          <button className="close-btn" onClick={onClose} title="Close (Esc)">&times;</button>
        </div>

        {/* Studio Tabs */}
        <div className="studio-tabs">
          <button
            type="button"
            className={`studio-tab-btn ${activeTab === 'seats' ? 'active' : ''}`}
            onClick={() => setActiveTab('seats')}
          >
            <span>Council Seats ({councilModels.length})</span>
          </button>
          <button
            type="button"
            className={`studio-tab-btn ${activeTab === 'providers' ? 'active' : ''}`}
            onClick={() => setActiveTab('providers')}
          >
            <span>Custom Providers ({customProviders.length})</span>
          </button>
          <button
            type="button"
            className={`studio-tab-btn ${activeTab === 'skills' ? 'active' : ''}`}
            onClick={() => setActiveTab('skills')}
          >
            <span>Skills Library ({availableSkills.length})</span>
          </button>
        </div>

        {/* Global Notifications */}
        {error && <div className="config-error">{error}</div>}
        {successMessage && <div className="config-success">{successMessage}</div>}

        {/* Body */}
        <div className="config-panel-body">
          {isLoading ? (
            <div className="config-loading">Loading studio data...</div>
          ) : (
            <>
              {/* =============================================================
                  TAB 1: COUNCIL PROFILES & SEATS
                  ============================================================= */}
              {activeTab === 'seats' && (
                <div className="tab-pane-seats">
                  {/* Saved Councils Bar */}
                  <div className="config-section councils-section">
                    <div className="section-header-row">
                      <h3>Active Council Profile</h3>
                      <button
                        type="button"
                        className="new-council-btn"
                        onClick={() => setShowSaveModal(true)}
                        title="Save current seat configuration as a reusable profile"
                      >
                        + New Profile
                      </button>
                    </div>

                    <div className="councils-grid">
                      {savedCouncils.map((c) => {
                        const isActive = c.id === activeCouncilId;
                        return (
                          <div
                            key={c.id}
                            className={`council-card ${isActive ? 'active' : ''}`}
                            onClick={() => handleLoadCouncil(c)}
                          >
                            <div className="council-card-top">
                              <span className="council-card-name">{c.name}</span>
                              {isActive && <span className="council-active-tag">Active</span>}
                              {!c.is_builtin && (
                                <button
                                  type="button"
                                  className="delete-council-btn"
                                  onClick={(e) => handleDeleteCouncil(c.id, e)}
                                  title="Delete profile"
                                >
                                  &times;
                                </button>
                              )}
                            </div>
                            <p className="council-card-desc">{c.description || `${c.council_models?.length} seats`}</p>
                            <div className="council-card-seats">
                              <span className="seats-count">{c.council_models?.length} seats</span>
                              <span className="chairman-tag">Chairman: {c.chairman_model?.split('/')[1]?.split('@')[0] || c.chairman_model}</span>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>

                  {/* Seat Roster */}
                  <div className="config-section">
                    <div className="section-header-row">
                      <h3>Deliberation Panelists (Seats)</h3>
                      <span className="section-subtitle">Min 2 required (Current: {councilModels.length})</span>
                    </div>
                    <p className="config-help">
                      Assign distinct models and domain skills to each seat. Use the Inspect skill button to inspect operative checklists.
                    </p>

                    <ul className="model-list">
                      {councilModels.map((model, index) => {
                        const [baseModel, currentSkillId = ''] = model.split('@');
                        const isChairman = model === chairmanModel;

                        return (
                          <li key={`${model}-${index}`} className="model-item">
                            <div className="model-item-content">
                              <div className="model-item-primary">
                                <span className="model-index">{index + 1}.</span>
                                <div className="model-selects-row">
                                  {/* Model selector */}
                                  <select
                                    className="seat-model-select"
                                    value={baseModel}
                                    onChange={(e) => handleModelChange(index, e.target.value)}
                                  >
                                    <optgroup label="Custom Providers">
                                      {customProviders.map((cp) => (
                                        <option key={cp.id} value={cp.id}>
                                          {cp.name} ({cp.id})
                                        </option>
                                      ))}
                                    </optgroup>
                                    <optgroup label="Available Models">
                                      {availableModels.map((m) => (
                                        <option key={m} value={m}>{m}</option>
                                      ))}
                                    </optgroup>
                                  </select>

                                  {/* Skill selector */}
                                  <select
                                    className={`seat-skill-select ${currentSkillId ? 'has-skill' : ''}`}
                                    value={currentSkillId}
                                    onChange={(e) => handleSkillChange(index, e.target.value)}
                                  >
                                    <option value="">No Domain Skill (Default)</option>
                                    {availableSkills.map((s) => (
                                      <option key={s.id} value={s.id}>
                                        {s.badge ? `[${s.badge}] ` : ''}{s.title}
                                      </option>
                                    ))}
                                  </select>

                                  {/* View Skill button */}
                                  {currentSkillId && (
                                    <button
                                      type="button"
                                      className="seat-view-skill-btn"
                                      onClick={() => handleJumpToSkill(currentSkillId)}
                                      title={`Read ${currentSkillId} checklist & rules`}
                                    >
                                      Read
                                    </button>
                                  )}
                                </div>
                              </div>

                              <div className="model-item-actions">
                                {isChairman ? (
                                  <span className="chairman-badge">Chairman</span>
                                ) : (
                                  <button
                                    type="button"
                                    className="set-chairman-btn"
                                    onClick={() => setChairmanModel(model)}
                                    title="Set as Chairman (synthesizes Stage 3 verdict)"
                                  >
                                    Make Chairman
                                  </button>
                                )}

                                <div className="reorder-buttons">
                                  <button
                                    type="button"
                                    className="reorder-btn"
                                    onClick={() => handleMoveUp(index)}
                                    disabled={index === 0}
                                    title="Move up"
                                  >
                                    ▲
                                  </button>
                                  <button
                                    type="button"
                                    className="reorder-btn"
                                    onClick={() => handleMoveDown(index)}
                                    disabled={index === councilModels.length - 1}
                                    title="Move down"
                                  >
                                    ▼
                                  </button>
                                </div>

                                <button
                                  type="button"
                                  className="remove-btn"
                                  onClick={() => handleRemoveModel(index)}
                                  disabled={councilModels.length <= 2}
                                  title={councilModels.length <= 2 ? 'Minimum 2 models required' : 'Remove seat'}
                                >
                                  &times;
                                </button>
                              </div>
                            </div>
                          </li>
                        );
                      })}
                    </ul>

                    {/* Add Seat Form */}
                    <div className="add-seat-box">
                      <div className="add-seat-row">
                        <select
                          className="add-seat-model-select"
                          value={newModelInput}
                          onChange={(e) => setNewModelInput(e.target.value)}
                        >
                          <option value="">Select model to add as new seat...</option>
                          {customProviders.length > 0 && (
                            <optgroup label="Custom Registered Providers">
                              {customProviders.map((cp) => (
                                <option key={cp.id} value={cp.id}>
                                  {cp.name} ({cp.id})
                                </option>
                              ))}
                            </optgroup>
                          )}
                          <optgroup label="Available Models">
                            {availableModels.map((m) => (
                              <option key={m} value={m}>{m}</option>
                            ))}
                          </optgroup>
                        </select>

                        <select
                          className="add-seat-skill-select"
                          value={newModelSkill}
                          onChange={(e) => setNewModelSkill(e.target.value)}
                        >
                          <option value="">No Domain Skill (Standard)</option>
                          {availableSkills.map((s) => (
                            <option key={s.id} value={s.id}>
                              {s.badge ? `[${s.badge}] ` : ''}{s.title}
                            </option>
                          ))}
                        </select>

                        <button
                          type="button"
                          className="add-seat-submit-btn"
                          onClick={() => handleAddModel()}
                          disabled={!newModelInput}
                        >
                          + Add Seat
                        </button>
                      </div>
                    </div>

                    {/* Chairman Override Selector */}
                    <div className="chairman-section">
                      <div className="chairman-section-header">
                        <span className="chairman-section-label">Chairman</span>
                        <span className="chairman-current-model">{chairmanModel || 'None selected'}</span>
                      </div>
                      <label htmlFor="chairman-select">Change chairman model:</label>
                      <select
                        id="chairman-select"
                        value={chairmanModel}
                        onChange={(e) => setChairmanModel(e.target.value)}
                      >
                        {/* Current chairman may be external (not one of the seats above) — keep it selectable */}
                        {chairmanModel && !councilModels.includes(chairmanModel) && (
                          <option key={chairmanModel} value={chairmanModel}>
                            {chairmanModel} (external)
                          </option>
                        )}
                        {councilModels.map((model) => (
                          <option key={model} value={model}>
                            {model}
                          </option>
                        ))}
                      </select>
                      <span className="chairman-help">
                        The chairman oversees the deliberation and compiles the final synthesis in Stage 3. It does not have to be one of the seats above.
                      </span>
                    </div>

                    {/* Action Buttons */}
                    <div className="config-actions">
                      <button
                        type="button"
                        className="reset-btn"
                        onClick={handleReset}
                        disabled={isSaving}
                      >
                        Reset to Defaults
                      </button>
                      <button
                        type="button"
                        className="save-btn"
                        onClick={handleSaveConfig}
                        disabled={isSaving || councilModels.length < 2}
                      >
                        {isSaving ? 'Saving...' : 'Save Configuration'}
                      </button>
                    </div>
                  </div>
                </div>
              )}

              {/* =============================================================
                  TAB 2: CUSTOM PROVIDERS (LOCAL & REMOTE)
                  ============================================================= */}
              {activeTab === 'providers' && (
                <div className="tab-pane-providers">
                  {/* Explainer Banner */}
                  <div className="provider-info-banner">
                    <div className="banner-text">
                      <strong>Dynamic OpenAI-Compatible Endpoints</strong>
                      <p>
                        Register any local LLM server (<strong>Ollama</strong>, <strong>vLLM</strong>, <strong>LM Studio</strong>)
                        or cloud provider (<strong>DeepSeek</strong>, <strong>Groq</strong>, <strong>Together</strong>, <strong>OpenAI</strong>).
                        Once added, they are immediately available for council seats and chairman selection.
                      </p>
                    </div>
                  </div>

                  {/* Add Provider Form */}
                  <div className="provider-form-card">
                    <h3 className="provider-form-title">Add Custom Provider / LLM Endpoint</h3>

                    <form onSubmit={handleSaveProvider}>
                      <div className="form-row-2col">
                        <div className="form-group">
                          <label htmlFor="provider-name">Provider / Model Friendly Name *</label>
                          <input
                            id="provider-name"
                            type="text"
                            placeholder="e.g. Ollama LLaMA 3.3 (70B) or DeepSeek Direct"
                            value={providerName}
                            onChange={(e) => setProviderName(e.target.value)}
                            required
                          />
                        </div>

                        <div className="form-group">
                          <label>Provider Type *</label>
                          <div className="type-toggle-group">
                            <button
                              type="button"
                              className={`type-toggle-btn ${providerType === 'local' ? 'active' : ''}`}
                              onClick={() => handleProviderTypeChange('local')}
                            >
                              Local (Ollama / vLLM)
                            </button>
                            <button
                              type="button"
                              className={`type-toggle-btn ${providerType === 'remote' ? 'active' : ''}`}
                              onClick={() => handleProviderTypeChange('remote')}
                            >
                              Remote Cloud API
                            </button>
                          </div>
                        </div>
                      </div>

                      <div className="form-row-2col">
                        <div className="form-group">
                          <label htmlFor="provider-url">Base URL (OpenAI-Compatible) *</label>
                          <input
                            id="provider-url"
                            type="text"
                            placeholder="http://host.docker.internal:11434/v1"
                            value={providerBaseUrl}
                            onChange={(e) => setProviderBaseUrl(e.target.value)}
                            required
                          />
                          <span className="field-hint">
                            For local servers running on your host machine, use <code>http://host.docker.internal:&lt;port&gt;/v1</code>.
                          </span>
                        </div>

                        <div className="form-group">
                          <label htmlFor="provider-model">Model ID (on Server) *</label>
                          <input
                            id="provider-model"
                            type="text"
                            placeholder="e.g. llama3.3:70b or deepseek-chat"
                            value={providerModelId}
                            onChange={(e) => setProviderModelId(e.target.value)}
                            required
                          />
                          <span className="field-hint">The model name sent in the <code>"model"</code> JSON payload.</span>
                        </div>
                      </div>

                      <div className="form-row-2col">
                        <div className="form-group">
                          <label htmlFor="provider-key">API Key (Optional for Local)</label>
                          <input
                            id="provider-key"
                            type="password"
                            autoComplete="new-password"
                            placeholder="sk-... or leave empty for Ollama"
                            value={providerApiKey}
                            onChange={(e) => setProviderApiKey(e.target.value)}
                          />
                        </div>

                        <div className="form-group">
                          <label htmlFor="provider-skill">Default Skill Persona (Optional)</label>
                          <select
                            id="provider-skill"
                            value={providerSkill}
                            onChange={(e) => setProviderSkill(e.target.value)}
                          >
                            <option value="">No default skill</option>
                            {availableSkills.map((s) => (
                              <option key={s.id} value={s.id}>
                                {s.badge ? `[${s.badge}] ` : ''}{s.title}
                              </option>
                            ))}
                          </select>
                        </div>
                      </div>

                      {/* Connection Test Result */}
                      {providerTestResult && (
                        <div className={`test-result-box ${providerTestResult.success ? 'success' : 'failure'}`}>
                          {providerTestResult.success ? (
                            <span>✓ {providerTestResult.message}</span>
                          ) : (
                            <span>✕ {providerTestResult.error}</span>
                          )}
                        </div>
                      )}

                      {/* Form Actions */}
                      <div className="provider-form-actions">
                        <button
                          type="button"
                          className="test-conn-btn"
                          onClick={handleTestProvider}
                          disabled={isTestingProvider || !providerBaseUrl || !providerModelId}
                        >
                          {isTestingProvider ? 'Testing Connection...' : 'Test Connection'}
                        </button>

                        <button
                          type="submit"
                          className="save-provider-btn"
                          disabled={isSavingProvider || !providerName || !providerBaseUrl || !providerModelId}
                        >
                          {isSavingProvider ? 'Saving...' : 'Save Provider'}
                        </button>
                      </div>
                    </form>
                  </div>

                  {/* Top Bar for Provider Management */}
                  <div className="providers-control-bar">
                    <div className="control-bar-info">
                      <span className="control-bar-title">Active LLM Endpoints &amp; Connectivity</span>
                      <span className="control-bar-sub">
                        {systemProviders.length} system (.env) + {customProviders.length} custom endpoints
                      </span>
                    </div>
                    <button
                      type="button"
                      className="ping-all-btn"
                      onClick={handlePingAll}
                      disabled={isPingingAll}
                      title="Test live connection to all registered endpoints"
                    >
                      {isPingingAll ? 'Pinging All Endpoints...' : 'Refresh Status / Ping All'}
                    </button>
                  </div>

                  {/* 1. System Endpoints (.env) */}
                  <div className="registered-providers-section">
                    <div className="section-header-row">
                      <h3>Environment &amp; System Endpoints</h3>
                      <span className="section-subtitle">Configured via .env and local architecture</span>
                    </div>

                    <div className="providers-grid">
                      {systemProviders.map((sp) => {
                        const status = providerStatuses[sp.id];
                        const isPingingThis = pingingId === sp.id || (isPingingAll && !status);

                        return (
                          <div key={sp.id} className="provider-card system-provider-card">
                            <div className="provider-card-top">
                              <div className="provider-card-badges">
                                <span className={`provider-type-tag ${sp.provider_type === 'local' ? 'type-local' : 'type-remote'}`}>
                                  {sp.provider_type === 'local' ? 'LOCAL' : 'REMOTE'}
                                </span>
                                <span className="provider-system-tag">SYSTEM (.ENV)</span>
                              </div>

                              <div className="provider-status-wrap">
                                {isPingingThis ? (
                                  <span className="status-badge status-checking">CHECKING...</span>
                                ) : status ? (
                                  status.online ? (
                                    <span className={`status-badge status-online ${getLatencyClass(status.latency_ms)}`} title={status.message || 'Endpoint reachable'}>
                                      ● ONLINE {status.latency_ms ? `(${status.latency_ms}ms)` : ''}
                                    </span>
                                  ) : (
                                    <span className="status-badge status-offline" title={status.error || 'Offline'}>
                                      ● OFFLINE
                                    </span>
                                  )
                                ) : (
                                  <span className="status-badge status-unchecked">● UNCHECKED</span>
                                )}
                              </div>
                            </div>

                            <div className="provider-card-title-row">
                              <span className="provider-card-name">{sp.name}</span>
                            </div>

                            <div className="provider-card-details">
                              <div className="detail-row">
                                <span className="detail-label">ID:</span>
                                <code className="detail-code">{sp.id}</code>
                              </div>
                              <div className="detail-row">
                                <span className="detail-label">Model:</span>
                                <code>{sp.model_id}</code>
                              </div>
                              <div className="detail-row">
                                <span className="detail-label">Endpoint:</span>
                                <span className="detail-url" title={sp.base_url}>{sp.base_url}</span>
                              </div>
                              {sp.source && (
                                <div className="detail-row">
                                  <span className="detail-label">Source:</span>
                                  <span className="detail-source-badge">{sp.source}</span>
                                </div>
                              )}
                              {status && !status.online && status.error && (
                                <div className="provider-error-pill" title={status.error}>
                                  {status.error}
                                </div>
                              )}
                            </div>

                            <div className="provider-card-actions">
                              <button
                                type="button"
                                className="provider-action-btn ping-single-btn"
                                onClick={() => handlePingSingle(sp.id)}
                                disabled={pingingId === sp.id || isPingingAll}
                                title="Ping this endpoint directly"
                              >
                                {pingingId === sp.id ? 'Pinging...' : 'Ping'}
                              </button>
                              <button
                                type="button"
                                className="provider-action-btn add-to-council"
                                onClick={() => {
                                  handleAddModel(sp.id, null);
                                  setActiveTab('seats');
                                }}
                                title="Add to council deliberation seats"
                              >
                                + Add to Seats
                              </button>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>

                  {/* 2. Custom Registered Providers */}
                  <div className="registered-providers-section">
                    <div className="section-header-row">
                      <h3>Custom Registered Providers</h3>
                      <span className="section-subtitle">{customProviders.length} active custom endpoints</span>
                    </div>

                    {customProviders.length === 0 ? (
                      <div className="no-providers-box">
                        No custom providers registered yet. Use the form above to connect additional Ollama, vLLM, LM Studio, or custom cloud APIs.
                      </div>
                    ) : (
                      <div className="providers-grid">
                        {customProviders.map((cp) => {
                          const status = providerStatuses[cp.id];
                          const isPingingThis = pingingId === cp.id || (isPingingAll && !status);

                          return (
                            <div key={cp.id} className="provider-card">
                              <div className="provider-card-top">
                                <div className="provider-card-badges">
                                  <span className={`provider-type-tag ${cp.provider_type === 'local' ? 'type-local' : 'type-remote'}`}>
                                    {cp.provider_type === 'local' ? 'LOCAL' : 'REMOTE'}
                                  </span>
                                  <span className="provider-custom-tag">CUSTOM</span>
                                </div>

                                <div className="provider-status-wrap">
                                  {isPingingThis ? (
                                    <span className="status-badge status-checking">CHECKING...</span>
                                  ) : status ? (
                                    status.online ? (
                                      <span className={`status-badge status-online ${getLatencyClass(status.latency_ms)}`} title={status.message || 'Endpoint reachable'}>
                                        ● ONLINE {status.latency_ms ? `(${status.latency_ms}ms)` : ''}
                                      </span>
                                    ) : (
                                      <span className="status-badge status-offline" title={status.error || 'Offline'}>
                                        ● OFFLINE
                                      </span>
                                    )
                                  ) : (
                                    <span className="status-badge status-unchecked">● UNCHECKED</span>
                                  )}
                                </div>

                                <button
                                  type="button"
                                  className="delete-provider-btn"
                                  onClick={() => handleDeleteProvider(cp.id)}
                                  title="Delete custom provider"
                                >
                                  &times;
                                </button>
                              </div>

                              <div className="provider-card-title-row">
                                <span className="provider-card-name">{cp.name}</span>
                              </div>

                              <div className="provider-card-details">
                                <div className="detail-row">
                                  <span className="detail-label">ID:</span>
                                  <code className="detail-code">{cp.id}</code>
                                </div>
                                <div className="detail-row">
                                  <span className="detail-label">Model:</span>
                                  <code>{cp.model_id}</code>
                                </div>
                                <div className="detail-row">
                                  <span className="detail-label">Endpoint:</span>
                                  <span className="detail-url" title={cp.base_url}>{cp.base_url}</span>
                                </div>
                                {cp.default_skill && (
                                  <div className="detail-row">
                                    <span className="detail-label">Skill:</span>
                                    <span className="provider-skill-badge">{cp.default_skill}</span>
                                  </div>
                                )}
                                {status && !status.online && status.error && (
                                  <div className="provider-error-pill" title={status.error}>
                                    {status.error}
                                  </div>
                                )}
                              </div>

                              <div className="provider-card-actions">
                                <button
                                  type="button"
                                  className="provider-action-btn ping-single-btn"
                                  onClick={() => handlePingSingle(cp.id)}
                                  disabled={pingingId === cp.id || isPingingAll}
                                  title="Ping this endpoint directly"
                                >
                                  {pingingId === cp.id ? 'Pinging...' : 'Ping'}
                                </button>
                                <button
                                  type="button"
                                  className="provider-action-btn add-to-council"
                                  onClick={() => {
                                    handleAddModel(cp.id, cp.default_skill || null);
                                    setActiveTab('seats');
                                  }}
                                  title="Add to council deliberation seats"
                                >
                                  + Add to Seats
                                </button>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* =============================================================
                  TAB 3: SKILLS LIBRARY & PERSONA INSPECTOR
                  ============================================================= */}
              {activeTab === 'skills' && (
                <div className="tab-pane-skills">
                  <div className="skills-studio-layout">
                    {/* Left: Skills Sidebar */}
                    <aside className="skills-studio-sidebar">
                      <div className="skills-sidebar-search">
                        <input
                          type="text"
                          placeholder="Search skills (e.g. security, testing)..."
                          value={skillSearchQuery}
                          onChange={(e) => setSkillSearchQuery(e.target.value)}
                        />
                      </div>

                      <div className="skills-studio-list">
                        {filteredSkills.map((s) => {
                          const isSelected = s.id === selectedSkillId;
                          return (
                            <button
                              key={s.id}
                              type="button"
                              className={`skills-studio-item ${isSelected ? 'active' : ''}`}
                              onClick={() => setSelectedSkillId(s.id)}
                            >
                              <div className="skill-item-header">
                                <span className="skill-badge-tag">{s.badge || 'SKILL'}</span>
                                <span className="skill-item-title">{s.title}</span>
                              </div>
                              <p className="skill-item-desc">{s.description}</p>
                            </button>
                          );
                        })}
                      </div>
                    </aside>

                    {/* Right: Skill Documentation & Actions */}
                    <main className="skills-studio-content">
                      {isLoadingSkillDetails ? (
                        <div className="skill-loading-box">Loading skill instructions...</div>
                      ) : skillDetails ? (
                        <div className="skill-doc-wrap">
                          <div className="skill-doc-header">
                            <div className="doc-header-titles">
                              <div className="doc-badge-row">
                                <span className="skill-badge-tag">{skillDetails.badge || 'SKILL'}</span>
                                <code>{skillDetails.id}</code>
                              </div>
                              <h2>{skillDetails.title}</h2>
                              <p className="doc-description">{skillDetails.description}</p>
                            </div>

                            <div className="doc-actions-wrap">
                              <button
                                type="button"
                                className="assign-skill-btn"
                                onClick={() => handleAssignSkillToActiveCouncil(skillDetails.id)}
                                title="Attach this skill persona to a council seat"
                              >
                                + Assign to Council
                              </button>
                            </div>
                          </div>

                          {/* Operative Checklist Callout */}
                          {skillDetails.checklist && (
                            <div className="skill-checklist-card">
                              <div className="checklist-card-header">
                                <span>OPERATIVE CHECKLIST &amp; DIRECTIVES</span>
                              </div>
                              <pre className="checklist-card-content">{skillDetails.checklist}</pre>
                            </div>
                          )}

                          {/* Markdown Instructions */}
                          <div className="skill-markdown-view">
                            <ReactMarkdown>{skillDetails.markdown || '*No further documentation.*'}</ReactMarkdown>
                          </div>
                        </div>
                      ) : (
                        <div className="skill-empty-box">Select a domain skill from the left to view instructions.</div>
                      )}
                    </main>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>

      {/* Save Council Modal */}
      {showSaveModal && (
        <div className="save-modal-overlay" onClick={() => setShowSaveModal(false)}>
          <div className="save-modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="save-modal-header">
              <h3>Save as New Council Profile</h3>
              <button className="close-btn" onClick={() => setShowSaveModal(false)}>&times;</button>
            </div>
            <div className="save-modal-body">
              <label>Profile Name *</label>
              <input
                type="text"
                value={newCouncilName}
                onChange={(e) => setNewCouncilName(e.target.value)}
                placeholder="e.g. Security & Hardening Council"
              />

              <label>Description</label>
              <textarea
                value={newCouncilDesc}
                onChange={(e) => setNewCouncilDesc(e.target.value)}
                placeholder="Brief summary of what this council specializes in..."
                rows={3}
              />
            </div>
            <div className="save-modal-footer">
              <button type="button" className="cancel-btn" onClick={() => setShowSaveModal(false)}>Cancel</button>
              <button
                type="button"
                className="confirm-save-btn"
                onClick={handleCreateCouncilSubmit}
                disabled={isSaving || !newCouncilName.trim()}
              >
                {isSaving ? 'Saving...' : 'Save Profile'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
