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
          <span className="sidebar-active-council-value">{activeCouncil.icon || '🏛️'} {activeCouncil.name}</span>
        </div>
      )}

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
        {conversations.length === 0 ? (
          <div className="no-conversations">
            {selectedTag ? `No conversations with #${selectedTag}` : 'No conversations yet'}
          </div>
        ) : (
          conversations.map((conv) => (
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
                {conv.id === loadingConversationId && (
                  <span className="conv-thinking-pill" title="Konsey deliberasyonu devam ediyor">
                    <span className="thinking-pulse-dot"></span> Düşünüyor...
                  </span>
                )}
                {conv.council_name && (
                  <span className="conv-council-pill" title={`Assigned Council: ${conv.council_name}`}>
                    🏛️ {conv.council_name}
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
