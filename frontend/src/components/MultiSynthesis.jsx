import { useState } from 'react';
import SafeMarkdown from './SafeMarkdown.jsx';
import './MultiSynthesis.css';

/**
 * MultiSynthesis - Displays multi-chairman synthesis results.
 *
 * Shows individual syntheses from multiple chairman models,
 * the supreme chairman's evaluation, and the final selected response.
 *
 * @param {Object} props
 * @param {Object} props.result - Complete multi-chairman result
 *   Contains: { model, response, selected_synthesis, selection_reasoning, syntheses, label_to_model }
 * @param {Array} props.syntheses - Array of synthesis objects during streaming
 * @param {string} props.selectionStreaming - Partial selection text (during streaming)
 * @param {boolean} props.isStreaming - Whether synthesis is currently streaming
 * @param {boolean} props.isSelecting - Whether selection is currently streaming
 */
export default function MultiSynthesis({
  result,
  syntheses = [],
  selectionStreaming = '',
  isStreaming = false,
  isSelecting = false,
}) {
  const [activeTab, setActiveTab] = useState(0);
  const [showEvaluation, setShowEvaluation] = useState(false);

  // Use streaming syntheses or final result syntheses
  const displaySyntheses = result?.syntheses || syntheses || [];
  const selectedModel = result?.selected_synthesis;
  const selectionReasoning = result?.selection_reasoning;
  const finalResponse = result?.response;
  const supremeModel = result?.model;

  if (displaySyntheses.length === 0 && !isStreaming) {
    return null;
  }

  return (
    <div className="multi-synthesis">
      <div className="multi-synthesis-header">
        <h4 className="multi-synthesis-title">
          Multi-Chairman Synthesis
          {isStreaming && <span className="streaming-badge">Synthesizing...</span>}
          {isSelecting && <span className="selecting-badge">Selecting...</span>}
        </h4>
        <span className="multi-synthesis-count">
          {displaySyntheses.length} chairman{displaySyntheses.length !== 1 ? 's' : ''}
        </span>
      </div>

      {/* Synthesis tabs */}
      <div className="synthesis-tabs">
        {displaySyntheses.map((synthesis, index) => {
          const modelName = synthesis.model?.split('/')[1] || synthesis.model || `Chairman ${index + 1}`;
          const isSelected = selectedModel === synthesis.model;
          const label = String.fromCharCode(65 + index); // A, B, C...

          return (
            <button
              key={synthesis.model || index}
              className={`synthesis-tab ${activeTab === index ? 'active' : ''} ${isSelected ? 'selected' : ''}`}
              onClick={() => setActiveTab(index)}
            >
              <span className="synthesis-label">{label}</span>
              <span className="synthesis-model-name">{modelName}</span>
              {isSelected && <span className="selected-icon">✓</span>}
            </button>
          );
        })}
      </div>

      {/* Synthesis content */}
      <div className="synthesis-content">
        {displaySyntheses.map((synthesis, index) => (
          <div
            key={synthesis.model || index}
            className={`synthesis-panel ${activeTab === index ? 'active' : ''}`}
          >
            <div className="synthesis-text markdown-content">
              <SafeMarkdown>{synthesis.response || ''}</SafeMarkdown>
            </div>
          </div>
        ))}
      </div>

      {/* Supreme Chairman Selection */}
      {(selectedModel || isSelecting || selectionStreaming) && (
        <div className="supreme-selection">
          <div className="supreme-header">
            <h4 className="supreme-title">
              Supreme Chairman Selection
              {isSelecting && <span className="selecting-badge">Evaluating...</span>}
            </h4>
            {supremeModel && (
              <span className="supreme-model">
                {supremeModel.split('/')[1] || supremeModel}
              </span>
            )}
          </div>

          {/* Selected synthesis indicator */}
          {selectedModel && (
            <div className="selection-result">
              <span className="selection-label">Selected:</span>
              <span className="selection-model">
                {selectedModel.split('/')[1] || selectedModel}
              </span>
            </div>
          )}

          {/* Selection reasoning toggle */}
          {(selectionReasoning || selectionStreaming) && (
            <div className="selection-reasoning-section">
              <button
                className="reasoning-toggle"
                onClick={() => setShowEvaluation(!showEvaluation)}
              >
                {showEvaluation ? '▼' : '▶'} Show Evaluation Details
              </button>
              {showEvaluation && (
                <div className="selection-reasoning markdown-content">
                  <SafeMarkdown>
                    {selectionReasoning || selectionStreaming || ''}
                  </SafeMarkdown>
                  {isSelecting && <span className="streaming-cursor green"></span>}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Final Response */}
      {finalResponse && !isSelecting && (
        <div className="final-synthesis">
          <div className="final-synthesis-header">
            <h4 className="final-synthesis-title">Final Response</h4>
          </div>
          <div className="final-synthesis-text markdown-content">
            <SafeMarkdown>{finalResponse}</SafeMarkdown>
          </div>
        </div>
      )}
    </div>
  );
}
