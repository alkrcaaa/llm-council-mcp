/**
 * Agent Visual Profiles Store & Hook.
 * Manages custom model names, colors, and avatar pictures across LLM Council.
 */

import { useState, useEffect } from 'react';
import { api } from './api';

let cachedProfiles = {
  'local/antigravity': { display_name: 'Antigravity', color: '#6366f1', avatar_url: '' },
  'local/claude-code': { display_name: 'Claude Code', color: '#d97706', avatar_url: '' },
  'local/qwen3.6-27b': { display_name: 'Qwen 27B', color: '#10b981', avatar_url: '' },
  'custom/gemini-3-6-flash': { display_name: 'Gemini 3.6 Flash', color: '#3b82f6', avatar_url: '' },
  'custom/groq': { display_name: 'Groq Llama 3.3', color: '#f97316', avatar_url: '' },
  'openai/gpt-4o': { display_name: 'GPT-4o', color: '#10a37f', avatar_url: '' },
  'deepseek/deepseek-chat': { display_name: 'DeepSeek', color: '#0ea5e9', avatar_url: '' },
};

const listeners = new Set();

function emitChange() {
  listeners.forEach((fn) => fn(cachedProfiles));
}

export async function fetchAgentProfiles() {
  try {
    const data = await api.getAgentProfiles();
    if (data && typeof data === 'object') {
      cachedProfiles = { ...cachedProfiles, ...data };
      emitChange();
    }
  } catch (err) {
    console.warn('Failed to load agent profiles:', err);
  }
  return cachedProfiles;
}

export async function saveAgentProfile(modelId, { displayName, color, avatarUrl }) {
  const baseModel = (modelId || '').split('@')[0].trim();
  const updated = await api.updateAgentProfile(baseModel, {
    display_name: displayName,
    color: color,
    avatar_url: avatarUrl,
  });
  cachedProfiles = {
    ...cachedProfiles,
    [baseModel]: updated,
  };
  emitChange();
  return updated;
}

export function getAgentProfile(modelId) {
  if (!modelId) {
    return {
      displayName: 'Model',
      color: '#64748b',
      avatarUrl: '',
      initials: 'MO',
    };
  }
  const baseModel = modelId.split('@')[0].trim();
  const prof = cachedProfiles[baseModel] || {};

  // Default display name fallback
  let displayName = prof.display_name;
  if (!displayName) {
    const parts = baseModel.split('/');
    displayName = parts[parts.length - 1] || baseModel;
    if (displayName.includes('antigravity')) displayName = 'Antigravity';
    else if (displayName.includes('claude')) displayName = 'Claude Code';
    else if (displayName.includes('qwen')) displayName = 'Qwen';
    else if (displayName.includes('gemini')) displayName = 'Gemini';
    else if (displayName.includes('groq')) displayName = 'Groq';
  }

  // Default color fallback
  let color = prof.color;
  if (!color) {
    const lower = baseModel.toLowerCase();
    if (lower.includes('antigravity') || lower.includes('agy')) color = '#6366f1';
    else if (lower.includes('claude') || lower.includes('anthropic')) color = '#d97706';
    else if (lower.includes('qwen')) color = '#10b981';
    else if (lower.includes('gemini') || lower.includes('google')) color = '#3b82f6';
    else if (lower.includes('groq') || lower.includes('llama')) color = '#f97316';
    else if (lower.includes('openai') || lower.includes('gpt')) color = '#10a37f';
    else if (lower.includes('deepseek')) color = '#0ea5e9';
    else color = '#8b5cf6';
  }

  // Initials generator
  const cleanWords = displayName.replace(/[^a-zA-Z0-9 ]/g, '').trim().split(/\s+/);
  let initials = 'AI';
  if (cleanWords.length >= 2) {
    initials = (cleanWords[0][0] + cleanWords[1][0]).toUpperCase();
  } else if (cleanWords[0] && cleanWords[0].length >= 2) {
    initials = cleanWords[0].slice(0, 2).toUpperCase();
  } else if (cleanWords[0]) {
    initials = cleanWords[0][0].toUpperCase();
  }

  return {
    displayName,
    color,
    avatarUrl: prof.avatar_url || '',
    initials,
  };
}

export function useAgentProfiles() {
  const [profiles, setProfiles] = useState(cachedProfiles);

  useEffect(() => {
    fetchAgentProfiles();
    const handler = (newProfiles) => setProfiles(newProfiles);
    listeners.add(handler);
    return () => listeners.delete(handler);
  }, []);

  return profiles;
}
