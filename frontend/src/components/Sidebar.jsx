import { useState } from 'react';
import './Sidebar.css';

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
}) {
  const [searchQuery, setSearchQuery] = useState('');

  const filteredConversations = conversations.filter((conv) => {
    if (selectedTag && (!conv.tags || !conv.tags.includes(selectedTag))) {
      return false;
    }
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      const titleMatch = (conv.title || '').toLowerCase().includes(q);
      const tagMatch = (conv.tags || []).some((t) => t.toLowerCase().includes(q));
      const councilMatch = (conv.council_name || '').toLowerCase().includes(q);
      return titleMatch || tagMatch || councilMatch;
    }
    return true;
  });

  return (
    <div className="sidebar">
      <div className="sidebar-header">
        <h1>LLM Council</h1>
        <button className="new-conversation-btn" onClick={() => onNewConversation?.()}>
          + New Conversation
        </button>
      </div>

      {/* Active Council indicator for new chats */}
      {activeCouncil && (
        <div className="sidebar-active-council" title={`New conversations will start with ${activeCouncil.name}`}>
          <span className="sidebar-active-council-label">COUNCIL:</span>
          <span className="sidebar-active-council-value">{activeCouncil.name}</span>
        </div>
      )}

      {/* Conversation Search Bar */}
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

      {/* Tag Filter */}
      {allTags && allTags.length > 0 && (
        <div className="tag-filter">
          <select
            value={selectedTag || ''}
            onChange={(e) => onTagFilterChange(e.target.value || null)}
            className="tag-filter-select"
          >
            <option value="">All conversations</option>
            {allTags.map((tag) => (
              <option key={tag} value={tag}>
                #{tag}
              </option>
            ))}
          </select>
        </div>
      )}

      <div className="conversation-list">
        {filteredConversations.length === 0 ? (
          <div className="no-conversations">
            {searchQuery
              ? `No conversations matching "${searchQuery}"`
              : selectedTag
              ? `No conversations with #${selectedTag}`
              : 'No conversations yet'}
          </div>
        ) : (
          filteredConversations.map((conv) => (
            <div
              key={conv.id}
              className={`conversation-item ${
                conv.id === currentConversationId ? 'active' : ''
              }`}
              onClick={() => onSelectConversation(conv.id)}
            >
              <div className="conversation-item-top">
                <div className="conversation-title">
                  {conv.title || 'New Conversation'}
                </div>
                {onDeleteConversation && (
                  <button
                    className="delete-conversation-btn"
                    onClick={(e) => {
                      e.stopPropagation();
                      onDeleteConversation(conv);
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
                {(conv.id === loadingConversationId || conv.status === 'deliberating') && (
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
              {conv.tags && conv.tags.length > 0 && (
                <div className="conversation-tags">
                  {conv.tags.map((tag) => (
                    <span key={tag} className="conversation-tag">
                      #{tag}
                    </span>
                  ))}
                </div>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
