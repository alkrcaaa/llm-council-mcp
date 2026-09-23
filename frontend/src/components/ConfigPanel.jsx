import React, { useState, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import { api } from '../api';
import { saveAgentProfile, getAgentProfile, fetchAgentProfiles, useAgentProfiles } from '../agentProfiles';
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

const COLOR_SWATCHES = [
  { name: 'Indigo', value: '#6366f1' },
  { name: 'Purple', value: '#8b5cf6' },
  { name: 'Sky Blue', value: '#3b82f6' },
  { name: 'Cyan', value: '#06b6d4' },
  { name: 'Emerald', value: '#10b981' },
  { name: 'Amber', value: '#d97706' },
  { name: 'Orange', value: '#f97316' },
  { name: 'Rose', value: '#f43f5e' },
  { name: 'Slate', value: '#64748b' },
];

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
  // 1b. Chat Roster State (Round Table Group Chat)
  // -------------------------------------------------------------------------
  const [savedRosters, setSavedRosters] = useState([]);
  const [activeRosterId, setActiveRosterId] = useState('');
  const [rosterModels, setRosterModels] = useState([]);
  const [chatSystemPrompt, setChatSystemPrompt] = useState('');
  const [showSaveRosterModal, setShowSaveRosterModal] = useState(false);
  const [newRosterName, setNewRosterName] = useState('');
  const [newRosterDesc, setNewRosterDesc] = useState('');
  const [newRosterModelInput, setNewRosterModelInput] = useState('');
  const [newRosterModelSkill, setNewRosterModelSkill] = useState('');
  const [isSavingRoster, setIsSavingRoster] = useState(false);

  // -------------------------------------------------------------------------
  // 2. Custom & System Providers State
  // -------------------------------------------------------------------------
  const [systemProviders, setSystemProviders] = useState([]);
  const [customProviders, setCustomProviders] = useState([]);
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

  // -------------------------------------------------------------------------
  // 3. Skills Library State
  // -------------------------------------------------------------------------
  const [selectedSkillId, setSelectedSkillId] = useState(initialSkillId);
  const [skillDetails, setSkillDetails] = useState(null);
  const [isLoadingSkillDetails, setIsLoadingSkillDetails] = useState(false);
  const [skillSearchQuery, setSkillSearchQuery] = useState('');
  const [deletingSkillId, setDeletingSkillId] = useState(null);

  // Add Skill (import from GitHub URL or pasted markdown)
  const [showAddSkill, setShowAddSkill] = useState(false);
  const [importMode, setImportMode] = useState('url'); // 'url' | 'paste'
  const [importUrl, setImportUrl] = useState('');
  const [importMarkdown, setImportMarkdown] = useState('');
  const [importPreview, setImportPreview] = useState(null);
  const [importDraftId, setImportDraftId] = useState('');
  const [importDraftMd, setImportDraftMd] = useState('');
  const [importConflict, setImportConflict] = useState(false);
  const [repoDiscovery, setRepoDiscovery] = useState(null);
  const [selectedRepoSkills, setSelectedRepoSkills] = useState([]);
  const [repoSkillFilter, setRepoSkillFilter] = useState('');
  const [bulkJob, setBulkJob] = useState(null);
  const [isDiscoveringRepo, setIsDiscoveringRepo] = useState(false);
  const [isPreviewingImport, setIsPreviewingImport] = useState(false);
  const [isSavingImport, setIsSavingImport] = useState(false);
  const [importError, setImportError] = useState(null);

  // -------------------------------------------------------------------------
  // 4. Agent Personas & Visual Profiles State
  // -------------------------------------------------------------------------
  const agentProfiles = useAgentProfiles();
  const [selectedProfileModel, setSelectedProfileModel] = useState('local/antigravity');
  const [profileDisplayName, setProfileDisplayName] = useState('');
  const [profileColor, setProfileColor] = useState('#6366f1');
  const [profileAvatarUrl, setProfileAvatarUrl] = useState('');
  const [isSavingProfile, setIsSavingProfile] = useState(false);
  const [profileAvatarFileError, setProfileAvatarFileError] = useState(null);

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
      if (e.key !== 'Escape') return;
      if (showAddSkill) setShowAddSkill(false);
      else onClose();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose, showAddSkill]);

  const loadAllData = async () => {
    try {
      setIsLoading(true);
      await Promise.all([
        loadConfig(),
        loadAvailableModels(),
        loadSkills(),
        loadCouncils(),
        loadChatRosters(),
        loadProviders(),
        fetchAgentProfiles(),
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

  const loadChatRosters = async () => {
    try {
      const [rosterRes, settingsRes] = await Promise.all([
        api.getChatRosters().catch(() => ({})),
        api.getChatSettings().catch(() => ({})),
      ]);
      setSavedRosters(rosterRes.rosters || []);
      setActiveRosterId(rosterRes.active_roster_id || '');
      if (settingsRes && settingsRes.models && settingsRes.models.length > 0) {
        setRosterModels(settingsRes.models);
      } else {
        const active = (rosterRes.rosters || []).find((r) => r.id === rosterRes.active_roster_id) || rosterRes.rosters?.[0];
        if (active) {
          setRosterModels(active.models || []);
        }
      }
      setChatSystemPrompt(settingsRes?.system_prompt || '');
    } catch (err) {
      console.error('Failed to load chat rosters and settings:', err);
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

  // -------------------------------------------------------------------------
  // Chat Roster Operations (Round Table)
  // -------------------------------------------------------------------------
  const handleLoadRoster = async (roster) => {
    setActiveRosterId(roster.id);
    setRosterModels([...(roster.models || [])]);
    try {
      await api.activateChatRoster(roster.id);
      showNotification(`Activated chat team "${roster.name}".`);
      onCouncilsUpdated?.();
    } catch (err) {
      console.error('Failed to activate roster:', err);
    }
  };

  const handleRosterModelChange = (index, newBaseModel) => {
    const updated = [...rosterModels];
    const [, skillId] = (updated[index] || '').split('@');
    updated[index] = skillId ? `${newBaseModel}@${skillId}` : newBaseModel;
    setRosterModels(updated);
  };

  const handleRosterSkillChange = (index, newSkillId) => {
    const updated = [...rosterModels];
    const [baseModel] = (updated[index] || '').split('@');
    updated[index] = newSkillId ? `${baseModel}@${newSkillId}` : baseModel;
    setRosterModels(updated);
  };

  const handleRemoveRosterModel = (index) => {
    if (rosterModels.length <= 1) {
      setError('Chat roster requires at least 1 participant.');
      return;
    }
    const updated = rosterModels.filter((_, i) => i !== index);
    setRosterModels(updated);
  };

  const handleAddRosterModel = (model, skillId = null) => {
    const modelWithSkill = skillId ? `${model}@${skillId}` : model;
    setRosterModels((prev) => [...prev, modelWithSkill]);
  };

  const handleSaveRosterChanges = async () => {
    if (rosterModels.length < 1) {
      setError('At least 1 participant is required.');
      return;
    }
    setIsSavingRoster(true);
    try {
      await api.updateChatSettings({
        models: rosterModels,
        system_prompt: chatSystemPrompt,
      });
      if (activeRosterId) {
        await api.updateChatRoster(activeRosterId, { models: rosterModels }).catch(() => {});
      }
      await loadChatRosters();
      showNotification('Round Table settings & user profile saved successfully.');
      onCouncilsUpdated?.();
    } catch (err) {
      setError(err.message || 'Failed to save chat settings');
    } finally {
      setIsSavingRoster(false);
    }
  };

  const handleResetChatBio = async () => {
    try {
      const res = await api.resetChatBio();
      setChatSystemPrompt(res.system_prompt || '');
      showNotification('Loaded English user profile template.');
    } catch (err) {
      setError(err.message || 'Failed to reset bio template');
    }
  };

  const handleCreateNewRoster = async () => {
    if (!newRosterName.trim()) {
      setError('Please enter a team name');
      return;
    }
    if (rosterModels.length < 1) {
      setError('At least 1 participant is required.');
      return;
    }
    setIsSavingRoster(true);
    try {
      const created = await api.createChatRoster({
        name: newRosterName.trim(),
        description: newRosterDesc.trim(),
        models: rosterModels,
      });
      await api.activateChatRoster(created.id);
      await loadChatRosters();
      setShowSaveRosterModal(false);
      setNewRosterName('');
      setNewRosterDesc('');
      showNotification(`Created and activated chat team "${created.name}".`);
      onCouncilsUpdated?.();
    } catch (err) {
      setError(err.message || 'Failed to create chat team');
    } finally {
      setIsSavingRoster(false);
    }
  };

  const handleDeleteRoster = async (rosterId, e) => {
    e?.stopPropagation();
    if (!window.confirm('Are you sure you want to delete this custom chat team?')) return;
    try {
      await api.deleteChatRoster(rosterId);
      await loadChatRosters();
      showNotification('Chat team deleted.');
      onCouncilsUpdated?.();
    } catch (err) {
      setError(err.message || 'Failed to delete chat team');
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
      await api.updateConfig(councilModels, chairmanModel);

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
      await loadAvailableModels();
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

  const resetSkillImport = () => {
    setRepoDiscovery(null);
    setSelectedRepoSkills([]);
    setRepoSkillFilter('');
    setBulkJob(null);
    setImportUrl('');
    setImportMarkdown('');
    setImportPreview(null);
    setImportDraftId('');
    setImportDraftMd('');
    setImportConflict(false);
    setImportError(null);
  };

  const openSkillImport = () => {
    resetSkillImport();
    setImportMode('url');
    setShowAddSkill(true);
  };

  const handlePreviewSkillImport = async () => {
    const isUrlMode = importMode === 'url';
    const value = isUrlMode ? importUrl.trim() : importMarkdown.trim();
    if (!value) {
      setImportError(isUrlMode ? 'Paste a GitHub URL first.' : 'Paste the skill markdown first.');
      return;
    }
    setImportError(null);
    setImportConflict(false);
    setRepoDiscovery(null);
    setBulkJob(null);

    // A collection repository holds many SKILL.md files: let the user pick instead
    // of normalizing its README into one meta-skill.
    if (isUrlMode && /github\.com\//i.test(value)) {
      try {
        setIsDiscoveringRepo(true);
        const discovery = await api.discoverRepoSkills(value);
        if (discovery.count > 1) {
          setImportPreview(null);
          setRepoDiscovery(discovery);
          setSelectedRepoSkills(discovery.skills.map((s) => s.id));
          return;
        }
        if (discovery.install_command) {
          setRepoDiscovery({ ...discovery, skills: [] });
        }
      } catch (err) {
        // Rate limited or not a repository: fall through to the single-skill path.
      } finally {
        setIsDiscoveringRepo(false);
      }
    }

    try {
      setIsPreviewingImport(true);
      const preview = await api.previewSkillImport(
        isUrlMode ? { url: value } : { markdown: importMarkdown }
      );
      setImportPreview(preview);
      setImportDraftId(preview.id || '');
      setImportDraftMd(preview.skill_md || '');
    } catch (err) {
      setImportPreview(null);
      setImportError(err.message || 'Failed to read the skill');
    } finally {
      setIsPreviewingImport(false);
    }
  };

  const toggleRepoSkill = (skillId) => {
    setSelectedRepoSkills((current) =>
      current.includes(skillId) ? current.filter((id) => id !== skillId) : [...current, skillId]
    );
  };

  const handleBulkImport = async (overwrite = false) => {
    const entries = (repoDiscovery?.skills || []).filter((s) => selectedRepoSkills.includes(s.id));
    if (entries.length === 0) {
      setImportError('Select at least one skill.');
      return;
    }
    try {
      setImportError(null);
      const { job } = await api.bulkImportSkills(entries, overwrite);
      setBulkJob({ ...job, total: entries.length });
      pollBulkJob(job.id);
    } catch (err) {
      setImportError(err.message || 'Failed to start the import');
    }
  };

  const pollBulkJob = (jobId) => {
    const tick = async () => {
      try {
        const job = await api.getSkillImportJob(jobId);
        setBulkJob(job);
        if (job.status === 'done' || job.status === 'error') {
          await loadSkills();
          const failed = job.errors?.length || 0;
          const skipped = job.skipped?.length || 0;
          showNotification(
            `Imported ${job.imported.length} skill(s)` +
            (skipped ? `, ${skipped} already present` : '') +
            (failed ? `, ${failed} failed` : '')
          );
          return;
        }
        setTimeout(tick, 800);
      } catch (err) {
        setImportError(err.message || 'Lost track of the import job');
      }
    };
    setTimeout(tick, 500);
  };

  const handleSaveSkillImport = async (overwrite = false) => {
    const skillId = importDraftId.trim();
    if (!skillId || !importDraftMd.trim()) {
      setImportError('A skill id and content are required.');
      return;
    }
    try {
      setIsSavingImport(true);
      setImportError(null);
      const result = await api.importSkill({
        skillId,
        skillMd: importDraftMd,
        origin: importPreview?.origin || null,
        overwrite,
      });
      await loadSkills();
      setSelectedSkillId(result.skill.id);
      setShowAddSkill(false);
      resetSkillImport();
      showNotification(`Skill "${result.skill.id}" added.`);
    } catch (err) {
      setImportConflict(err.status === 409);
      setImportError(err.message || 'Failed to save the skill');
    } finally {
      setIsSavingImport(false);
    }
  };

  const handleDeleteSkill = async (skillId) => {
    if (deletingSkillId !== skillId) {
      setDeletingSkillId(skillId);
      setTimeout(() => setDeletingSkillId((current) => (current === skillId ? null : current)), 4000);
      return;
    }
    try {
      await api.deleteSkill(skillId);
      setDeletingSkillId(null);
      setSkillDetails(null);
      setSelectedSkillId(null);
      await loadSkills();
      showNotification(`Skill "${skillId}" deleted.`);
    } catch (err) {
      setDeletingSkillId(null);
      setError(err.message || 'Failed to delete the skill');
    }
  };

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

  // -------------------------------------------------------------------------
  // 4. Agent Personas & Visual Profiles Handlers
  // -------------------------------------------------------------------------
  useEffect(() => {
    if (!selectedProfileModel) return;
    const p = getAgentProfile(selectedProfileModel);
    setProfileDisplayName(p.displayName || selectedProfileModel.split('/').pop());
    setProfileColor(p.color || '#6366f1');
    setProfileAvatarUrl(p.avatarUrl || '');
    setProfileAvatarFileError(null);
  }, [selectedProfileModel, agentProfiles]);

  const handleOpenCustomizeProfile = (modelId) => {
    const baseModel = (modelId || '').split('@')[0].trim();
    setSelectedProfileModel(baseModel);
    const p = getAgentProfile(baseModel);
    setProfileDisplayName(p.displayName || baseModel.split('/').pop());
    setProfileColor(p.color || '#6366f1');
    setProfileAvatarUrl(p.avatarUrl || '');
    setProfileAvatarFileError(null);
    setActiveTab('profiles');
  };

  const handleAvatarFileUpload = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (file.size > 2 * 1024 * 1024) {
      setProfileAvatarFileError('Görsel boyutu 2MB üzerinde olamaz.');
      return;
    }
    setProfileAvatarFileError(null);
    const reader = new FileReader();
    reader.onload = () => {
      setProfileAvatarUrl(reader.result);
    };
    reader.readAsDataURL(file);
  };

  const handleSaveProfileSubmit = async (e) => {
    if (e) e.preventDefault();
    if (!selectedProfileModel) return;
    setIsSavingProfile(true);
    setError(null);
    try {
      await saveAgentProfile(selectedProfileModel, {
        displayName: profileDisplayName.trim(),
        color: profileColor,
        avatarUrl: profileAvatarUrl.trim(),
      });
      setSuccessMessage(`${profileDisplayName || selectedProfileModel} profili kaydedildi.`);
      setTimeout(() => setSuccessMessage(null), 3000);
    } catch (err) {
      setError(`Profil kaydedilemedi: ${err.message}`);
    } finally {
      setIsSavingProfile(false);
    }
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
            <span>Council Deliberation ({councilModels.length})</span>
          </button>
          <button
            type="button"
            className={`studio-tab-btn ${activeTab === 'chat' ? 'active' : ''}`}
            onClick={() => setActiveTab('chat')}
          >
            <span>Chat Rosters ({rosterModels.length})</span>
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
          <button
            type="button"
            className={`studio-tab-btn ${activeTab === 'profiles' ? 'active' : ''}`}
            onClick={() => setActiveTab('profiles')}
          >
            <span>Agent Personas & Colors</span>
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

                                <button
                                  type="button"
                                  className="seat-profile-btn"
                                  onClick={() => handleOpenCustomizeProfile(baseModel)}
                                  title="Bu modelin profil resmini, rengini ve ismini özelleştir"
                                >
                                  Persona
                                </button>

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
                  TAB 2: CHAT ROSTERS (ROUND TABLE CHAT TEAMS)
                  ============================================================= */}
              {activeTab === 'chat' && (
                <div className="tab-pane-seats">
                  {/* Injected Prompt Set & User Profile Section */}
                  <div className="config-section">
                    <div className="section-header-row">
                      <div>
                        <h3>Injected Prompt Set &amp; User Profile</h3>
                        <span className="section-subtitle">Custom instructions and persona injected before every message turn</span>
                      </div>
                      <div className="prompt-action-btns">
                        <button
                          type="button"
                          className="prompt-template-btn"
                          onClick={handleResetChatBio}
                          title="Vault Hakkımda profilini yükle"
                        >
                          Vault Profilini Yükle
                        </button>
                        <button
                          type="button"
                          className="prompt-clear-btn"
                          onClick={() => setChatSystemPrompt('')}
                          title="Temizle"
                        >
                          Temizle
                        </button>
                      </div>
                    </div>
                    <p className="config-help">
                      User profile and working rules. Council and chat models use this context to tailor their answers to you.
                    </p>

                    <textarea
                      className="chat-system-prompt-textarea"
                      value={chatSystemPrompt}
                      onChange={(e) => setChatSystemPrompt(e.target.value)}
                      rows={7}
                      placeholder="Type custom instructions or paste user profile context in English here (e.g. background, tone preferences, no emoji, concise answers)..."
                    />
                  </div>

                  {/* Participants Roster */}
                  <div className="config-section">
                    <div className="section-header-row">
                      <h3>Round Table Participants</h3>
                      <span className="section-subtitle">Min 1 required (Current: {rosterModels.length})</span>
                    </div>
                    <p className="config-help">
                      Assign models participating in the Round Table chat room. Skills are optional — models converse directly and collaborate without formal deliberation stages or chairman synthesis.
                    </p>

                    <ul className="model-list">
                      {rosterModels.map((model, index) => {
                        const [baseModel, currentSkillId = ''] = model.split('@');

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
                                    onChange={(e) => handleRosterModelChange(index, e.target.value)}
                                  >
                                    <optgroup label="Local Models (dev-agent-kit)">
                                      <option value="local/antigravity">local/antigravity (Antigravity Agent)</option>
                                      <option value="local/claude-code">local/claude-code (Claude Code CLI)</option>
                                      <option value="local/qwen3.6-27b">local/qwen3.6-27b (vLLM 27B)</option>
                                    </optgroup>
                                    {customProviders.length > 0 && (
                                      <optgroup label="Custom Providers">
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

                                  {/* Skill selector */}
                                  <select
                                    className={`seat-skill-select ${currentSkillId ? 'has-skill' : ''}`}
                                    value={currentSkillId}
                                    onChange={(e) => handleRosterSkillChange(index, e.target.value)}
                                  >
                                    <option value="">No Domain Skill (General Chat)</option>
                                    {availableSkills.map((s) => (
                                      <option key={s.id} value={s.id}>
                                        {s.badge ? `[${s.badge}] ` : ''}{s.title}
                                      </option>
                                    ))}
                                  </select>

                                  {currentSkillId && (
                                    <button
                                      type="button"
                                      className="seat-view-skill-btn"
                                      onClick={() => {
                                        setSelectedSkillId(currentSkillId);
                                        setActiveTab('skills');
                                      }}
                                      title="Inspect skill checklist in Skills Library"
                                    >
                                      Inspect
                                    </button>
                                  )}
                                </div>
                              </div>
                            </div>

                            <button
                              type="button"
                              className="seat-profile-btn"
                              onClick={() => handleOpenCustomizeProfile(baseModel)}
                              title="Bu modelin profil resmini, rengini ve ismini özelleştir"
                            >
                              Persona
                            </button>

                            <button
                              type="button"
                              className="remove-btn"
                              onClick={() => handleRemoveRosterModel(index)}
                              title="Remove participant"
                              disabled={rosterModels.length <= 1}
                            >
                              &times;
                            </button>
                          </li>
                        );
                      })}
                    </ul>

                    {/* Add Participant Box */}
                    <div className="add-seat-box">
                      <div className="add-seat-row">
                        <select
                          className="add-seat-model-select"
                          value={newRosterModelInput}
                          onChange={(e) => setNewRosterModelInput(e.target.value)}
                        >
                          <option value="">Select model to add to table...</option>
                          <optgroup label="Local Models (dev-agent-kit)">
                            <option value="local/antigravity">local/antigravity (Antigravity Agent)</option>
                            <option value="local/claude-code">local/claude-code (Claude Code CLI)</option>
                            <option value="local/qwen3.6-27b">local/qwen3.6-27b (vLLM 27B)</option>
                          </optgroup>
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
                          value={newRosterModelSkill}
                          onChange={(e) => setNewRosterModelSkill(e.target.value)}
                        >
                          <option value="">Assign Skill (Optional)</option>
                          {availableSkills.map((s) => (
                            <option key={s.id} value={s.id}>
                              {s.badge ? `[${s.badge}] ` : ''}{s.title}
                            </option>
                          ))}
                        </select>

                        <button
                          type="button"
                          className="add-seat-submit-btn"
                          onClick={() => {
                            if (newRosterModelInput) {
                              handleAddRosterModel(newRosterModelInput, newRosterModelSkill || null);
                              setNewRosterModelInput('');
                              setNewRosterModelSkill('');
                            }
                          }}
                          disabled={!newRosterModelInput}
                        >
                          + Add Participant
                        </button>
                      </div>
                    </div>
                  </div>

                  {/* Actions Footer */}
                  <div className="config-actions">
                    <button
                      type="button"
                      className="save-btn"
                      onClick={handleSaveRosterChanges}
                      disabled={isSavingRoster || rosterModels.length < 1}
                    >
                      {isSavingRoster ? 'Saving...' : 'Save Round Table Settings'}
                    </button>
                  </div>
                </div>
              )}

              {/* =============================================================
                  TAB 3: CUSTOM PROVIDERS (LOCAL & REMOTE)
                  ============================================================= */}
              {activeTab === 'providers' && (
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
                          <span>✕ Model Discovery Notice: {fetchModelsError}</span>
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
                      <div className="banner-badge-icon">✓</div>
                      <div className="banner-details">
                        <div className="banner-headline">
                          Provider <strong>"{savedProviderBanner.name}"</strong> registered successfully!
                        </div>
                        <div className="banner-subtext">
                          Endpoint is verified and active. Would you like to add it as a seat to your council right now?
                        </div>
                      </div>
                      <div className="banner-action-buttons">
                        <button
                          type="button"
                          className="banner-add-seat-btn"
                          onClick={() => {
                            handleAddModel(savedProviderBanner.id, savedProviderBanner.default_skill);
                            setActiveTab('seats');
                            setSavedProviderBanner(null);
                          }}
                        >
                          + Add as Council Seat
                        </button>
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
                        <button
                          type="button"
                          className="add-skill-btn"
                          onClick={openSkillImport}
                          title="Import a skill from a GitHub URL or pasted markdown"
                        >
                          + Add Skill
                        </button>
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
                                {s.source === 'imported' && (
                                  <span className="skill-source-tag" title={s.origin || 'Imported skill'}>IMPORTED</span>
                                )}
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
                              {skillDetails.origin && (
                                <a
                                  className="doc-origin-link"
                                  href={skillDetails.origin}
                                  target="_blank"
                                  rel="noreferrer"
                                >
                                  {skillDetails.origin}
                                </a>
                              )}
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
                              {skillDetails.source === 'imported' && (
                                <button
                                  type="button"
                                  className={`delete-skill-btn ${deletingSkillId === skillDetails.id ? 'confirm' : ''}`}
                                  onClick={() => handleDeleteSkill(skillDetails.id)}
                                  title="Delete this imported skill"
                                >
                                  {deletingSkillId === skillDetails.id ? 'Click again to delete' : 'Delete'}
                                </button>
                              )}
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

                  {showAddSkill && (
                    <div className="skill-import-overlay" onClick={() => setShowAddSkill(false)}>
                      <div className="skill-import-modal" onClick={(e) => e.stopPropagation()}>
                        <div className="skill-import-header">
                          <h3>Add Skill</h3>
                          <button
                            type="button"
                            className="skill-import-close"
                            onClick={() => setShowAddSkill(false)}
                          >
                            ×
                          </button>
                        </div>

                        <div className="skill-import-modes">
                          <button
                            type="button"
                            className={importMode === 'url' ? 'active' : ''}
                            onClick={() => setImportMode('url')}
                          >
                            GitHub URL
                          </button>
                          <button
                            type="button"
                            className={importMode === 'paste' ? 'active' : ''}
                            onClick={() => setImportMode('paste')}
                          >
                            Paste markdown
                          </button>
                        </div>

                        {importMode === 'url' ? (
                          <input
                            type="text"
                            className="skill-import-input"
                            placeholder="https://github.com/owner/repo or .../tree/main/skills/my-skill"
                            value={importUrl}
                            onChange={(e) => setImportUrl(e.target.value)}
                            onKeyDown={(e) => { if (e.key === 'Enter') handlePreviewSkillImport(); }}
                          />
                        ) : (
                          <textarea
                            className="skill-import-textarea"
                            rows={8}
                            placeholder="Paste a README or a complete SKILL.md..."
                            value={importMarkdown}
                            onChange={(e) => setImportMarkdown(e.target.value)}
                            spellCheck={false}
                          />
                        )}

                        <p className="skill-import-hint">
                          A real SKILL.md is imported as-is. Anything else (a README, docs) is
                          rewritten into a SKILL.md with an operative checklist before it is saved.
                        </p>

                        {importError && <div className="skill-import-error">{importError}</div>}

                        <div className="skill-import-actions">
                          <button
                            type="button"
                            className="skill-import-fetch"
                            onClick={handlePreviewSkillImport}
                            disabled={isPreviewingImport || isDiscoveringRepo}
                          >
                            {isDiscoveringRepo ? 'Scanning repo…' : isPreviewingImport ? 'Reading…' : 'Fetch & preview'}
                          </button>
                        </div>

                        {repoDiscovery?.install_command && (
                          <div className="repo-install-hint">
                            <span>Official installer (run it on your own machine):</span>
                            <code>{repoDiscovery.install_command}</code>
                            <button
                              type="button"
                              onClick={() => navigator.clipboard?.writeText(repoDiscovery.install_command)}
                            >
                              Copy
                            </button>
                          </div>
                        )}

                        {repoDiscovery?.skills?.length > 0 && (
                          <div className="repo-skill-picker">
                            <div className="repo-picker-header">
                              <span>
                                <strong>{repoDiscovery.repo}</strong> holds {repoDiscovery.count} skills
                              </span>
                              <div className="repo-picker-bulk">
                                <button
                                  type="button"
                                  onClick={() => setSelectedRepoSkills(repoDiscovery.skills.map((s) => s.id))}
                                >
                                  Select all
                                </button>
                                <button type="button" onClick={() => setSelectedRepoSkills([])}>
                                  Clear
                                </button>
                              </div>
                            </div>

                            <input
                              type="text"
                              className="skill-import-input"
                              placeholder="Filter skills..."
                              value={repoSkillFilter}
                              onChange={(e) => setRepoSkillFilter(e.target.value)}
                            />

                            <div className="repo-skill-list">
                              {repoDiscovery.skills
                                .filter((s) => s.id.includes(repoSkillFilter.trim().toLowerCase()))
                                .map((s) => (
                                  <label key={s.id} className="repo-skill-row">
                                    <input
                                      type="checkbox"
                                      checked={selectedRepoSkills.includes(s.id)}
                                      onChange={() => toggleRepoSkill(s.id)}
                                    />
                                    <span className="repo-skill-id">{s.id}</span>
                                    <span className="repo-skill-path">{s.path}</span>
                                  </label>
                                ))}
                            </div>

                            {bulkJob ? (
                              <div className="bulk-job-status">
                                <div className="bulk-job-bar">
                                  <div
                                    className="bulk-job-fill"
                                    style={{ width: `${Math.round((bulkJob.completed / Math.max(bulkJob.total, 1)) * 100)}%` }}
                                  />
                                </div>
                                <span>
                                  {bulkJob.status === 'done' || bulkJob.status === 'error'
                                    ? `Finished — ${bulkJob.imported?.length || 0} imported` +
                                      (bulkJob.skipped?.length ? `, ${bulkJob.skipped.length} already present` : '') +
                                      (bulkJob.errors?.length ? `, ${bulkJob.errors.length} failed` : '')
                                    : `Importing ${bulkJob.completed}/${bulkJob.total}…`}
                                </span>
                              </div>
                            ) : (
                              <div className="skill-import-actions">
                                <button
                                  type="button"
                                  className="skill-import-save"
                                  onClick={() => handleBulkImport(false)}
                                  disabled={selectedRepoSkills.length === 0}
                                >
                                  Import selected ({selectedRepoSkills.length})
                                </button>
                                <button
                                  type="button"
                                  className="skill-import-replace"
                                  onClick={() => handleBulkImport(true)}
                                  disabled={selectedRepoSkills.length === 0}
                                  title="Replace skills that are already imported"
                                >
                                  Import &amp; replace
                                </button>
                              </div>
                            )}
                          </div>
                        )}

                        {importPreview && (
                          <div className="skill-import-preview">
                            <div className="import-preview-meta">
                              <label>
                                Skill id
                                <input
                                  type="text"
                                  value={importDraftId}
                                  onChange={(e) => setImportDraftId(e.target.value)}
                                  spellCheck={false}
                                />
                              </label>
                              <span className={`import-method-tag method-${importPreview.method}`}>
                                {importPreview.method === 'passthrough'
                                  ? 'SKILL.md found'
                                  : importPreview.method === 'llm'
                                    ? 'normalized by model'
                                    : 'basic conversion'}
                              </span>
                            </div>

                            {importPreview.source_url && (
                              <p className="import-source-url">{importPreview.source_url}</p>
                            )}

                            <textarea
                              className="skill-import-editor"
                              rows={14}
                              value={importDraftMd}
                              onChange={(e) => setImportDraftMd(e.target.value)}
                              spellCheck={false}
                            />

                            <div className="skill-import-actions">
                              <button
                                type="button"
                                className="skill-import-save"
                                onClick={() => handleSaveSkillImport(false)}
                                disabled={isSavingImport || !importDraftId.trim()}
                              >
                                {isSavingImport ? 'Saving…' : 'Save skill'}
                              </button>
                              {importConflict && (
                                <button
                                  type="button"
                                  className="skill-import-replace"
                                  onClick={() => handleSaveSkillImport(true)}
                                  disabled={isSavingImport}
                                >
                                  Replace existing
                                </button>
                              )}
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* =============================================================
                  TAB 5: AGENT PERSONAS & VISUAL STYLING
                  ============================================================= */}
              {activeTab === 'profiles' && (() => {
                const allDistinctModels = Array.from(new Set([
                  'local/antigravity',
                  'local/claude-code',
                  'local/qwen3.6-27b',
                  ...availableModels,
                  ...customProviders.map((cp) => cp.id),
                  ...councilModels.map((s) => (s.includes('@') ? s.split('@')[0] : s)),
                  ...rosterModels.map((s) => (s.includes('@') ? s.split('@')[0] : s)),
                  ...Object.keys(agentProfiles || {}),
                ])).filter(Boolean);

                return (
                  <div className="tab-pane-profiles">
                    <div className="provider-form-header" style={{ marginBottom: '1rem' }}>
                      <div>
                        <h3 className="provider-form-title">Agent Personas &amp; Visual Styling</h3>
                        <p className="provider-form-subtitle">
                          Modellerin Round Table grup sohbetinde ve Deliberation turlarında görünecek profil resmini (avatar), tema rengini ve görünen ismini özelleştirin.
                        </p>
                      </div>
                    </div>

                    <div className="profiles-layout">
                      {/* Left Column: Model List */}
                      <div className="profiles-sidebar">
                        <div style={{ fontSize: '0.78rem', fontWeight: 600, color: '#8b949e', textTransform: 'uppercase', marginBottom: '8px', padding: '0 4px' }}>
                          Modeller ({allDistinctModels.length})
                        </div>
                        {allDistinctModels.map((m) => {
                          const prof = getAgentProfile(m);
                          const isSelected = selectedProfileModel === m;
                          return (
                            <button
                              key={m}
                              type="button"
                              className={`profile-model-item ${isSelected ? 'active' : ''}`}
                              style={{ '--item-color': prof.color }}
                              onClick={() => setSelectedProfileModel(m)}
                            >
                              <div className="profile-item-avatar">
                                {prof.avatarUrl ? (
                                  <img src={prof.avatarUrl} alt={prof.displayName} />
                                ) : (
                                  <span>{prof.initials}</span>
                                )}
                              </div>
                              <div className="profile-item-info">
                                <span className="profile-item-name">{prof.displayName}</span>
                                <span className="profile-item-id">{m}</span>
                              </div>
                            </button>
                          );
                        })}
                      </div>

                      {/* Right Column: Editor */}
                      <div className="profile-editor-card">
                        <div className="profile-editor-header">
                          <h3 style={{ margin: 0, fontSize: '1.1rem', color: '#f0f6fc' }}>
                            {selectedProfileModel}
                          </h3>
                          <p style={{ margin: '4px 0 0', fontSize: '0.8rem', color: '#8b949e' }}>
                            Görünen ismi, sohbet rengini ve avatar görselini güncelleyin.
                          </p>
                        </div>

                        <form onSubmit={handleSaveProfileSubmit} className="profile-form">
                          {/* Display Name */}
                          <div className="form-group" style={{ marginBottom: '1.25rem' }}>
                            <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, color: '#c9d1d9', marginBottom: '6px' }}>
                              Görünen İsim (Display Name)
                            </label>
                            <input
                              type="text"
                              value={profileDisplayName}
                              onChange={(e) => setProfileDisplayName(e.target.value)}
                              placeholder="Örn: Antigravity, Qwen 27B, Claude Code"
                              style={{
                                width: '100%',
                                padding: '8px 12px',
                                background: '#0d1117',
                                border: '1px solid #30363d',
                                borderRadius: '6px',
                                color: '#f0f6fc',
                                fontSize: '0.9rem',
                              }}
                            />
                          </div>

                          {/* Theme Color */}
                          <div className="form-group" style={{ marginBottom: '1.25rem' }}>
                            <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, color: '#c9d1d9', marginBottom: '6px' }}>
                              Tema &amp; Sohbet Rengi
                            </label>
                            <div className="color-swatches-grid">
                              {COLOR_SWATCHES.map((swatch) => (
                                <button
                                  key={swatch.value}
                                  type="button"
                                  className={`swatch-btn ${profileColor.toLowerCase() === swatch.value.toLowerCase() ? 'active' : ''}`}
                                  style={{ backgroundColor: swatch.value }}
                                  onClick={() => setProfileColor(swatch.value)}
                                  title={`${swatch.name} (${swatch.value})`}
                                />
                              ))}
                              <div className="custom-color-picker-wrap">
                                <input
                                  type="color"
                                  value={profileColor.startsWith('#') && profileColor.length === 7 ? profileColor : '#6366f1'}
                                  onChange={(e) => setProfileColor(e.target.value)}
                                  className="color-native-input"
                                  title="Özel renk seç"
                                />
                                <input
                                  type="text"
                                  value={profileColor}
                                  onChange={(e) => setProfileColor(e.target.value)}
                                  className="color-hex-text"
                                  placeholder="#6366f1"
                                  maxLength={7}
                                />
                              </div>
                            </div>
                          </div>

                          {/* Avatar Image */}
                          <div className="form-group" style={{ marginBottom: '1.25rem' }}>
                            <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, color: '#c9d1d9', marginBottom: '6px' }}>
                              Profil Resmi (Avatar)
                            </label>
                            <input
                              type="text"
                              value={profileAvatarUrl}
                              onChange={(e) => setProfileAvatarUrl(e.target.value)}
                              placeholder="Görsel URL'si (https://...) veya yerel dosya seçin"
                              style={{
                                width: '100%',
                                padding: '8px 12px',
                                background: '#0d1117',
                                border: '1px solid #30363d',
                                borderRadius: '6px',
                                color: '#f0f6fc',
                                fontSize: '0.9rem',
                              }}
                            />
                            <div className="avatar-upload-row">
                              <label className="avatar-file-btn">
                                Dosyadan Yükle (PNG/JPG/SVG/WebP)
                                <input
                                  type="file"
                                  accept="image/*"
                                  onChange={handleAvatarFileUpload}
                                  style={{ display: 'none' }}
                                />
                              </label>
                              {profileAvatarUrl && (
                                <button
                                  type="button"
                                  className="avatar-clear-btn"
                                  onClick={() => setProfileAvatarUrl('')}
                                >
                                  Görseli Kaldır
                                </button>
                              )}
                            </div>
                            {profileAvatarFileError && (
                              <span style={{ color: '#f85149', fontSize: '0.78rem', marginTop: '6px', display: 'block' }}>
                                {profileAvatarFileError}
                              </span>
                            )}
                          </div>

                          {/* Live Preview Card */}
                          <div className="profile-preview-card">
                            <span className="profile-preview-label">Canlı Sohbet Önizlemesi</span>
                            <div className="profile-preview-bubble">
                              <div
                                className="profile-item-avatar"
                                style={{
                                  '--item-color': profileColor,
                                  width: '40px',
                                  height: '40px',
                                  fontSize: '13px',
                                }}
                              >
                                {profileAvatarUrl ? (
                                  <img src={profileAvatarUrl} alt="Preview" />
                                ) : (
                                  <span>
                                    {(profileDisplayName || selectedProfileModel)
                                      .replace(/[^a-zA-Z0-9 ]/g, '')
                                      .trim()
                                      .slice(0, 2)
                                      .toUpperCase() || 'AI'}
                                  </span>
                                )}
                              </div>
                              <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', flex: 1 }}>
                                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                  <span style={{ fontWeight: 600, color: profileColor, fontSize: '0.9rem' }}>
                                    {profileDisplayName || selectedProfileModel}
                                  </span>
                                  <span style={{ fontSize: '0.72rem', color: '#8b949e', fontFamily: 'monospace' }}>
                                    {selectedProfileModel}
                                  </span>
                                </div>
                                <div
                                  style={{
                                    background: '#161b22',
                                    border: '1px solid #30363d',
                                    borderRadius: '6px',
                                    padding: '8px 12px',
                                    fontSize: '0.85rem',
                                    color: '#c9d1d9',
                                    lineHeight: '1.4',
                                  }}
                                >
                                  Round Table ve Council deliberasyonunda yanıtlarım bu renkte ve avatarla görünecek.
                                </div>
                              </div>
                            </div>
                          </div>

                          {/* Submit */}
                          <div style={{ marginTop: '1.5rem', display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
                            <button
                              type="submit"
                              className="confirm-save-btn"
                              disabled={isSavingProfile}
                            >
                              {isSavingProfile ? 'Kaydediliyor...' : 'Profili Kaydet'}
                            </button>
                          </div>
                        </form>
                      </div>
                    </div>
                  </div>
                );
              })()}
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

      {/* Save Chat Team Modal */}
      {showSaveRosterModal && (
        <div className="save-modal-overlay" onClick={() => setShowSaveRosterModal(false)}>
          <div className="save-modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="save-modal-header">
              <h3>Save as New Chat Team</h3>
              <button className="close-btn" onClick={() => setShowSaveRosterModal(false)}>&times;</button>
            </div>
            <div className="save-modal-body">
              <label>Team Name *</label>
              <input
                type="text"
                value={newRosterName}
                onChange={(e) => setNewRosterName(e.target.value)}
                placeholder="e.g. Creative Brainstormers"
              />

              <label>Description</label>
              <textarea
                value={newRosterDesc}
                onChange={(e) => setNewRosterDesc(e.target.value)}
                placeholder="Brief summary of this chat team's roles and vibe..."
                rows={3}
              />
            </div>
            <div className="save-modal-footer">
              <button type="button" className="cancel-btn" onClick={() => setShowSaveRosterModal(false)}>Cancel</button>
              <button
                type="button"
                className="confirm-save-btn"
                onClick={handleCreateNewRoster}
                disabled={isSavingRoster || !newRosterName.trim()}
              >
                {isSavingRoster ? 'Saving...' : 'Save Team'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
