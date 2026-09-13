import { useState, useRef, useEffect } from 'react';
import './Sidebar.css';

function ConversationItem({ conv, isActive, isLoading, onSelect, onDelete }) {
  return (
    <div
      className={`conversation-item ${isActive ? 'active' : ''}`}
      onClick={() => onSelect(conv.id)}
      title={conv.title || 'New Conversation'}
    >
      <div className="conversation-item-top">
        <div className="conversation-title" title={conv.title || 'New Conversation'}>
          {conv.title || 'New Conversation'}
        </div>
        {onDelete && (
          <button
            className="delete-conversation-btn"
            onClick={(e) => {
              e.stopPropagation();
              onDelete(conv);
            }}
            title="Delete conversation"
            aria-label="Delete conversation"
          >
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="3 6 5 6 21 6"></polyline>
              <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
            </svg>
          </button>
        )}
      </div>
      <div className="conversation-meta">
        <span className="conversation-count">{conv.message_count} messages</span>
        {(isLoading || conv.status === 'deliberating') && (
          <span className="conv-thinking-pill" title="Council deliberation in progress">
            <span className="thinking-pulse-dot"></span> Thinking...
          </span>
        )}
        {conv.status === 'aborted' && (
          <span className="conv-aborted-pill" title="Deliberation cancelled">
            Aborted
          </span>
        )}
        {conv.council_name && (
          <span className="conv-council-pill" title={`Council: ${conv.council_name}`}>
            {conv.council_name}
          </span>
        )}
      </div>
      {conv.tags && conv.tags.length > 1 && (
        <div className="conversation-tags">
          {conv.tags.slice(1).map((tag) => (
            <span key={tag} className="conversation-tag">
              #{tag}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

export default function Sidebar({
  conversations,
  currentConversationId,
  loadingConversationId,
  onSelectConversation,
  onNewConversation,
  onDeleteConversation,
  allTags,
  selectedTag,
  onTagFilterChange,
  activeCouncil,
  currentUser,
  advancedSettingsActive,
  onOpenDashboard,
  onOpenTelemetry,
  telemetryActive,
  telemetryLevel,
  onOpenSettings,
  onOpenConfigPanel,
  onOpenAccount,
  onLogout,
}) {
  const [searchQuery, setSearchQuery] = useState('');
  const [collapsedProjects, setCollapsedProjects] = useState({});
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const userMenuRef = useRef(null);

  useEffect(() => {
    if (!userMenuOpen) return;
    const handleClick = (e) => {
      if (userMenuRef.current && !userMenuRef.current.contains(e.target)) {
        setUserMenuOpen(false);
      }
    };
    const handleKey = (e) => {
      if (e.key === 'Escape') setUserMenuOpen(false);
    };
    document.addEventListener('mousedown', handleClick);
    document.addEventListener('keydown', handleKey);
    return () => {
      document.removeEventListener('mousedown', handleClick);
      document.removeEventListener('keydown', handleKey);
    };
  }, [userMenuOpen]);

  const searched = conversations.filter((conv) => {
    if (!searchQuery.trim()) return true;
    const q = searchQuery.toLowerCase();
    const titleMatch = (conv.title || '').toLowerCase().includes(q);
    const tagMatch = (conv.tags || []).some((t) => t.toLowerCase().includes(q));
    const councilMatch = (conv.council_name || '').toLowerCase().includes(q);
    return titleMatch || tagMatch || councilMatch;
  });

  // Group by primary (first) tag into "Projects"; conversations without a
  // tag fall into the flat "Chats" list below, mirroring ChatGPT's layout
  // while reusing the existing tag system instead of a new data model.
  const projectGroups = [];
  const ungrouped = [];
  if (!selectedTag) {
    const byTag = new Map();
    for (const conv of searched) {
      const primaryTag = conv.tags && conv.tags[0];
      if (!primaryTag) {
        ungrouped.push(conv);
        continue;
      }
      if (!byTag.has(primaryTag)) byTag.set(primaryTag, []);
      byTag.get(primaryTag).push(conv);
    }
    for (const [tag, items] of byTag.entries()) {
      projectGroups.push({ tag, items });
    }
    projectGroups.sort((a, b) => a.tag.localeCompare(b.tag));
  }

  const flatList = selectedTag ? searched : ungrouped;
  const toggleProject = (tag) => {
    setCollapsedProjects((prev) => ({ ...prev, [tag]: !prev[tag] }));
  };

  const initials = (currentUser || '?').slice(0, 2).toUpperCase();

  return (
    <div className="sidebar">
      <div className="sidebar-header">
        <span className="sidebar-brand">LLM Council</span>
        <button className="new-conversation-btn" onClick={() => onNewConversation?.()}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="12" y1="5" x2="12" y2="19"></line>
            <line x1="5" y1="12" x2="19" y2="12"></line>
          </svg>
          New Conversation
        </button>
      </div>

      {activeCouncil && (
        <div className="sidebar-active-council" title={`New conversations will start with ${activeCouncil.name}`}>
          <span className="sidebar-active-council-label">COUNCIL</span>
          <span className="sidebar-active-council-value">{activeCouncil.name}</span>
        </div>
      )}

      <nav className="sidebar-nav">
        <button type="button" className="sidebar-nav-item" onClick={onOpenDashboard}>
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="18" y1="20" x2="18" y2="10"></line>
            <line x1="12" y1="20" x2="12" y2="4"></line>
            <line x1="6" y1="20" x2="6" y2="14"></line>
          </svg>
          Dashboard
        </button>
        <button type="button" className={`sidebar-nav-item ${telemetryActive ? 'active' : ''}`} onClick={onOpenTelemetry}>
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline>
          </svg>
          Telemetry
          {telemetryLevel > 0 && <span className="sidebar-nav-badge">L{telemetryLevel}</span>}
        </button>
      </nav>

      <div className="sidebar-search">
        <input
          type="text"
          className="sidebar-search-input"
          placeholder="Search conversations..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
        />
        {searchQuery && (
          <button
            className="sidebar-search-clear"
            onClick={() => setSearchQuery('')}
            title="Clear search"
          >
            ×
          </button>
        )}
      </div>

      {selectedTag && (
        <div className="sidebar-active-filter">
          <span>Project: #{selectedTag}</span>
          <button type="button" onClick={() => onTagFilterChange(null)} title="Back to all conversations">
            ← All
          </button>
        </div>
      )}

      <div className="sidebar-scroll">
        {!selectedTag && projectGroups.length > 0 && (
          <div className="sidebar-section">
            <div className="sidebar-section-label">Projects</div>
            {projectGroups.map((group) => {
              const isCollapsed = !!collapsedProjects[group.tag];
              return (
                <div key={group.tag} className="project-group">
                  <div className="project-group-header">
                    <button
                      type="button"
                      className="project-group-toggle"
                      onClick={() => toggleProject(group.tag)}
                      title={isCollapsed ? 'Expand' : 'Collapse'}
                    >
                      <svg
                        width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3"
                        strokeLinecap="round" strokeLinejoin="round"
                        style={{ transform: isCollapsed ? 'rotate(-90deg)' : 'none', transition: 'transform 0.15s ease-out' }}
                      >
                        <polyline points="6 9 12 15 18 9"></polyline>
                      </svg>
                      <span className="project-group-name">{group.tag}</span>
                    </button>
                    <button
                      type="button"
                      className="project-group-filter-btn"
                      onClick={() => onTagFilterChange(group.tag)}
                      title={`Filter to only #${group.tag}`}
                    >
                      {group.items.length}
                    </button>
                  </div>
                  {!isCollapsed && (
                    <div className="project-group-items">
                      {group.items.map((conv) => (
                        <ConversationItem
                          key={conv.id}
                          conv={conv}
                          isActive={conv.id === currentConversationId}
                          isLoading={conv.id === loadingConversationId}
                          onSelect={onSelectConversation}
                          onDelete={onDeleteConversation}
                        />
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}

        <div className="sidebar-section">
          <div className="sidebar-section-label">{selectedTag ? `#${selectedTag}` : 'Chats'}</div>
          {flatList.length === 0 ? (
            <div className="no-conversations">
              {searchQuery
                ? `No conversations matching "${searchQuery}"`
                : selectedTag
                ? `No conversations with #${selectedTag}`
                : 'No untagged conversations'}
            </div>
          ) : (
            flatList.map((conv) => (
              <ConversationItem
                key={conv.id}
                conv={conv}
                isActive={conv.id === currentConversationId}
                isLoading={conv.id === loadingConversationId}
                onSelect={onSelectConversation}
                onDelete={onDeleteConversation}
              />
            ))
          )}
        </div>
      </div>

      {currentUser && (
        <div className="sidebar-user-footer" ref={userMenuRef}>
          {userMenuOpen && (
            <div className="user-menu">
              <button type="button" className="user-menu-item" onClick={() => { onOpenSettings(); setUserMenuOpen(false); }}>
                Settings
                {advancedSettingsActive && <span className="user-menu-dot" title="Advanced settings active" />}
              </button>
              <button type="button" className="user-menu-item" onClick={() => { onOpenConfigPanel(); setUserMenuOpen(false); }}>
                Configure Models
              </button>
              <button type="button" className="user-menu-item" onClick={() => { onOpenAccount(); setUserMenuOpen(false); }}>
                Account &amp; Password
              </button>
              <div className="user-menu-divider" />
              <button type="button" className="user-menu-item user-menu-logout" onClick={() => { onLogout(); setUserMenuOpen(false); }}>
                Logout
              </button>
            </div>
          )}
          <button type="button" className="sidebar-user-btn" onClick={() => setUserMenuOpen((v) => !v)}>
            <span className="user-avatar">{initials}</span>
            <span className="user-name">{currentUser}</span>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="user-menu-caret">
              <polyline points="18 15 12 9 6 15"></polyline>
            </svg>
          </button>
        </div>
      )}
    </div>
  );
}
