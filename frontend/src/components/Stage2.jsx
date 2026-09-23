import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import './Stage2.css';

function formatModelLabel(model) {
  if (!model) return '';
  const [baseModel, skillId = ''] = model.split('@');
  const shortName = baseModel.split('/')[1] || baseModel;
  if (!skillId) return shortName.replace(':free', '');

  let skillTitle = skillId;
  if (skillId.includes('security')) skillTitle = 'Security';
  else if (skillId.includes('karpathy') || skillId.includes('architect')) skillTitle = 'Simplicity';
  else if (skillId.includes('devops')) skillTitle = 'DevOps';
  else if (skillId.includes('testing') || skillId.includes('qa')) skillTitle = 'Quality';
  else if (skillId.includes('review')) skillTitle = 'Review';
  else if (skillId.includes('first-principles')) skillTitle = 'Principles';
  else if (skillId.includes('deep-research')) skillTitle = 'Research';
  else if (skillId.includes('design-dna') || skillId.includes('frontend')) skillTitle = 'UI/UX';
  else {
    skillTitle = skillId.replace(/-(guidelines|handbook|audit|security)/g, '');
    skillTitle = skillTitle.charAt(0).toUpperCase() + skillTitle.slice(1);
  }

  return `${shortName.replace(':free', '')} [${skillTitle}]`;
}

function deAnonymizeText(text, labelToModel) {
  if (!labelToModel) return text;

  let result = text;
  Object.entries(labelToModel).forEach(([label, model]) => {
    const labelFormatted = formatModelLabel(model);
    result = result.replace(new RegExp(label, 'g'), `**${labelFormatted}**`);
  });
  return result;
}

export default function Stage2({ rankings, labelToModel, aggregateRankings, useWeightedConsensus, weightsInfo }) {
  const [viewMode, setViewMode] = useState('matrix'); // 'matrix' | 'tabs'
  const [activeTab, setActiveTab] = useState(0);
  const [showWeightsDetails, setShowWeightsDetails] = useState(false);

  if (!rankings || rankings.length === 0) {
    return null;
  }

  const hasWeightedData = useWeightedConsensus && weightsInfo?.has_historical_data;

  // Extract all target models from labelToModel
  const targetModels = labelToModel ? Object.values(labelToModel) : [];

  return (
    <div className="stage stage2">
      <div className="stage2-header-row">
        <div>
          <h3 className="stage-title">Stage 2: Peer Review & Critique Matrix</h3>
          <p className="stage-description">
            Models anonymously evaluated and ranked their peers. Explore who ranked whom and why.
          </p>
        </div>

        {/* View Mode Switcher */}
        <div className="stage2-view-switcher">
          <button
            type="button"
            className={`view-mode-btn ${viewMode === 'matrix' ? 'active' : ''}`}
            onClick={() => setViewMode('matrix')}
            title="Show who ranked whom in a cross-model matrix"
          >
            Peer Matrix
          </button>
          <button
            type="button"
            className={`view-mode-btn ${viewMode === 'tabs' ? 'active' : ''}`}
            onClick={() => setViewMode('tabs')}
            title="View full detailed critique from each model"
          >
            Detailed Critiques
          </button>
        </div>
      </div>

      {/* Aggregate Leaderboard First */}
      {aggregateRankings && aggregateRankings.length > 0 && (
        <div className="aggregate-rankings">
          <div className="aggregate-header">
            <h4>Council Consensus Leaderboard</h4>
            {useWeightedConsensus && (
              <span className="weighted-badge" title="Weighted by historical performance">
                Weighted
              </span>
            )}
          </div>
          <p className="stage-description">
            Combined peer score across all deliberations (lower score = higher consensus agreement):
          </p>

          <div className="aggregate-list">
            {aggregateRankings.map((agg, index) => (
              <div key={index} className="aggregate-item">
                <span className={`rank-position pos-${index + 1}`}>#{index + 1}</span>
                <span className="rank-model">
                  {formatModelLabel(agg.model)}
                </span>
                <span className="rank-score">
                  {hasWeightedData && agg.weighted_average_rank != null ? (
                    <>
                      <span className="weighted-rank">Score: {agg.weighted_average_rank.toFixed(2)}</span>
                      {agg.rank_change != null && agg.rank_change !== 0 && (
                        <span className={`rank-change ${agg.rank_change > 0 ? 'positive' : 'negative'}`}>
                          ({agg.rank_change > 0 ? '+' : ''}{agg.rank_change.toFixed(2)})
                        </span>
                      )}
                    </>
                  ) : (
                    <>Avg Rank: {agg.average_rank.toFixed(2)}</>
                  )}
                </span>
                <span className="rank-count">
                  ({agg.rankings_count} votes)
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* VIEW MODE 1: Peer Critique Matrix */}
      {viewMode === 'matrix' && (
        <div className="peer-matrix-container">
          <div className="matrix-card">
            <h4>Cross-Model Ranking Matrix</h4>
            <p className="matrix-help">
              Rows are the <strong>Reviewers</strong>, columns are the <strong>Evaluated Peers</strong>. Numbers indicate assigned rank (#1 is best).
            </p>

            <div className="matrix-table-wrap">
              <table className="peer-matrix-table">
                <thead>
                  <tr>
                    <th className="reviewer-header">Evaluator ↓ / Target →</th>
                    {targetModels.map((target, idx) => (
                      <th key={idx} className="target-header">
                        {formatModelLabel(target)}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {rankings.map((r, rIdx) => {
                    const reviewerLabel = formatModelLabel(r.model);
                    // parsed_ranking contains labels like ['Response A', 'Response B']
                    const ranksMap = {};
                    if (r.parsed_ranking && labelToModel) {
                      r.parsed_ranking.forEach((label, pos) => {
                        const m = labelToModel[label];
                        if (m) ranksMap[m] = pos + 1;
                      });
                    }

                    return (
                      <tr key={rIdx}>
                        <td className="reviewer-cell">
                          <strong>{reviewerLabel}</strong>
                        </td>
                        {targetModels.map((target, tIdx) => {
                          const rankNum = ranksMap[target];
                          const isSelf = r.model.split('@')[0] === target.split('@')[0];
                          return (
                            <td key={tIdx} className={`rank-cell ${rankNum ? `rank-pos-${rankNum}` : ''} ${isSelf ? 'self-eval' : ''}`}>
                              {isSelf ? (
                                <span className="self-tag" title="Self-response (anonymized during evaluation)">Self</span>
                              ) : rankNum ? (
                                <span className="matrix-rank-badge">#{rankNum}</span>
                              ) : (
                                <span className="unranked">—</span>
                              )}
                            </td>
                          );
                        })}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* VIEW MODE 2: Detailed Tabs */}
      {viewMode === 'tabs' && (
        <div className="detailed-critiques-container">
          <div className="tabs">
            {rankings.map((rank, index) => (
              <button
                key={index}
                className={`tab ${activeTab === index ? 'active' : ''}`}
                onClick={() => setActiveTab(index)}
              >
                {formatModelLabel(rank.model)}
              </button>
            ))}
          </div>

          <div className="tab-content">
            <div className="ranking-model">
              {formatModelLabel(rankings[activeTab].model)}'s Peer Review
            </div>
            <div className="ranking-content markdown-content">
              <ReactMarkdown>
                {deAnonymizeText(rankings[activeTab].ranking, labelToModel)}
              </ReactMarkdown>
            </div>

            {rankings[activeTab].parsed_ranking &&
             rankings[activeTab].parsed_ranking.length > 0 && (
              <div className="parsed-ranking">
                <strong>Extracted Ranking Order:</strong>
                <ol>
                  {rankings[activeTab].parsed_ranking.map((label, i) => (
                    <li key={i}>
                      {labelToModel && labelToModel[label]
                        ? formatModelLabel(labelToModel[label])
                        : label}
                    </li>
                  ))}
                </ol>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Historical Weights Details Accordion */}
      {useWeightedConsensus && weightsInfo && (
        <div className="weights-summary">
          <button
            className="weights-toggle"
            onClick={() => setShowWeightsDetails(!showWeightsDetails)}
          >
            {showWeightsDetails ? '▼' : '▶'} {weightsInfo.has_historical_data
              ? `${weightsInfo.models_with_history} models with historical reputation (${weightsInfo.weight_range?.min?.toFixed(2)}-${weightsInfo.weight_range?.max?.toFixed(2)})`
              : 'Historical credibility metrics (Equal weights)'}
          </button>
          {showWeightsDetails && weightsInfo.weights && (
            <div className="weights-details">
              {Object.entries(weightsInfo.weights).map(([model, info]) => (
                <div key={model} className="weight-item">
                  <span className="weight-model">{formatModelLabel(model)}</span>
                  <span className="weight-value" title={info.weight_explanation}>
                    {info.normalized_weight?.toFixed(2) || '1.00'}×
                  </span>
                  {info.has_history && (
                    <span className="weight-stats">
                      ({info.win_rate?.toFixed(0)}% win rate, avg rank {info.average_rank?.toFixed(1)})
                    </span>
                  )}
                  {!info.has_history && (
                    <span className="weight-no-history">(first run / no history)</span>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
