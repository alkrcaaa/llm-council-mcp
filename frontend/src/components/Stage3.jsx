import ReactMarkdown from 'react-markdown';
import MultiSynthesis from './MultiSynthesis';
import RefinementView, { RefinementBadge } from './RefinementView';
import AdversaryReview, { AdversaryBadge } from './AdversaryReview';
import DebateView, { DebateBadge } from './DebateView';
import DecomposedView, { DecompositionBadge } from './DecomposedView';
import './Stage3.css';

/**
 * Stage3 - Displays the final council answer from the chairman model.
 *
 * Supports real-time token streaming: as the chairman generates the response,
 * tokens are displayed incrementally with a cursor indicator.
 *
 * Also supports multi-chairman mode where multiple chairmen create syntheses
 * and a supreme chairman selects the best one.
 *
 * Additionally supports early consensus exit where Stage 3 is skipped when
 * all models strongly agree, displaying the consensus response directly.
 *
 * Also supports iterative refinement where the council critiques and the
 * chairman revises the synthesis until quality converges.
 *
 * Also supports adversarial validation where a devil's advocate model
 * reviews the synthesis for flaws and issues.
 *
 * Also supports debate mode where models engage in structured multi-round
 * debates: Position → Critique → Rebuttal → Judgment.
 *
 * @param {Object} props
 * @param {Object} props.finalResponse - Complete response object (when finished)
 *   Contains: { model, response, usage?, cost? }
 *   For multi-chairman: also includes { selected_synthesis, selection_reasoning, syntheses, label_to_model }
 *   For consensus: also includes { is_consensus, consensus_reason }
 *   For refinement: also includes { refinement_applied, refinement_iterations, refinement_converged }
 *   For adversary: also includes { adversary_applied, adversary_issues_found, adversary_severity, adversary_revised }
 * @param {string} props.streamingResponse - Partial response text (during streaming)
 * @param {string} props.streamingModel - Model identifier (during streaming)
 * @param {boolean} props.isStreaming - Whether Stage 3 is currently streaming
 * @param {boolean} props.useMultiChairman - Whether multi-chairman mode is active
 * @param {Array} props.multiSyntheses - Array of synthesis objects during streaming
 * @param {string} props.selectionStreaming - Partial selection text during streaming
 * @param {boolean} props.isSelecting - Whether supreme chairman is selecting
 * @param {boolean} props.isConsensus - Whether consensus was detected (Stage 3 skipped)
 * @param {Object} props.consensusInfo - Consensus detection details
 * @param {boolean} props.useRefinement - Whether refinement mode is active
 * @param {Array} props.refinementIterations - Array of refinement iteration objects
 * @param {boolean} props.isRefining - Whether refinement is in progress
 * @param {number} props.currentRefinementIteration - Current iteration number
 * @param {Array} props.refinementCritiques - Current iteration's critiques (during streaming)
 * @param {string} props.refinementStreaming - Partial revision text during streaming
 * @param {number} props.refinementMaxIterations - Max configured iterations
 * @param {boolean} props.refinementConverged - Whether refinement converged early
 * @param {boolean} props.useAdversary - Whether adversary mode is active
 * @param {string} props.adversaryCritique - The adversary's critique
 * @param {boolean} props.adversaryHasIssues - Whether issues were found
 * @param {string} props.adversarySeverity - Severity level: critical, major, minor, none
 * @param {boolean} props.adversaryRevised - Whether a revision was made
 * @param {string} props.adversaryRevision - The revised response (if applicable)
 * @param {string} props.adversaryModel - The adversary model used
 * @param {boolean} props.isAdversaryReviewing - Whether adversary is currently reviewing
 * @param {boolean} props.isAdversaryRevising - Whether chairman is revising based on adversary
 * @param {string} props.adversaryStreaming - Partial critique during streaming
 * @param {string} props.adversaryRevisionStreaming - Partial revision during streaming
 * @param {boolean} props.useDebate - Whether debate mode is active
 * @param {Array} props.debatePositions - Round 1 position statements
 * @param {Array} props.debateCritiques - Round 2 critiques
 * @param {Array} props.debateRebuttals - Round 3 rebuttals
 * @param {string} props.debateJudgment - Chairman's final judgment
 * @param {string} props.debateJudgmentStreaming - Partial judgment during streaming
 * @param {boolean} props.isDebating - Whether debate is in progress
 * @param {boolean} props.isJudging - Whether judgment is being generated
 * @param {number} props.debateRound - Current debate round number
 * @param {Object} props.debateModelToLabel - Mapping of model IDs to labels
 * @param {Object} props.debateLabelToModel - Mapping of labels to model IDs
 * @param {number} props.debateNumRounds - Number of debate rounds (2 or 3)
 * @param {boolean} props.useDecomposition - Whether decomposition mode is active
 * @param {Array} props.subQuestions - Array of sub-questions generated
 * @param {Array} props.subResults - Array of sub-council results
 * @param {boolean} props.isDecomposing - Whether decomposition is in progress
 * @param {number} props.currentSubQuestion - Current sub-question index
 * @param {number} props.totalSubQuestions - Total number of sub-questions
 * @param {string} props.mergeStreaming - Partial merge response during streaming
 * @param {boolean} props.isMerging - Whether merge is in progress
 * @param {string} props.decompositionFinalResponse - Final merged response
 * @param {string} props.chairmanModel - Chairman model used for merging
 * @param {Object} props.complexityInfo - Complexity analysis result
 * @param {boolean} props.decompositionSkipped - Whether decomposition was skipped (too simple)
 * @param {boolean} props.decompositionComplete - Whether decomposition is complete
 */
export default function Stage3({
  finalResponse,
  streamingResponse,
  streamingModel,
  isStreaming,
  useMultiChairman = false,
  multiSyntheses = [],
  selectionStreaming = '',
  isSelecting = false,
  isConsensus = false,
  consensusInfo = null,
  useRefinement = false,
  refinementIterations = [],
  isRefining = false,
  currentRefinementIteration = 0,
  refinementCritiques = [],
  refinementStreaming = '',
  refinementMaxIterations = 2,
  refinementConverged = false,
  useAdversary = false,
  adversaryCritique = '',
  adversaryHasIssues = false,
  adversarySeverity = 'none',
  adversaryRevised = false,
  adversaryRevision = '',
  adversaryModel = '',
  isAdversaryReviewing = false,
  isAdversaryRevising = false,
  adversaryStreaming = '',
  adversaryRevisionStreaming = '',
  // Debate props
  useDebate = false,
  debatePositions = [],
  debateCritiques = [],
  debateRebuttals = [],
  debateJudgment = '',
  debateJudgmentStreaming = '',
  isDebating = false,
  isJudging = false,
  debateRound = 0,
  debateModelToLabel = {},
  debateLabelToModel = {},
  debateNumRounds = 3,
  // Decomposition props
  useDecomposition = false,
  subQuestions = [],
  subResults = [],
  isDecomposing = false,
  currentSubQuestion = -1,
  totalSubQuestions = 0,
  mergeStreaming = '',
  isMerging = false,
  decompositionFinalResponse = '',
  chairmanModel = '',
  complexityInfo = null,
  decompositionSkipped = false,
  decompositionComplete = false,
}) {
  // Early Consensus Exit mode
  if (isConsensus && finalResponse) {
    const metrics = consensusInfo?.metrics || {};
    const model = finalResponse.model || 'Unknown';
    const modelShort = model.split('/')[1] || model;

    return (
      <div className="stage stage3 consensus-mode">
        <div className="stage3-header">
          <h3 className="stage-title">Stage 3: Final Council Answer</h3>
          <span className="consensus-badge">Consensus</span>
        </div>
        <div className="consensus-notice">
          <div className="consensus-icon">&#10003;</div>
          <div className="consensus-text">
            <strong>Early Consensus Detected</strong>
            <p>Stage 3 chairman synthesis was skipped because the council reached strong agreement.</p>
          </div>
        </div>
        <div className="consensus-metrics">
          <div className="metric">
            <span className="metric-label">Winning Model</span>
            <span className="metric-value model-name">{modelShort}</span>
          </div>
          <div className="metric">
            <span className="metric-label">Average Rank</span>
            <span className="metric-value">{metrics.average_rank?.toFixed(2) || 'N/A'}</span>
          </div>
          <div className="metric">
            <span className="metric-label">First-Place Votes</span>
            <span className="metric-value">{metrics.first_place_votes || 0} / {metrics.total_voters || 0}</span>
          </div>
          <div className="metric">
            <span className="metric-label">Avg Confidence</span>
            <span className="metric-value">{metrics.average_confidence?.toFixed(1) || 'N/A'}</span>
          </div>
        </div>
        <div className="final-response consensus-response">
          <div className="chairman-label consensus-winner">
            Winner: {modelShort}
          </div>
          <div className="final-text markdown-content">
            <ReactMarkdown>{finalResponse.response || ''}</ReactMarkdown>
          </div>
        </div>
      </div>
    );
  }

  // Multi-Chairman mode
  if (useMultiChairman) {
    const hasContent = finalResponse || multiSyntheses.length > 0 || isStreaming || isSelecting;
    if (!hasContent) {
      return null;
    }

    return (
      <div className="stage stage3">
        <div className="stage3-header">
          <h3 className="stage-title">Stage 3: Final Council Answer</h3>
          <span className="multi-chairman-badge">Multi-Chairman</span>
          {isStreaming && <span className="streaming-indicator">Synthesizing...</span>}
          {isSelecting && <span className="streaming-indicator selecting">Selecting...</span>}
        </div>
        <MultiSynthesis
          result={finalResponse}
          syntheses={multiSyntheses}
          selectionStreaming={selectionStreaming}
          isStreaming={isStreaming}
          isSelecting={isSelecting}
        />
      </div>
    );
  }

  // Debate mode - completely different flow
  if (useDebate) {
    const hasDebateContent = debatePositions.length > 0 || isDebating || isJudging || debateJudgment || debateJudgmentStreaming;
    if (!hasDebateContent) {
      return null;
    }

    return (
      <div className="stage stage3 debate-mode">
        <div className="stage3-header">
          <h3 className="stage-title">Council Debate</h3>
          <DebateBadge numRounds={debateNumRounds} />
          {isDebating && !isJudging && <span className="streaming-indicator debate">Round {debateRound}...</span>}
          {isJudging && <span className="streaming-indicator debate">Judging...</span>}
        </div>
        <DebateView
          positions={debatePositions}
          critiques={debateCritiques}
          rebuttals={debateRebuttals}
          judgment={debateJudgment}
          modelToLabel={debateModelToLabel}
          labelToModel={debateLabelToModel}
          numRounds={debateNumRounds}
          isDebating={isDebating}
          currentRound={debateRound}
          judgmentStreaming={debateJudgmentStreaming}
          isJudging={isJudging}
        />
      </div>
    );
  }

  // Sub-Question Decomposition mode
  if (useDecomposition) {
    const hasDecompositionContent = subQuestions.length > 0 || isDecomposing || isMerging || decompositionComplete || decompositionSkipped;
    if (!hasDecompositionContent) {
      return null;
    }

    // When decomposition is skipped, still show the view with skip indicator
    // The normal council flow will handle the response
    if (decompositionSkipped) {
      return (
        <div className="stage stage3 decomposition-mode">
          <div className="stage3-header">
            <h3 className="stage-title">Stage 3: Final Council Answer</h3>
          </div>
          <DecomposedView
            wasSkipped={true}
            complexityInfo={complexityInfo}
          />
        </div>
      );
    }

    return (
      <div className="stage stage3 decomposition-mode">
        <div className="stage3-header">
          <h3 className="stage-title">Stage 3: Final Council Answer</h3>
          <DecompositionBadge subQuestionCount={subQuestions.length || totalSubQuestions} />
          {isDecomposing && !isMerging && <span className="streaming-indicator decomposition">Processing {currentSubQuestion + 1}/{totalSubQuestions}...</span>}
          {isMerging && <span className="streaming-indicator decomposition merging">Merging...</span>}
        </div>
        <DecomposedView
          subQuestions={subQuestions}
          subResults={subResults}
          finalResponse={decompositionFinalResponse}
          chairmanModel={chairmanModel}
          isDecomposing={isDecomposing}
          currentSubQuestion={currentSubQuestion}
          totalSubQuestions={totalSubQuestions}
          mergeStreaming={mergeStreaming}
          isMerging={isMerging}
          complexityInfo={complexityInfo}
          wasSkipped={false}
        />
      </div>
    );
  }

  // Standard single chairman mode
  // Use streaming data if available, otherwise use final response
  const displayResponse = finalResponse?.response || streamingResponse || '';
  const displayModel = finalResponse?.model || streamingModel || 'Chairman';

  // Check if refinement was applied
  const refinementApplied = finalResponse?.refinement_applied;
  const refinementIterationCount = finalResponse?.refinement_iterations || refinementIterations?.length || 0;
  const didConverge = finalResponse?.refinement_converged || refinementConverged;

  // Check if adversary was applied
  const adversaryApplied = finalResponse?.adversary_applied;
  const adversaryIssuesFound = finalResponse?.adversary_issues_found ?? adversaryHasIssues;
  const adversarySeverityLevel = finalResponse?.adversary_severity || adversarySeverity;
  const wasAdversaryRevised = finalResponse?.adversary_revised ?? adversaryRevised;

  if (!displayResponse && !isStreaming && !isRefining && !isAdversaryReviewing) {
    return null;
  }

  return (
    <div className="stage stage3">
      <div className="stage3-header">
        <h3 className="stage-title">Stage 3: Final Council Answer</h3>
        {refinementApplied && (
          <RefinementBadge iterations={refinementIterationCount} converged={didConverge} />
        )}
        {adversaryApplied && (
          <AdversaryBadge hasIssues={adversaryIssuesFound} severity={adversarySeverityLevel} revised={wasAdversaryRevised} />
        )}
        {isStreaming && <span className="streaming-indicator">Streaming...</span>}
        {isRefining && <span className="streaming-indicator refining">Refining...</span>}
        {isAdversaryReviewing && <span className="streaming-indicator adversary">Validating...</span>}
        {isAdversaryRevising && <span className="streaming-indicator adversary">Revising...</span>}
      </div>
      <div className="final-response">
        <div className="chairman-label">
          Chairman: {(() => {
            const [baseDisplay, sId] = displayModel.split('@');
            const bName = baseDisplay.split('/')[1] || baseDisplay;
            return sId ? `${bName} [${sId}]` : bName;
          })()}
          {isStreaming && <span className="streaming-badge">Generating...</span>}
        </div>
        <div className={`final-text markdown-content ${isStreaming ? 'streaming' : ''}`}>
          <ReactMarkdown>{displayResponse}</ReactMarkdown>
          {isStreaming && <span className="streaming-cursor"></span>}
        </div>
      </div>

      {/* Refinement View - shown when refinement is active or was applied */}
      {(useRefinement || refinementApplied || isRefining || refinementIterations.length > 0) && (
        <RefinementView
          iterations={refinementIterations}
          finalResponse={displayResponse}
          totalIterations={refinementIterationCount}
          converged={didConverge}
          isRefining={isRefining}
          currentIteration={currentRefinementIteration}
          streamingCritiques={refinementCritiques}
          streamingRevision={refinementStreaming}
          maxIterations={refinementMaxIterations}
        />
      )}

      {/* Adversary Review - shown when adversary is active or was applied */}
      {(useAdversary || adversaryApplied || isAdversaryReviewing || isAdversaryRevising || adversaryCritique) && (
        <AdversaryReview
          critique={adversaryCritique}
          hasIssues={adversaryIssuesFound}
          severity={adversarySeverityLevel}
          revised={wasAdversaryRevised}
          revision={adversaryRevision}
          adversaryModel={adversaryModel}
          isReviewing={isAdversaryReviewing}
          isRevising={isAdversaryRevising}
          streamingCritique={adversaryStreaming}
          streamingRevision={adversaryRevisionStreaming}
        />
      )}
    </div>
  );
}
