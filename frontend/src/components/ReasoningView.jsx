import { useState } from 'react';
import SafeMarkdown from './SafeMarkdown.jsx';
import './ReasoningView.css';

/**
 * ReasoningView - Displays Chain-of-Thought structured reasoning.
 *
 * Shows the three-step reasoning process:
 * 1. THINKING - Initial thoughts and key considerations
 * 2. ANALYSIS - Evaluation of approaches and trade-offs
 * 3. CONCLUSION - Final answer based on the analysis
 *
 * Each step can be expanded/collapsed independently.
 *
 * @param {Object} props
 * @param {Object} props.cot - Chain-of-Thought object with thinking, analysis, conclusion
 * @param {string} props.cot.thinking - Initial thinking process
 * @param {string} props.cot.analysis - Analysis of approaches
 * @param {string} props.cot.conclusion - Final conclusion
 * @param {boolean} props.showAll - If true, show all sections expanded by default
 * @param {boolean} props.compact - If true, use compact display mode
 */
export default function ReasoningView({ cot, showAll = false, compact = false }) {
  const [expandedSections, setExpandedSections] = useState({
    thinking: showAll,
    analysis: showAll,
    conclusion: true, // Always show conclusion by default
  });

  if (!cot) return null;

  const toggleSection = (section) => {
    setExpandedSections((prev) => ({
      ...prev,
      [section]: !prev[section],
    }));
  };

  const sections = [
    {
      key: 'thinking',
      title: 'Thinking',
      icon: '1',
      description: 'Initial thoughts and key considerations',
      content: cot.thinking,
      color: 'blue',
    },
    {
      key: 'analysis',
      title: 'Analysis',
      icon: '2',
      description: 'Evaluation of approaches and trade-offs',
      content: cot.analysis,
      color: 'purple',
    },
    {
      key: 'conclusion',
      title: 'Conclusion',
      icon: '3',
      description: 'Final answer based on the analysis',
      content: cot.conclusion,
      color: 'green',
    },
  ];

  if (compact) {
    return (
      <div className="reasoning-view compact">
        <div className="cot-badge">
          <span className="cot-icon">CoT</span>
          <span className="cot-label">Chain-of-Thought</span>
        </div>
      </div>
    );
  }

  return (
    <div className="reasoning-view">
      <div className="reasoning-header">
        <div className="cot-badge">
          <span className="cot-icon">CoT</span>
          <span className="cot-label">Chain-of-Thought Reasoning</span>
        </div>
        <div className="reasoning-progress">
          {sections.map((section, index) => (
            <div
              key={section.key}
              className={`progress-step ${section.color} ${section.content ? 'has-content' : 'empty'}`}
              title={section.title}
            >
              <span className="step-number">{section.icon}</span>
              {index < sections.length - 1 && <span className="step-connector" />}
            </div>
          ))}
        </div>
      </div>

      <div className="reasoning-sections">
        {sections.map((section) => (
          <div
            key={section.key}
            className={`reasoning-section ${section.color} ${expandedSections[section.key] ? 'expanded' : ''}`}
          >
            <button
              className="section-header"
              onClick={() => toggleSection(section.key)}
              disabled={!section.content}
            >
              <div className="section-indicator">
                <span className={`step-badge ${section.color}`}>{section.icon}</span>
              </div>
              <div className="section-info">
                <span className="section-title">{section.title}</span>
                <span className="section-description">{section.description}</span>
              </div>
              <span className="section-toggle">
                {section.content ? (expandedSections[section.key] ? '−' : '+') : '○'}
              </span>
            </button>

            {expandedSections[section.key] && section.content && (
              <div className="section-content">
                <div className="markdown-content">
                  <SafeMarkdown>{section.content}</SafeMarkdown>
                </div>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

/**
 * CoTBadge - Small badge indicating Chain-of-Thought is enabled.
 *
 * Used in tabs or headers to show a response has CoT structure.
 */
export function CoTBadge() {
  return (
    <span className="cot-mini-badge" title="Chain-of-Thought reasoning">
      CoT
    </span>
  );
}

/**
 * CoTToggle - Toggle control for enabling/disabling CoT mode.
 *
 * @param {Object} props
 * @param {boolean} props.enabled - Whether CoT mode is enabled
 * @param {function} props.onChange - Callback when toggle changes
 */
export function CoTToggle({ enabled, onChange }) {
  return (
    <label className="cot-toggle">
      <input
        type="checkbox"
        checked={enabled}
        onChange={(e) => onChange(e.target.checked)}
      />
      <span className="toggle-slider" />
      <span className="toggle-label">
        Chain-of-Thought
        <span className="toggle-description">Request structured reasoning</span>
      </span>
    </label>
  );
}
