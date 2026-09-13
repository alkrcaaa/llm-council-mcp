import { useState } from 'react';
import './TagEditor.css';

const SUGGESTED_TAGS = [
  'coding',
  'writing',
  'analysis',
  'research',
  'creative',
  'technical',
  'business',
  'learning',
];

export default function TagEditor({ tags, onTagsChange, onClose }) {
  const [inputValue, setInputValue] = useState('');
  const [showSuggestions, setShowSuggestions] = useState(false);

  const addTag = (tag) => {
    const normalizedTag = tag.trim().toLowerCase();
    if (normalizedTag && !tags.includes(normalizedTag)) {
      onTagsChange([...tags, normalizedTag]);
    }
    setInputValue('');
    setShowSuggestions(false);
  };

  const removeTag = (tagToRemove) => {
    onTagsChange(tags.filter((t) => t !== tagToRemove));
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && inputValue.trim()) {
      e.preventDefault();
      addTag(inputValue);
    } else if (e.key === 'Escape') {
      onClose?.();
    }
  };

  // Filter suggestions to exclude already-added tags
  const availableSuggestions = SUGGESTED_TAGS.filter(
    (tag) => !tags.includes(tag)
  );

  return (
    <div className="tag-editor">
      <div className="tags-list">
        {tags.map((tag) => (
          <span key={tag} className="tag">
            {tag}
            <button
              className="tag-remove"
              onClick={() => removeTag(tag)}
              title="Remove tag"
            >
              ×
            </button>
          </span>
        ))}
      </div>

      <div className="tag-input-container">
        <input
          type="text"
          className="tag-input"
          placeholder="Add tag..."
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyDown={handleKeyDown}
          onFocus={() => setShowSuggestions(true)}
          onBlur={() => setTimeout(() => setShowSuggestions(false), 150)}
        />
        {showSuggestions && availableSuggestions.length > 0 && (
          <div className="tag-suggestions">
            {availableSuggestions.map((tag) => (
              <button
                key={tag}
                className="tag-suggestion"
                onClick={() => addTag(tag)}
              >
                {tag}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
