import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import './Stage2.css';

function formatModelLabel(model) {
  if (!model) return '';
  const [baseModel, skillId = ''] = model.split('@');
  const shortName = baseModel.split('/')[1] || baseModel;
  if (!skillId) return shortName;

  let skillTitle = skillId;
  if (skillId.includes('security')) skillTitle = 'Security';
  else if (skillId.includes('karpathy') || skillId.includes('architect')) skillTitle = 'Architect';
  else if (skillId.includes('devops')) skillTitle = 'DevOps';
  else if (skillId.includes('testing') || skillId.includes('qa')) skillTitle = 'Quality';
  else if (skillId.includes('review')) skillTitle = 'Review';
  else {
    skillTitle = skillId.replace(/-(guidelines|handbook|audit|security)/g, '');
    skillTitle = skillTitle.charAt(0).toUpperCase() + skillTitle.slice(1);
  }

  return `${shortName} [${skillTitle}]`;
}

function deAnonymizeText(text, labelToModel) {
  if (!labelToModel) return text;

  let result = text;
  // Replace each "Response X" with the actual model name + specialist tag
  Object.entries(labelToModel).forEach(([label, model]) => {
    const labelFormatted = formatModelLabel(model);
    result = result.replace(new RegExp(label, 'g'), `**${labelFormatted}**`);
  });
  return result;
}

export default function Stage2({ rankings, labelToModel, aggregateRankings, useWeightedConsensus, weightsInfo }) {
  const [activeTab, setActiveTab] = useState(0);
  const [showWeightsDetails, setShowWeightsDetails] = useState(false);

  if (!rankings || rankings.length === 0) {
    return null;
  }

  // Check if weighted consensus is active and has historical data
  const hasWeightedData = useWeightedConsensus && weightsInfo?.has_historical_data;

  return (
    <div className="stage stage2">
      <h3 className="stage-title">Stage 2: Peer Rankings</h3>

      <h4>Raw Evaluations</h4>
      <p className="stage-description">
        Each model evaluated all responses (anonymized as Response A, B, C, etc.) and provided rankings.
        Below, model names are shown in <strong>bold</strong> for readability, but the original evaluation used anonymous labels.
      </p>

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
          {formatModelLabel(rankings[activeTab].model)}
        </div>
        <div className="ranking-content markdown-content">
          <ReactMarkdown>
            {deAnonymizeText(rankings[activeTab].ranking, labelToModel)}
          </ReactMarkdown>
        </div>

        {rankings[activeTab].parsed_ranking &&
         rankings[activeTab].parsed_ranking.length > 0 && (
          <div className="parsed-ranking">
            <strong>Extracted Ranking:</strong>
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

      {aggregateRankings && aggregateRankings.length > 0 && (
        <div className="aggregate-rankings">
          <div className="aggregate-header">
            <h4>Aggregate Rankings (Street Cred)</h4>
            {useWeightedConsensus && (
              <span className="weighted-badge" title="Weighted by historical performance">
                Weighted
              </span>
            )}
          </div>
          <p className="stage-description">
            Combined results across all peer evaluations (lower score is better)
            {hasWeightedData && ' - weighted by historical model performance'}:
          </p>

          {/* Weights Summary Section */}
          {useWeightedConsensus && weightsInfo && (
            <div className="weights-summary">
              <button
                className="weights-toggle"
                onClick={() => setShowWeightsDetails(!showWeightsDetails)}
              >
                {showWeightsDetails ? '▼' : '▶'} {weightsInfo.has_historical_data
                  ? `${weightsInfo.models_with_history} models with history (weights ${weightsInfo.weight_range?.min?.toFixed(2)}-${weightsInfo.weight_range?.max?.toFixed(2)})`
                  : 'No historical data yet (equal weights)'}
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
                          ({info.win_rate?.toFixed(0)}% wins, avg rank {info.average_rank?.toFixed(1)})
                        </span>
                      )}
                      {!info.has_history && (
                        <span className="weight-no-history">(no history)</span>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          <div className="aggregate-list">
            {aggregateRankings.map((agg, index) => (
              <div key={index} className="aggregate-item">
                <span className="rank-position">#{index + 1}</span>
                <span className="rank-model">
                  {formatModelLabel(agg.model)}
                </span>
                <span className="rank-score">
                  {hasWeightedData && agg.weighted_average_rank != null ? (
                    <>
                      <span className="weighted-rank">Weighted: {agg.weighted_average_rank.toFixed(2)}</span>
                      {agg.rank_change != null && agg.rank_change !== 0 && (
                        <span className={`rank-change ${agg.rank_change > 0 ? 'positive' : 'negative'}`}>
                          ({agg.rank_change > 0 ? '+' : ''}{agg.rank_change.toFixed(2)})
                        </span>
                      )}
                    </>
                  ) : (
                    <>Avg: {agg.average_rank.toFixed(2)}</>
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
    </div>
  );
}
