import React, { useState, useEffect } from 'react';
import { api } from '../api';
import './ConfigPanel.css';

const PROVIDER_PRESETS = [
  {
    id: 'google',
    name: 'Google AI Studio (Gemini)',
    baseUrl: 'https://generativelanguage.googleapis.com/v1beta/openai',
    type: 'remote',
    defaultModel: 'gemini-3.6-flash',
    requiresKey: true,
    keyHint: 'Google AI Studio API Key (from aistudio.google.com)',
  },
  {
    id: 'groq',
    name: 'Groq Cloud',
    baseUrl: 'https://api.groq.com/openai/v1',
    type: 'remote',
    defaultModel: 'llama-3.3-70b-versatile',
    requiresKey: true,
    keyHint: 'Groq API Key (starts with gsk_...)',
  },
  {
    id: 'deepseek',
    name: 'DeepSeek Direct',
    baseUrl: 'https://api.deepseek.com/v1',
    type: 'remote',
    defaultModel: 'deepseek-chat',
    requiresKey: true,
    keyHint: 'DeepSeek API Key (starts with sk-...)',
  },
  {
    id: 'openai',
    name: 'OpenAI Direct',
    baseUrl: 'https://api.openai.com/v1',
    type: 'remote',
    defaultModel: 'gpt-4o-mini',
    requiresKey: true,
    keyHint: 'OpenAI API Key (starts with sk-...)',
  },
  {
    id: 'openrouter',
    name: 'OpenRouter Gateway',
    baseUrl: 'https://openrouter.ai/api/v1',
    type: 'remote',
    defaultModel: 'openrouter/auto',
    requiresKey: true,
    keyHint: 'OpenRouter API Key (starts with sk-or-...)',
  },
  {
    id: 'ollama',
    name: 'Ollama (Local Host)',
    baseUrl: 'http://host.docker.internal:11434/v1',
    type: 'local',
    defaultModel: 'llama3.3:latest',
    requiresKey: false,
    keyHint: 'Runs on host (port 11434). Registered under local/<model> namespace ($0 cost).',
  },
  {
    id: 'lmstudio',
    name: 'LM Studio / vLLM (Local Host)',
    baseUrl: 'http://host.docker.internal:1234/v1',
    type: 'local',
    defaultModel: 'default',
    requiresKey: false,
    keyHint: 'Leave empty if unauthenticated local server',
  },
  {
    id: 'custom',
    name: 'Custom OpenAI-Compatible Endpoint',
    baseUrl: '',
    type: 'remote',
    defaultModel: '',
    requiresKey: false,
    keyHint: 'Enter custom base URL and API key',
  },
];

const getLatencyClass = (latencyMs) => {
  if (latencyMs == null) return '';
  if (latencyMs < 100) return 'status-latency-fast';
  if (latencyMs <= 350) return 'status-latency-medium';
  return 'status-latency-slow';
};

/**
 * Editor for a provider's display label — the variant/effort ("Sonnet 4.5 · high
 * effort") that only the operator knows, shown next to the model in the chat header.
 */
function ProviderLabelEditor({ provider, onSaved }) {
  const [value, setValue] = useState(provider.label || '');
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    setValue(provider.label || '');
  }, [provider.id, provider.label]);

  const save = async () => {
    try {
      setIsSaving(true);
      setError(null);
      await api.setProviderLabel(provider.id, value.trim());
      onSaved?.();
    } catch (err) {
      setError(err.message || 'Failed to save the label');
    } finally {
      setIsSaving(false);
    }
  };

  const dirty = (value.trim() || '') !== (provider.label || '');

  return (
    <div className="provider-label-editor">
      <span className="detail-label">Label:</span>
      <input
        type="text"
        value={value}
        placeholder="e.g. Sonnet 4.5 · high effort"
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={(e) => { if (e.key === 'Enter' && dirty) save(); }}
        maxLength={80}
      />
      <button type="button" onClick={save} disabled={!dirty || isSaving}>
        {isSaving ? 'Saving…' : 'Save'}
      </button>
      {error && <span className="provider-label-error">{error}</span>}
    </div>
  );
}

/**
 * Providers hub: register local/remote OpenAI-compatible endpoints and check their
 * connectivity. `onAddSeat(id, skill)` is optional; when absent the "add to seats"
 * actions are hidden. `onChanged` fires after a provider is saved or deleted.
 */
export default function ProvidersTab({ onChanged, onAddSeat }) {
  const [systemProviders, setSystemProviders] = useState([]);
  const [customProviders, setCustomProviders] = useState([]);
  const [availableSkills, setAvailableSkills] = useState([]);
  const [providerStatuses, setProviderStatuses] = useState({});
  const [isPingingAll, setIsPingingAll] = useState(false);
  const [pingingId, setPingingId] = useState(null);
  const [providerPreset, setProviderPreset] = useState('google');
  const [showAdvancedUrl, setShowAdvancedUrl] = useState(false);
  const [providerName, setProviderName] = useState('Google AI Studio');
  const [providerType, setProviderType] = useState('remote');
  const [providerBaseUrl, setProviderBaseUrl] = useState('');
  const [providerModelId, setProviderModelId] = useState('gemini-3.6-flash');
  const [providerApiKey, setProviderApiKey] = useState('');
  const [providerSkill, setProviderSkill] = useState('');
  const [isTestingProvider, setIsTestingProvider] = useState(false);
  const [providerTestResult, setProviderTestResult] = useState(null);
  const [isSavingProvider, setIsSavingProvider] = useState(false);
  const [isFetchingModels, setIsFetchingModels] = useState(false);
  const [fetchedModels, setFetchedModels] = useState([]);
  const [fetchModelsError, setFetchModelsError] = useState(null);
  const [savedProviderBanner, setSavedProviderBanner] = useState(null);
  const [deletingProviderId, setDeletingProviderId] = useState(null);
  const [error, setError] = useState(null);
  const [successMessage, setSuccessMessage] = useState(null);

  const showNotification = (msg) => {
    setSuccessMessage(msg);
    setTimeout(() => setSuccessMessage(null), 3000);
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

  useEffect(() => {
    loadProviders();
    api.getSkills().then((r) => setAvailableSkills(r.skills || [])).catch(() => {});
    handlePingAll();
  }, []);

  const handlePresetChange = (presetId) => {
    setProviderPreset(presetId);
    setProviderTestResult(null);
    setFetchModelsError(null);
    setFetchedModels([]);
    const preset = PROVIDER_PRESETS.find((p) => p.id === presetId);
    if (preset) {
      setProviderType(preset.type);
      setProviderBaseUrl(preset.baseUrl);
      setProviderModelId(preset.defaultModel);
      if (!providerName || PROVIDER_PRESETS.some((p) => p.name === providerName)) {
        setProviderName(preset.name);
      }
      if (preset.id === 'custom') {
        setShowAdvancedUrl(true);
      }
    }
  };

  const handleProviderTypeChange = (type) => {
    setProviderType(type);
    if (type === 'local' && (!providerBaseUrl || providerBaseUrl.includes('deepseek') || providerBaseUrl.includes('googleapis') || providerBaseUrl.includes('openai'))) {
      setProviderBaseUrl('http://host.docker.internal:11434/v1');
    } else if (type === 'remote' && providerBaseUrl.includes('host.docker.internal')) {
      const preset = PROVIDER_PRESETS.find((p) => p.id === providerPreset);
      setProviderBaseUrl(preset?.baseUrl || 'https://generativelanguage.googleapis.com/v1beta/openai');
    }
  };

  const handleFetchModels = async () => {
    const selectedPreset = PROVIDER_PRESETS.find((p) => p.id === providerPreset);
    const effectiveBaseUrl = providerBaseUrl.trim() || selectedPreset?.baseUrl || '';
    if (!effectiveBaseUrl && providerPreset === 'custom') {
      setFetchModelsError('Please enter a Base URL before fetching models.');
      return;
    }

    try {
      setIsFetchingModels(true);
      setFetchModelsError(null);
      const res = await api.fetchProviderModels({
        base_url: effectiveBaseUrl,
        preset: providerPreset,
        api_key: providerApiKey.trim(),
      });
      if (res.success && res.models && res.models.length > 0) {
        setFetchedModels(res.models);
        if (!providerModelId || !res.models.includes(providerModelId)) {
          setProviderModelId(res.models[0]);
        }
        showNotification(`Discovered ${res.models.length} models.`);
      } else {
        setFetchModelsError(res.error || 'No models returned from endpoint.');
      }
    } catch (err) {
      setFetchModelsError(err.message || 'Failed to fetch models from endpoint.');
    } finally {
      setIsFetchingModels(false);
    }
  };

  const handleTestProvider = async () => {
    const selectedPreset = PROVIDER_PRESETS.find((p) => p.id === providerPreset);
    const effectiveBaseUrl = providerBaseUrl.trim() || selectedPreset?.baseUrl || '';
    if (!effectiveBaseUrl && providerPreset === 'custom') {
      setProviderTestResult({
        success: false,
        error: 'Please enter a Base URL before testing.',
      });
      return;
    }
    if (!providerModelId.trim()) {
      setProviderTestResult({
        success: false,
        error: 'Please enter or select a Model ID before testing.',
      });
      return;
    }

    try {
      setIsTestingProvider(true);
      setProviderTestResult(null);
      const res = await api.testProvider({
        base_url: effectiveBaseUrl,
        preset: providerPreset,
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
    const selectedPreset = PROVIDER_PRESETS.find((p) => p.id === providerPreset);
    const effectiveBaseUrl = providerBaseUrl.trim() || selectedPreset?.baseUrl || '';
    const effectiveName = providerName.trim() || selectedPreset?.name || providerModelId.trim();

    if (!effectiveName || !effectiveBaseUrl || !providerModelId.trim()) {
      setError('Provider Name, Base URL (or Preset), and Model ID are required.');
      return;
    }

    try {
      setIsSavingProvider(true);
      setError(null);
      const res = await api.saveProvider({
        name: effectiveName,
        preset: providerPreset,
        provider_type: providerType,
        base_url: effectiveBaseUrl,
        model_id: providerModelId.trim(),
        api_key: providerApiKey.trim(),
        default_skill: providerSkill || null,
      });

      await loadProviders();
      onChanged?.();
      showNotification(`Saved provider "${res.provider.name}".`);

      // Inline banner offer to add to council (no browser popup window.confirm)
      setSavedProviderBanner({
        id: res.provider.id,
        name: res.provider.name,
        default_skill: providerSkill || null,
      });

      // Reset form but keep preset ready
      setProviderName('');
      setProviderModelId('');
      setProviderApiKey('');
      setFetchedModels([]);
      setProviderTestResult(null);
    } catch (err) {
      setError(err.message || 'Failed to save provider');
    } finally {
      setIsSavingProvider(false);
    }
  };

  const handleDeleteProvider = async (providerId) => {
    if (deletingProviderId !== providerId) {
      setDeletingProviderId(providerId);
      return;
    }
    try {
      await api.deleteProvider(providerId);
      setDeletingProviderId(null);
      await loadProviders();
      onChanged?.();
      showNotification(`Provider deleted.`);
    } catch (err) {
      setError(err.message || 'Failed to delete provider');
    }
  };

  return (
    <>
      {error && <div className="config-error">{error}</div>}
      {successMessage && <div className="config-success">{successMessage}</div>}
  <div className="tab-pane-providers">
    {/* Add Provider Form */}
    <div className="provider-form-card">
      <div className="provider-form-header">
        <div>
          <h3 className="provider-form-title">Add Custom Provider / LLM Endpoint</h3>
          <p className="provider-form-subtitle">
            Register local servers (Ollama, vLLM) or cloud providers (Groq, Gemini, DeepSeek). Added endpoints are immediately available for council seats and chairman selection.
          </p>
        </div>
        <span className="preset-quick-badge">
          Preset: {PROVIDER_PRESETS.find((p) => p.id === providerPreset)?.name || 'Custom'}
        </span>
      </div>

      <form onSubmit={handleSaveProvider}>
        {/* Preset Selection Row */}
        <div className="form-group form-group-full preset-selection-container">
          <label htmlFor="provider-preset">Choose Provider Preset / Service</label>
          <div className="preset-selector-row">
            <select
              id="provider-preset"
              value={providerPreset}
              onChange={(e) => handlePresetChange(e.target.value)}
              className="preset-select"
            >
              {PROVIDER_PRESETS.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name} {p.requiresKey ? '• (API Key)' : '• (Local / Keyless)'}
                </option>
              ))}
            </select>
            <button
              type="button"
              className="advanced-toggle-btn"
              onClick={() => setShowAdvancedUrl(!showAdvancedUrl)}
              title="Toggle custom Base URL configuration"
            >
              {showAdvancedUrl ? 'Hide Base URL' : 'Custom Base URL'}
            </button>
          </div>
          <span className="field-hint">
            {PROVIDER_PRESETS.find((p) => p.id === providerPreset)?.keyHint || 'Select a service preset.'}
            {!showAdvancedUrl && providerPreset !== 'custom' && (
              <span className="preset-url-preview">
                {' '}Base URL is pre-configured (<code>{PROVIDER_PRESETS.find((p) => p.id === providerPreset)?.baseUrl}</code>).
              </span>
            )}
          </span>
        </div>

        <div className="form-row-2col">
          <div className="form-group">
            <label htmlFor="provider-name">Provider / Model Friendly Name *</label>
            <input
              id="provider-name"
              type="text"
              placeholder="e.g. Google AI Studio or Groq Cloud"
              value={providerName}
              onChange={(e) => setProviderName(e.target.value)}
              required
            />
          </div>

          <div className="form-group">
            <label>Provider Type</label>
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

        {/* Base URL (Optional when preset is active) */}
        {(showAdvancedUrl || providerPreset === 'custom') && (
          <div className="form-group form-group-full">
            <label htmlFor="provider-url">
              Base URL (OpenAI-Compatible) {providerPreset !== 'custom' ? '(Optional Overwrite)' : '*'}
            </label>
            <input
              id="provider-url"
              type="text"
              placeholder={PROVIDER_PRESETS.find((p) => p.id === providerPreset)?.baseUrl || 'http://host.docker.internal:11434/v1'}
              value={providerBaseUrl}
              onChange={(e) => setProviderBaseUrl(e.target.value)}
            />
            <span className="field-hint">
              Leave blank to use the standard default endpoint for {PROVIDER_PRESETS.find((p) => p.id === providerPreset)?.name}.
            </span>
          </div>
        )}

        <div className="form-row-2col">
          <div className="form-group">
            <label htmlFor="provider-key">
              API Key {PROVIDER_PRESETS.find((p) => p.id === providerPreset)?.requiresKey ? '*' : '(Optional for Local)'}
            </label>
            <input
              id="provider-key"
              type="password"
              autoComplete="new-password"
              placeholder="Paste API Key here..."
              value={providerApiKey}
              onChange={(e) => setProviderApiKey(e.target.value)}
            />
          </div>

          <div className="form-group">
            <div className="label-with-action">
              <label htmlFor="provider-model">
                Model ID * {fetchedModels.length > 0 && `(${fetchedModels.length} fetched)`}
              </label>
              {fetchedModels.length > 0 && (
                <button
                  type="button"
                  className="text-link-btn"
                  onClick={() => setFetchedModels([])}
                >
                  Manual input
                </button>
              )}
            </div>

            {fetchedModels.length > 0 ? (
              <select
                id="provider-model"
                value={providerModelId}
                onChange={(e) => setProviderModelId(e.target.value)}
                className="model-dropdown-select"
              >
                {fetchedModels.map((m) => (
                  <option key={m} value={m}>{m}</option>
                ))}
              </select>
            ) : (
              <div className="model-input-with-fetch">
                <input
                  id="provider-model"
                  type="text"
                  placeholder="e.g. gemini-3.6-flash or llama-3.3-70b-versatile"
                  value={providerModelId}
                  onChange={(e) => setProviderModelId(e.target.value)}
                  required
                />
              </div>
            )}

            <button
              type="button"
              className="fetch-models-inline-btn"
              onClick={handleFetchModels}
              disabled={isFetchingModels}
              title="Query endpoint for available model list"
            >
              {isFetchingModels ? 'Querying /models...' : 'Fetch Models from Server'}
            </button>
          </div>
        </div>

        {/* Fetch Models Error */}
        {fetchModelsError && (
          <div className="test-result-box failure">
            <span>Model discovery notice: {fetchModelsError}</span>
          </div>
        )}

        <div className="form-row-2col">
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
          <div className="form-group empty-spacer" />
        </div>

        {/* Connection Test Result */}
        {providerTestResult && (
          <div className={`test-result-box ${providerTestResult.success ? 'success' : 'failure'}`}>
            {providerTestResult.success ? (
              <span>{providerTestResult.message}</span>
            ) : (
              <span>{providerTestResult.error}</span>
            )}
          </div>
        )}

        {/* Form Actions */}
        <div className="provider-form-actions">
          <button
            type="button"
            className="test-conn-btn"
            onClick={handleTestProvider}
            disabled={isTestingProvider || !providerModelId}
          >
            {isTestingProvider ? 'Testing Connection...' : 'Test Connection'}
          </button>

          <button
            type="submit"
            className="save-provider-btn"
            disabled={isSavingProvider || !providerModelId}
          >
            {isSavingProvider ? 'Saving...' : 'Save Provider'}
          </button>
        </div>
      </form>
    </div>

    {/* Saved Provider Inline Banner (Replaces window.confirm popup) */}
    {savedProviderBanner && (
      <div className="provider-save-success-banner">
        <div className="banner-badge-icon">OK</div>
        <div className="banner-details">
          <div className="banner-headline">
            Provider <strong>"{savedProviderBanner.name}"</strong> registered successfully!
          </div>
          <div className="banner-subtext">
            Endpoint is verified and active. Would you like to add it as a seat to your council right now?
          </div>
        </div>
        <div className="banner-action-buttons">
          {onAddSeat && (
          <button
            type="button"
            className="banner-add-seat-btn"
            onClick={() => {
              onAddSeat(savedProviderBanner.id, savedProviderBanner.default_skill);
              setSavedProviderBanner(null);
            }}
          >
            + Add as Council Seat
          </button>
          )}
          <button
            type="button"
            className="banner-dismiss-btn"
            onClick={() => setSavedProviderBanner(null)}
          >
            Dismiss
          </button>
        </div>
      </div>
    )}

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
                <ProviderLabelEditor provider={sp} onSaved={loadProviders} />
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
                {onAddSeat && (
                <button
                  type="button"
                  className="provider-action-btn add-to-council"
                  onClick={() => {
                    onAddSeat(sp.id, null);
                  }}
                  title="Add to council deliberation seats"
                >
                  + Add to Seats
                </button>
                )}
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

                  {deletingProviderId === cp.id ? (
                    <div className="delete-confirm-wrap">
                      <button
                        type="button"
                        className="delete-confirm-yes-btn"
                        onClick={() => handleDeleteProvider(cp.id)}
                        title="Confirm permanent deletion"
                      >
                        Confirm Delete
                      </button>
                      <button
                        type="button"
                        className="delete-confirm-no-btn"
                        onClick={() => setDeletingProviderId(null)}
                        title="Cancel"
                      >
                        Cancel
                      </button>
                    </div>
                  ) : (
                    <button
                      type="button"
                      className="delete-provider-btn"
                      onClick={() => handleDeleteProvider(cp.id)}
                      title="Delete custom provider"
                    >
                      &times;
                    </button>
                  )}
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
                  <ProviderLabelEditor provider={cp} onSaved={loadProviders} />
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
                  {onAddSeat && (
                  <button
                    type="button"
                    className="provider-action-btn add-to-council"
                    onClick={() => {
                      onAddSeat(cp.id, cp.default_skill || null);
                    }}
                    title="Add to council deliberation seats"
                  >
                    + Add to Seats
                  </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  </div>
    </>
  );
}
