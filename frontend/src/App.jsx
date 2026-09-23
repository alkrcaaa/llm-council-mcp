import { useState, useEffect, useRef } from 'react';
import Sidebar from './components/Sidebar';
import ChatInterface from './components/ChatInterface';
import ConfigPanel from './components/ConfigPanel';
import PerformanceDashboard from './components/PerformanceDashboard';
import ProcessMonitor from './components/ProcessMonitor';
import DeleteConfirmModal from './components/DeleteConfirmModal';
import LoginModal from './components/LoginModal';
import SettingsModal from './components/SettingsModal';
import AccountModal from './components/AccountModal';
import { api } from './api';
import { createStreamDispatcher } from './streamHandler';
import './App.css';

function App() {
  const [currentUser, setCurrentUser] = useState(null);
  const [isAuthChecking, setIsAuthChecking] = useState(true);
  const [conversations, setConversations] = useState([]);
  // Do not force-open the last conversation on fresh load unless user clicks it
  // The open conversation lives in the URL (?c=<id>) so a refresh, back/forward
  // and a copied link all land on the same chat. The bare URL stays a clean landing.
  const [currentConversationId, setCurrentConversationId] = useState(
    () => new URLSearchParams(window.location.search).get('c')
  );
  const [currentConversation, _setCurrentConversation] = useState(null);
  const setCurrentConversation = _setCurrentConversation;
  const [loadingConversationId, setLoadingConversationId] = useState(null);
  const activeStreamRef = useRef({});
  const skipNextLoadRef = useRef(null);
  const isAttachingRef = useRef(false);
  const isLoading = !!loadingConversationId;
  const [systemPrompt, setSystemPrompt] = useState(
    () => localStorage.getItem('systemPrompt') || ''
  );
  const [showSettings, setShowSettings] = useState(
    () => sessionStorage.getItem('showSettings') === 'true'
  );
  const [allTags, setAllTags] = useState([]);
  const [selectedTag, setSelectedTag] = useState(null);
  const [showConfigPanel, setShowConfigPanel] = useState(
    () => sessionStorage.getItem('showConfigPanel') === 'true'
  );
  const [configPanelTab, setConfigPanelTab] = useState(
    () => sessionStorage.getItem('configPanelTab') || 'seats'
  );
  const [showDashboard, setShowDashboard] = useState(false);
  const [selectedSkillIdForModal, setSelectedSkillIdForModal] = useState(null);
  const [conversationToDelete, setConversationToDelete] = useState(null);
  const [isDeletingConversation, setIsDeletingConversation] = useState(false);
  const [showAccountModal, setShowAccountModal] = useState(false);


  // Process Monitor state
  const [showProcessMonitor, setShowProcessMonitor] = useState(false);
  const [processVerbosity, setProcessVerbosity] = useState(
    () => parseInt(localStorage.getItem('processVerbosity') || '0', 10)
  );
  const [processEvents, setProcessEvents] = useState([]);

  // Chain-of-Thought mode state
  const [useCot, setUseCot] = useState(
    () => localStorage.getItem('useCot') === 'true'
  );

  // Multi-Chairman mode state
  const [useMultiChairman, setUseMultiChairman] = useState(
    () => localStorage.getItem('useMultiChairman') === 'true'
  );

  // Weighted Consensus mode state (default true)
  const [useWeightedConsensus, setUseWeightedConsensus] = useState(
    () => localStorage.getItem('useWeightedConsensus') !== 'false'
  );

  // Early Consensus Exit mode state (default false)
  const [useEarlyConsensus, setUseEarlyConsensus] = useState(
    () => localStorage.getItem('useEarlyConsensus') === 'true'
  );

  // Dynamic Model Routing state (default false)
  const [useDynamicRouting, setUseDynamicRouting] = useState(
    () => localStorage.getItem('useDynamicRouting') === 'true'
  );

  // Confidence-Gated Escalation state (default false)
  const [useEscalation, setUseEscalation] = useState(
    () => localStorage.getItem('useEscalation') === 'true'
  );

  // Iterative Refinement state (default false)
  const [useRefinement, setUseRefinement] = useState(
    () => localStorage.getItem('useRefinement') === 'true'
  );
  const [refinementMaxIterations, setRefinementMaxIterations] = useState(
    () => parseInt(localStorage.getItem('refinementMaxIterations') || '2', 10)
  );

  // Adversarial Validation state (default false)
  const [useAdversary, setUseAdversary] = useState(
    () => localStorage.getItem('useAdversary') === 'true'
  );

  // Debate Mode state (default false)
  const [useDebate, setUseDebate] = useState(
    () => localStorage.getItem('useDebate') === 'true'
  );
  const [includeRebuttal, setIncludeRebuttal] = useState(
    () => localStorage.getItem('includeRebuttal') !== 'false'  // default true
  );

  // Sub-Question Decomposition state (default false)
  const [useDecomposition, setUseDecomposition] = useState(
    () => localStorage.getItem('useDecomposition') === 'true'
  );

  // Semantic Response Caching state (default false)
  const [useCache, setUseCache] = useState(
    () => localStorage.getItem('useCache') === 'true'
  );

  // Autonomous Tech Scouting & Candidate Discovery state (default true)
  const [useResearch, setUseResearch] = useState(
    () => localStorage.getItem('useResearch') !== 'false'
  );

  // Council profiles state
  const [councilsList, setCouncilsList] = useState([]);
  const [providerLabels, setProviderLabels] = useState({});
  const [activeCouncil, setActiveCouncil] = useState(null);
  const [showCouncilDropdown, setShowCouncilDropdown] = useState(false);

  // Chat rosters state (Round Table)
  const [chatRostersList, setChatRostersList] = useState([]);
  const [activeChatRoster, setActiveChatRoster] = useState(null);

  // Local workspaces state
  const [workspaces, setWorkspaces] = useState([]);
  const [selectedWorkspace, setSelectedWorkspace] = useState('');

  // Load conversations, tags, councils, chat rosters, and workspaces once signed in
  // (every endpoint is authenticated, so loading before login only yields 401s).
  useEffect(() => {
    if (!currentUser) return;
    loadConversations();
    loadAllTags();
    loadCouncils();
    loadChatRosters();
    loadWorkspaces();
    loadProviderLabels();
  }, [currentUser]);

  // Persist modal open/tab state for this tab session so a page refresh (F5)
  // while inside Configure Models or Settings doesn't drop the user back to
  // the empty landing state.
  useEffect(() => {
    sessionStorage.setItem('showConfigPanel', showConfigPanel.toString());
  }, [showConfigPanel]);

  useEffect(() => {
    sessionStorage.setItem('showSettings', showSettings.toString());
  }, [showSettings]);

  useEffect(() => {
    sessionStorage.setItem('configPanelTab', configPanelTab);
  }, [configPanelTab]);

  useEffect(() => {
    const handleGlobalKeyDown = (e) => {
      if (e.key === 'Escape') {
        if (showCouncilDropdown) setShowCouncilDropdown(false);
        if (showDashboard) setShowDashboard(false);
        if (conversationToDelete && !isDeletingConversation) setConversationToDelete(null);
      }
    };
    window.addEventListener('keydown', handleGlobalKeyDown);
    return () => window.removeEventListener('keydown', handleGlobalKeyDown);
  }, [showCouncilDropdown, showDashboard, conversationToDelete, isDeletingConversation]);

  const loadWorkspaces = async () => {
    try {
      const res = await api.getWorkspaces();
      setWorkspaces(res.workspaces || []);

    } catch (e) {
      console.warn('Failed to load workspaces:', e);
    }
  };

  // Provider display labels (e.g. "Sonnet 4.5 · high effort"), shown next to the
  // seat models in the chat header. Only the provider settings know the variant.
  const loadProviderLabels = async () => {
    try {
      const res = await api.getProviders();
      const labels = {};
      for (const provider of res.providers || []) {
        if (provider.label) labels[provider.id] = provider.label;
      }
      setProviderLabels(labels);
    } catch (e) {
      console.warn('Failed to load provider labels:', e);
    }
  };

  const loadCouncils = async () => {
    try {
      const res = await api.getCouncils();
      const list = res.councils || [];
      setCouncilsList(list);
      const active = list.find((c) => c.id === res.active_council_id) || list[0];
      setActiveCouncil(active);
      if (active) {
        setCurrentConversation((prev) => {
          if (!prev) return null;
          if (prev.council_id === active.id || (!prev.messages || prev.messages.length === 0)) {
            return {
              ...prev,
              council_id: active.id,
              council_name: active.name,
              council_models: active.council_models,
              chairman_model: active.chairman_model,
            };
          }
          return prev;
        });
      }
    } catch (err) {
      console.error('Failed to load councils:', err);
    }
  };

  const handleSelectCouncil = async (council) => {
    setActiveCouncil(council);
    setShowCouncilDropdown(false);
    try {
      await api.activateCouncil(council.id);
      if (currentConversationId) {
        await api.updateConversationCouncil(currentConversationId, council.id);
        setCurrentConversation((prev) => (prev ? {
          ...prev,
          council_id: council.id,
          council_name: council.name,
          council_models: council.council_models,
          chairman_model: council.chairman_model,
        } : null));
        setConversations((prev) => prev.map((c) => (c.id === currentConversationId ? {
          ...c,
          council_id: council.id,
          council_name: council.name,
        } : c)));
      }
    } catch (err) {
      console.error('Failed to activate council:', err);
    }
  };

  const loadChatRosters = async () => {
    try {
      const res = await api.getChatRosters();
      const list = res.rosters || [];
      setChatRostersList(list);
      const active = list.find((r) => r.id === res.active_roster_id) || list[0];
      setActiveChatRoster(active);
      if (active) {
        setCurrentConversation((prev) => {
          if (!prev || prev.conversation_type !== 'roundtable') return prev;
          if (prev.council_id === active.id || (!prev.messages || prev.messages.length === 0)) {
            return {
              ...prev,
              council_id: active.id,
              council_name: active.name,
              council_models: active.models,
              chairman_model: null,
            };
          }
          return prev;
        });
      }
    } catch (err) {
      console.error('Failed to load chat rosters:', err);
    }
  };

  const handleSelectChatRoster = async (roster) => {
    setActiveChatRoster(roster);
    setShowCouncilDropdown(false);
    try {
      await api.activateChatRoster(roster.id);
      if (currentConversationId) {
        await api.updateConversationCouncil(currentConversationId, roster.id);
        setCurrentConversation((prev) => (prev ? {
          ...prev,
          council_id: roster.id,
          council_name: roster.name,
          council_models: roster.models,
          chairman_model: null,
        } : null));
        setConversations((prev) => prev.map((c) => (c.id === currentConversationId ? {
          ...c,
          council_id: roster.id,
          council_name: roster.name,
        } : c)));
      }
    } catch (err) {
      console.error('Failed to switch chat roster:', err);
    }
  };

  // Reload conversations when tag filter changes
  useEffect(() => {
    loadConversations(selectedTag);
  }, [selectedTag]);

  useEffect(() => {
    const url = new URL(window.location.href);
    if ((url.searchParams.get('c') || null) === (currentConversationId || null)) return;
    if (currentConversationId) url.searchParams.set('c', currentConversationId);
    else url.searchParams.delete('c');
    window.history.pushState(null, '', url);
  }, [currentConversationId]);

  useEffect(() => {
    const onPopState = () => {
      const id = new URLSearchParams(window.location.search).get('c');
      setCurrentConversationId(id);
      if (!id) setCurrentConversation(null);
    };
    window.addEventListener('popstate', onPopState);
    return () => window.removeEventListener('popstate', onPopState);
  }, []);

  // Load conversation details when selected
  useEffect(() => {
    if (!currentConversationId) return;
    // A conversation restored from the URL must wait for the auth check;
    // fetching before it would 401 and bounce the user to the landing screen.
    if (!currentUser) return;
    // handleNewConversation already has the freshly-created conversation
    // object and sets it directly; refetching it here raced against the
    // SSE stream that starts right after (landing-composer flow sends the
    // first message immediately) — the GET could resolve with an empty
    // messages: [] and stomp the in-progress assistant placeholder,
    // crashing the next stage event's mutation on messages[length-1].
    if (skipNextLoadRef.current === currentConversationId) {
      skipNextLoadRef.current = null;
      return;
    }
    loadConversation(currentConversationId);
  }, [currentConversationId, currentUser]);

  // Check auth session on startup
  useEffect(() => {
    const checkAuth = async () => {
      try {
        const res = await api.verifyAuth();
        if (res && res.valid) {
          setCurrentUser(res.username || 'admin');
        } else {
          setCurrentUser(null);
        }
      } catch {
        setCurrentUser(null);
      } finally {
        setIsAuthChecking(false);
      }
    };
    checkAuth();
  }, []);

  const loadConversations = async (tag = null) => {
    try {
      const convs = await api.listConversations(tag);
      setConversations(convs);
      // Clean landing: Do not auto-select the last conversation on fresh page visit.
      // The user chooses from the sidebar or starts a new deliberation cleanly.
    } catch (error) {
      console.error('Failed to load conversations:', error);
    }
  };

  const loadAllTags = async () => {
    try {
      const result = await api.getAllTags();
      setAllTags(result.tags);
    } catch (error) {
      console.error('Failed to load tags:', error);
    }
  };

  const loadConversation = async (id) => {
    try {
      const conv = await api.getConversation(id);
      // If this conversation is actively streaming, attach in-flight assistant message
      if (activeStreamRef.current && activeStreamRef.current[id]) {
        conv.messages = [...(conv.messages || []), activeStreamRef.current[id]];
      }
      setCurrentConversation(conv);
      // If conversation has its own bound council or chat roster, sync active state
      if (conv.conversation_type === 'roundtable' && conv.council_id && chatRostersList.length > 0) {
        const matchingRoster = chatRostersList.find((r) => r.id === conv.council_id);
        if (matchingRoster) {
          setActiveChatRoster(matchingRoster);
        }
      } else if (conv.council_id && councilsList.length > 0) {
        const matching = councilsList.find((c) => c.id === conv.council_id);
        if (matching) {
          setActiveCouncil(matching);
        }
      }

      // If this conversation is actively generating in background and not yet attached, reconnect to stream
      if ((conv.status === 'deliberating' || conv.status === 'streaming') && loadingConversationId !== id) {
        attachToActiveStream(id, conv);
      }
    } catch (error) {
      console.error('Failed to load conversation:', error);
      // Stale link (deleted conversation): fall back to the landing screen
      // instead of an empty chat pane.
      setCurrentConversationId((cur) => (cur === id ? null : cur));
    }
  };

  const attachToActiveStream = async (conversationId, convObj = null) => {
    if (!conversationId || isAttachingRef.current) return;
    isAttachingRef.current = true;
    setLoadingConversationId(conversationId);

    try {
      const conv = convObj || (await api.getConversation(conversationId));
      const isRoundTable = conv?.conversation_type === 'roundtable';

      // Ensure assistant placeholder is present for streaming chunks
      _setCurrentConversation((prev) => {
        if (!prev || prev.id !== conversationId) return prev;
        const messages = [...(prev.messages || [])];
        const lastMsg = messages[messages.length - 1];
        if (!lastMsg || lastMsg.role !== 'assistant') {
          messages.push({
            role: 'assistant',
            isRoundTable,
            roundtableStreaming: {},
            roundtableResponses: [],
            stage1: null,
            stage2: null,
            stage3: null,
            loading: {},
          });
          return { ...prev, messages };
        }
        return prev;
      });

      const dispatchStreamEvent = createStreamDispatcher({
        targetConversationId: conversationId,
        _setCurrentConversation,
        activeStreamRef,
        setLoadingConversationId,
        loadConversation,
        loadConversations,
        setProcessEvents,
        selectedTag,
      });

      const connected = await api.subscribeToConversationEvents(conversationId, dispatchStreamEvent);

      if (!connected) {
        setLoadingConversationId(null);
        await loadConversation(conversationId);
      }
    } catch (err) {
      console.warn('Failed to reconnect to active stream:', err);
      setLoadingConversationId(null);
    } finally {
      isAttachingRef.current = false;
    }
  };

  const handleAbortDeliberation = async (conversationId) => {
    const targetId = conversationId || currentConversationId;
    if (!targetId) return;

    try {
      await api.abortDeliberation(targetId);
      if (loadingConversationId === targetId) {
        setLoadingConversationId(null);
      }
      if (activeStreamRef.current) {
        delete activeStreamRef.current[targetId];
      }
      await loadConversation(targetId);
      await loadConversations(selectedTag);
    } catch (err) {
      console.error('Failed to abort deliberation:', err);
    }
  };

  // Background stream recovery (survives F5 / page reload / tab switch):
  // Reconnects directly to the active SSE stream if a conversation is in progress.
  useEffect(() => {
    const isStreamActive = loadingConversationId !== null;
    const isRunning =
      currentConversation?.status === 'deliberating' ||
      currentConversation?.status === 'streaming';

    if (!isStreamActive && isRunning && currentConversationId) {
      attachToActiveStream(currentConversationId, currentConversation);
    }
  }, [currentConversationId, currentConversation?.status, loadingConversationId]);

  // Tab visibility change: quietly sync state when returning to the tab if no stream is active
  useEffect(() => {
    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible' && currentConversationId && !loadingConversationId) {
        loadConversation(currentConversationId);
      }
    };
    document.addEventListener('visibilitychange', handleVisibilityChange);
    return () => document.removeEventListener('visibilitychange', handleVisibilityChange);
  }, [currentConversationId, loadingConversationId]);

  const handleNewConversation = async (councilId = null, initialMessage = null, conversationType = 'deliberation') => {
    setShowSettings(false);
    try {
      const defaultId = conversationType === 'roundtable' ? activeChatRoster?.id : activeCouncil?.id;
      const targetCouncilId = (typeof councilId === 'string' && councilId.trim()) ? councilId.trim() : defaultId;
      const newConv = await api.createConversation(targetCouncilId, conversationType);
      // Clear tag filter when creating new conversation
      setSelectedTag(null);
      setConversations((prev) => [
        {
          id: newConv.id,
          title: newConv.title || 'New Conversation',
          created_at: newConv.created_at,
          tags: [],
          conversation_type: newConv.conversation_type || conversationType,
          council_id: newConv.council_id,
          council_name: newConv.council_name,
          message_count: 0,
        },
        ...prev,
      ]);
      skipNextLoadRef.current = newConv.id;
      setCurrentConversationId(newConv.id);
      setCurrentConversation(newConv);
      if (initialMessage && initialMessage.trim()) {
        // Pass the id explicitly: currentConversationId in this closure is
        // still the pre-update value until the next render.
        handleSendMessage(initialMessage, false, newConv.id);
      }
    } catch (error) {
      console.error('Failed to create conversation:', error);
      if (error.message?.includes('Authentication') || error.message?.includes('401')) {
        api.clearToken();
        setCurrentUser(null);
      }
    }
  };

  const handleDeleteConversation = (conv, e) => {
    if (e) e.stopPropagation();
    let target = conv;
    if (typeof conv === 'string') {
      target = conversations.find((c) => c.id === conv) || { id: conv };
    }
    if (currentConversation && currentConversation.id === target?.id) {
      target = {
        ...target,
        title: currentConversation.title || target?.title || 'New Conversation',
        message_count: currentConversation.messages?.length ?? target?.message_count ?? 0,
      };
    }
    if (!target.title) {
      target = { ...target, title: 'New Conversation' };
    }
    setConversationToDelete(target);
  };

  const handleConfirmDeleteConversation = async () => {
    if (!conversationToDelete) return;
    const id = conversationToDelete.id;
    setIsDeletingConversation(true);
    try {
      await api.deleteConversation(id);
      const updated = conversations.filter((c) => c.id !== id);
      setConversations(updated);
      if (currentConversationId === id) {
        if (updated.length > 0) {
          setCurrentConversationId(updated[0].id);
        } else {
          setCurrentConversationId(null);
          setCurrentConversation(null);
        }
      }
      setConversationToDelete(null);
    } catch (error) {
      console.error('Failed to delete conversation:', error);
    } finally {
      setIsDeletingConversation(false);
    }
  };

  const handleTagsChange = async (tags) => {
    if (!currentConversationId) return;

    try {
      await api.updateTags(currentConversationId, tags);
      // Update current conversation state
      setCurrentConversation((prev) => ({
        ...prev,
        tags,
      }));
      // Reload conversations list to reflect tag changes
      loadConversations(selectedTag);
      // Reload all tags in case new tags were added
      loadAllTags();
    } catch (error) {
      console.error('Failed to update tags:', error);
    }
  };

  const handleTagFilterChange = (tag) => {
    setSelectedTag(tag);
  };

  const handleSelectConversation = (id) => {
    setShowSettings(false);
    setCurrentConversationId(id);
  };

  const handleSystemPromptChange = (value) => {
    setSystemPrompt(value);
    localStorage.setItem('systemPrompt', value);
  };

  const handleVerbosityChange = (value) => {
    setProcessVerbosity(value);
    localStorage.setItem('processVerbosity', value.toString());
  };

  const handleCotChange = (value) => {
    setUseCot(value);
    localStorage.setItem('useCot', value.toString());
  };

  const handleMultiChairmanChange = (value) => {
    setUseMultiChairman(value);
    localStorage.setItem('useMultiChairman', value.toString());
  };

  const handleWeightedConsensusChange = (value) => {
    setUseWeightedConsensus(value);
    localStorage.setItem('useWeightedConsensus', value.toString());
  };

  const handleEarlyConsensusChange = (value) => {
    setUseEarlyConsensus(value);
    localStorage.setItem('useEarlyConsensus', value.toString());
  };

  const handleDynamicRoutingChange = (value) => {
    setUseDynamicRouting(value);
    localStorage.setItem('useDynamicRouting', value.toString());
  };

  const handleEscalationChange = (value) => {
    setUseEscalation(value);
    localStorage.setItem('useEscalation', value.toString());
  };

  const handleRefinementChange = (value) => {
    setUseRefinement(value);
    localStorage.setItem('useRefinement', value.toString());
  };

  const handleRefinementMaxIterationsChange = (value) => {
    setRefinementMaxIterations(value);
    localStorage.setItem('refinementMaxIterations', value.toString());
  };

  const handleAdversaryChange = (value) => {
    setUseAdversary(value);
    localStorage.setItem('useAdversary', value.toString());
  };

  const handleDebateChange = (value) => {
    setUseDebate(value);
    localStorage.setItem('useDebate', value.toString());
  };

  const handleIncludeRebuttalChange = (value) => {
    setIncludeRebuttal(value);
    localStorage.setItem('includeRebuttal', value.toString());
  };

  const handleDecompositionChange = (value) => {
    setUseDecomposition(value);
    localStorage.setItem('useDecomposition', value.toString());
  };

  const handleCacheChange = (value) => {
    setUseCache(value);
    localStorage.setItem('useCache', value.toString());
  };

  const handleResearchChange = (value) => {
    setUseResearch(value);
    localStorage.setItem('useResearch', value.toString());
  };

  const handleSendMessage = async (content, isRetry = false, overrideId = null) => {
    const targetConversationId = overrideId || currentConversationId;
    if (!targetConversationId) return;

    setLoadingConversationId(targetConversationId);

    // Clear process events for new query
    setProcessEvents([]);

    // Scoped updater that only mutates state if the target conversation is currently displayed
    // and caches the in-flight assistant message for seamless tab switching
    const setCurrentConversation = (updater) => {
      let updatedAssistantMsg = null;
      _setCurrentConversation((prev) => {
        // Check the guard BEFORE running the updater: several updaters below
        // mutate messages[messages.length - 1] directly (not a pure spread),
        // so calling one against an unrelated/mismatched `prev` — not just
        // discarding its result — can throw (e.g. an empty conversation's
        // messages[-1] is undefined) and crash the whole render tree.
        if (!prev || prev.id !== targetConversationId) {
          return prev;
        }
        let next;
        try {
          next = typeof updater === 'function' ? updater(prev) : updater;
        } catch (err) {
          console.error('Dropped a malformed stream update instead of crashing:', err);
          return prev;
        }
        if (next && next.messages && next.messages.length > 0) {
          const last = next.messages[next.messages.length - 1];
          if (last && last.role === 'assistant') {
            updatedAssistantMsg = last;
          }
        }
        return next;
      });
      if (updatedAssistantMsg) {
        activeStreamRef.current[targetConversationId] = updatedAssistantMsg;
      }
    };

    try {
      // Optimistically add user message to UI only if not a retry
      if (!isRetry) {
        const userMessage = { role: 'user', content, created_at: new Date().toISOString() };
        setCurrentConversation((prev) => ({
          ...prev,
          messages: [...prev.messages, userMessage],
        }));
      }

      // Create a partial assistant message that will be updated progressively
      const assistantMessage = {
        role: 'assistant',
        stage1: null,
        stage2: null,
        stage3: null,
        metadata: null,
        loading: {
          routing: false,
          stage1: false,
          stage2: false,
          stage3: false,
          tier1: false,
          tier2: false,
          refinement: false,
          adversary: false,
        },
        // Dynamic routing state
        useDynamicRouting: useDynamicRouting,
        routingInfo: null,
        // Multi-chairman streaming state
        useMultiChairman: useMultiChairman,
        multiSyntheses: [],
        selectionStreaming: '',
        isSelecting: false,
        // Escalation state
        useEscalation: useEscalation,
        escalationInfo: null,
        currentTier: null,
        escalated: false,
        // Refinement state
        useRefinement: useRefinement,
        refinementIterations: [],
        refinementStreaming: '',
        refinementCritiques: [],
        isRefining: false,
        currentRefinementIteration: 0,
        refinementMaxIterations: refinementMaxIterations,
        refinementConverged: false,
        // Adversary state
        useAdversary: useAdversary,
        adversaryCritique: '',
        adversaryStreaming: '',
        adversaryRevisionStreaming: '',
        isAdversaryReviewing: false,
        isAdversaryRevising: false,
        adversaryResult: null,
        // Debate state
        useDebate: useDebate,
        includeRebuttal: includeRebuttal,
        isDebating: useDebate,
        debateRound: useDebate ? 1 : 0,
        debatePositions: [],
        debateCritiques: [],
        debateRebuttals: [],
        debateJudgment: '',
        debateJudgmentStreaming: '',
        isJudging: false,
        debateModelToLabel: {},
        debateLabelToModel: {},
        debateNumRounds: includeRebuttal ? 3 : 2,
        // Decomposition state
        useDecomposition: useDecomposition,
        isDecomposing: false,
        decompositionSkipped: false,
        complexityInfo: null,
        subQuestions: [],
        subResults: [],
        currentSubQuestion: -1,
        totalSubQuestions: 0,
        mergeStreaming: '',
        isMerging: false,
        decompositionComplete: false,
        // Cache state
        useCache: useCache,
        cacheChecking: false,
        cacheHit: null,
        cacheStored: null,
      };

      // Add the partial assistant message
      setCurrentConversation((prev) => ({
        ...prev,
        messages: [...prev.messages, assistantMessage],
      }));

      const dispatchStreamEvent = createStreamDispatcher({
        targetConversationId,
        _setCurrentConversation,
        activeStreamRef,
        setLoadingConversationId,
        loadConversation,
        loadConversations,
        setProcessEvents,
        selectedTag,
      });

      // Send message with streaming
      await api.sendMessageStream(
        targetConversationId,
        content,
        dispatchStreamEvent,
        systemPrompt || null,
        processVerbosity,
        useCot,
        useMultiChairman,
        useWeightedConsensus,
        useEarlyConsensus,
        useDynamicRouting,
        useEscalation,
        useRefinement,
        refinementMaxIterations,
        useAdversary,
        useDebate,
        includeRebuttal,
        useDecomposition,
        useCache,
        0.92,
        currentConversation?.council_id || activeCouncil?.id,
        selectedWorkspace || null,
        useResearch
      );
      // Ensure active streaming cache and loading state are cleared on completion
      if (activeStreamRef.current) {
        delete activeStreamRef.current[targetConversationId];
      }
      setLoadingConversationId(null);
      loadConversation(targetConversationId);
      loadConversations(selectedTag);
    } catch (error) {
      console.error('Failed to send message:', error);
      if (activeStreamRef.current) {
        delete activeStreamRef.current[targetConversationId];
      }
      // Remove optimistic messages on error
      setCurrentConversation((prev) => ({
        ...prev,
        messages: isRetry ? prev.messages.slice(0, -1) : prev.messages.slice(0, -2),
      }));
      setLoadingConversationId(null);
    }
  };

  if (!currentUser && !isAuthChecking) {
    return <LoginModal onLoginSuccess={(username) => setCurrentUser(username)} />;
  }

  return (
    <div className="app">
      <Sidebar
        conversations={conversations}
        currentConversationId={currentConversationId}
        loadingConversationId={loadingConversationId}
        onSelectConversation={handleSelectConversation}
        onNewConversation={handleNewConversation}
        onDeleteConversation={handleDeleteConversation}
        allTags={allTags}
        selectedTag={selectedTag}
        onTagFilterChange={handleTagFilterChange}
        activeCouncil={activeCouncil}
        currentUser={currentUser}
        advancedSettingsActive={!!(systemPrompt || useCot || useMultiChairman || useWeightedConsensus || useEarlyConsensus || useDynamicRouting || useEscalation || useRefinement || useAdversary || useDebate || useDecomposition || useCache || useResearch)}
        onOpenDashboard={() => setShowDashboard(true)}
        onOpenTelemetry={() => setShowProcessMonitor((v) => !v)}
        telemetryActive={showProcessMonitor || processVerbosity > 0}
        telemetryLevel={processVerbosity}
        onOpenSettings={() => setShowSettings(true)}
        onOpenConfigPanel={() => {
          const tab = currentConversation?.conversation_type === 'roundtable' ? 'chat' : 'seats';
          setConfigPanelTab(tab);
          setShowConfigPanel(true);
        }}
        onOpenAccount={() => setShowAccountModal(true)}
        onLogout={() => { api.logout(); setCurrentUser(null); }}
      />
      <div className="main-content">
        <div className="settings-bar">
          <div className="settings-bar-row">
            <div className="settings-bar-controls">
              {/* Council / Chat Team Selector Pill & Dropdown */}
              {(() => {
                const isRoundTableMode = currentConversation?.conversation_type === 'roundtable';
                if (isRoundTableMode) {
                  const modelCount = currentConversation?.council_models?.length || activeChatRoster?.models?.length || 3;
                  return (
                    <div className="council-selector-pill-wrap">
                      <button
                        type="button"
                        className="council-selector-pill"
                        onClick={() => {
                          setConfigPanelTab('chat');
                          setShowConfigPanel(true);
                        }}
                        title="Configure Round Table models and injected prompt set"
                      >
                        <span className="council-selector-label">Round Table:</span>
                        <span className="council-selector-name">
                          {modelCount} Models • Setup
                        </span>
                        <svg className="council-selector-caret" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                          <polyline points="6 9 12 15 18 9"></polyline>
                        </svg>
                      </button>
                    </div>
                  );
                }

                return (
                  <div className="council-selector-pill-wrap">
                    <button
                      type="button"
                      className={`council-selector-pill ${showCouncilDropdown ? 'active' : ''}`}
                      onClick={() => setShowCouncilDropdown(!showCouncilDropdown)}
                      title="Select or switch active Council profile"
                    >
                      <span className="council-selector-label">Council:</span>
                      <span className="council-selector-name">
                        {activeCouncil?.name || 'Default'}
                      </span>
                      <svg className="council-selector-caret" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                        <polyline points="6 9 12 15 18 9"></polyline>
                      </svg>
                    </button>

                    {showCouncilDropdown && (
                      <>
                        <div
                          className="council-dropdown-backdrop"
                          onClick={() => setShowCouncilDropdown(false)}
                        />
                        <div className="council-dropdown-menu">
                          <div className="council-dropdown-header">
                            <span>SELECT COUNCIL PROFILE</span>
                            <button
                              type="button"
                              className="council-dropdown-manage-link"
                              onClick={() => {
                                setShowCouncilDropdown(false);
                                setConfigPanelTab('seats');
                                setShowConfigPanel(true);
                              }}
                            >
                              Manage Profiles
                            </button>
                          </div>
                          <div className="council-dropdown-list">
                            {councilsList.map((c) => {
                              const isSelected = activeCouncil?.id === c.id;
                              return (
                                <button
                                  key={c.id}
                                  type="button"
                                  className={`council-dropdown-item ${isSelected ? 'selected' : ''}`}
                                  onClick={() => handleSelectCouncil(c)}
                                >
                                  <div className="council-item-info">
                                    <div className="council-item-name-row">
                                      <span className="council-item-name">{c.name}</span>
                                      {c.is_builtin ? (
                                        <span className="council-type-tag builtin">Built-in</span>
                                      ) : (
                                        <span className="council-type-tag custom">Custom</span>
                                      )}
                                    </div>
                                    <span className="council-item-desc">{c.description || `${c.council_models?.length} seats`}</span>
                                  </div>
                                  {isSelected && (
                                    <svg className="council-item-check" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                                      <polyline points="20 6 9 17 4 12"></polyline>
                                    </svg>
                                  )}
                                </button>
                              );
                            })}
                          </div>
                          <div className="council-dropdown-footer">
                            <button
                              type="button"
                              className="council-dropdown-create-btn"
                              onClick={() => {
                                setShowCouncilDropdown(false);
                                setConfigPanelTab('seats');
                                setShowConfigPanel(true);
                              }}
                            >
                              + New Custom Council
                            </button>
                          </div>
                        </div>
                      </>
                    )}
                  </div>
                );
              })()}

              {/* Workspace Context Selector */}
              {workspaces.length > 0 && (
                <div className="workspace-selector-pill-wrap">
                  <select
                    className="workspace-selector-select"
                    value={selectedWorkspace}
                    onChange={(e) => setSelectedWorkspace(e.target.value)}
                    title="Target local workspace project to evaluate against (auto-detected if blank)"
                  >
                    <option value="">Auto Workspace</option>
                    {workspaces.map((ws) => (
                      <option key={ws.name} value={ws.name}>
                        {ws.name}
                      </option>
                    ))}
                  </select>
                </div>
              )}

            </div>
          </div>
        </div>
        <ChatInterface
          conversation={currentConversation}
          activeCouncil={activeCouncil}
          activeChatRoster={activeChatRoster}
          currentUser={currentUser}
          onSendMessage={handleSendMessage}
          onNewConversation={handleNewConversation}
          isLoading={loadingConversationId === currentConversationId}
          isDeliberating={loadingConversationId === currentConversationId || currentConversation?.status === 'deliberating'}
          onAbortDeliberation={handleAbortDeliberation}
          onTagsChange={handleTagsChange}
          providerLabels={providerLabels}
          onInspectSkill={(skillId) => {
            setSelectedSkillIdForModal(skillId);
            setConfigPanelTab('skills');
            setShowConfigPanel(true);
          }}
        />
      </div>

      {/* Model Studio, Custom Providers & Skills Hub */}
      {showConfigPanel && (
        <ConfigPanel
          onClose={() => setShowConfigPanel(false)}
          onCouncilsUpdated={() => {
            loadCouncils();
            loadChatRosters();
            loadProviderLabels();
          }}
          initialTab={configPanelTab}
          initialSkillId={selectedSkillIdForModal}
        />
      )}

      {/* Performance Dashboard */}
      {showDashboard && (
        <>
          <div
            className="config-overlay"
            onClick={() => setShowDashboard(false)}
          />
          <PerformanceDashboard onClose={() => setShowDashboard(false)} />
        </>
      )}

      {/* In-App Delete Conversation Confirmation Modal */}
      {conversationToDelete && (
        <DeleteConfirmModal
          conversation={conversationToDelete}
          onConfirm={handleConfirmDeleteConversation}
          onCancel={() => !isDeletingConversation && setConversationToDelete(null)}
          isDeleting={isDeletingConversation}
        />
      )}

      {/* Process Monitor Side Panel */}
      <ProcessMonitor
        events={processEvents}
        verbosity={processVerbosity}
        onVerbosityChange={handleVerbosityChange}
        isOpen={showProcessMonitor}
        onToggle={() => setShowProcessMonitor(!showProcessMonitor)}
      />

      {/* Account / Password Modal */}
      <AccountModal
        isOpen={showAccountModal}
        onClose={() => setShowAccountModal(false)}
        currentUser={currentUser || 'admin'}
      />


      {/* Deliberation Settings Modal */}
      <SettingsModal
        isOpen={showSettings}
        onClose={() => setShowSettings(false)}
        systemPrompt={systemPrompt}
        onSystemPromptChange={handleSystemPromptChange}
        useCot={useCot}
        onCotChange={handleCotChange}
        useMultiChairman={useMultiChairman}
        onMultiChairmanChange={handleMultiChairmanChange}
        useWeightedConsensus={useWeightedConsensus}
        onWeightedConsensusChange={handleWeightedConsensusChange}
        useEarlyConsensus={useEarlyConsensus}
        onEarlyConsensusChange={handleEarlyConsensusChange}
        useDynamicRouting={useDynamicRouting}
        onDynamicRoutingChange={handleDynamicRoutingChange}
        useEscalation={useEscalation}
        onEscalationChange={handleEscalationChange}
        useRefinement={useRefinement}
        onRefinementChange={handleRefinementChange}
        refinementMaxIterations={refinementMaxIterations}
        onRefinementMaxIterationsChange={handleRefinementMaxIterationsChange}
        useAdversary={useAdversary}
        onAdversaryChange={handleAdversaryChange}
        useDebate={useDebate}
        onDebateChange={handleDebateChange}
        includeRebuttal={includeRebuttal}
        onIncludeRebuttalChange={handleIncludeRebuttalChange}
        useDecomposition={useDecomposition}
        onDecompositionChange={handleDecompositionChange}
        useCache={useCache}
        onCacheChange={handleCacheChange}
        useResearch={useResearch}
        onResearchChange={handleResearchChange}
      />
    </div>
  );
}

export default App;
