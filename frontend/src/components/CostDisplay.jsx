import './CostDisplay.css';

/**
 * CostDisplay - Shows token usage and cost breakdown for a council query.
 *
 * Displays costs per stage (Stage 1, Stage 2, Stage 3) and total costs.
 * Shows both token counts and USD costs with appropriate formatting.
 *
 * @param {Object} props
 * @param {Object} props.costs - Cost summary object from API response
 *   Contains stage1, stage2, stage3, and total summaries
 * @param {boolean} props.expanded - Whether to show detailed breakdown (default: false)
 */
export default function CostDisplay({ costs, expanded = false }) {
  if (!costs || !costs.total) {
    return null;
  }

  const { stage1, stage2, stage3, total } = costs;

  // Format cost for display
  const formatCost = (cost) => {
    if (cost === undefined || cost === null) return '$0.0000';
    if (cost < 0.0001) return '<$0.0001';
    if (cost < 0.01) return `$${cost.toFixed(4)}`;
    if (cost < 1.00) return `$${cost.toFixed(3)}`;
    return `$${cost.toFixed(2)}`;
  };

  // Format token count with commas
  const formatTokens = (count) => {
    if (count === undefined || count === null) return '0';
    return count.toLocaleString();
  };

  // Calculate percentage of total for each stage
  const getPercentage = (stageCost) => {
    if (!total.total_cost || total.total_cost === 0) return 0;
    return ((stageCost / total.total_cost) * 100).toFixed(1);
  };

  // Simple compact view (just total)
  if (!expanded) {
    return (
      <div className="cost-display cost-display-compact">
        <div className="cost-summary">
          <span className="cost-label">Query Cost:</span>
          <span className="cost-value">{formatCost(total.total_cost)}</span>
          <span className="cost-tokens">
            ({formatTokens(total.total_tokens)} tokens)
          </span>
        </div>
      </div>
    );
  }

  // Expanded view with breakdown
  return (
    <div className="cost-display cost-display-expanded">
      <div className="cost-header">
        <h4 className="cost-title">Cost Breakdown</h4>
        <div className="cost-total">
          <span className="cost-total-label">Total:</span>
          <span className="cost-total-value">{formatCost(total.total_cost)}</span>
        </div>
      </div>

      <div className="cost-stages">
        {costs.debate ? (
          <div className="cost-stage">
            <div className="cost-stage-header">
              <span className="cost-stage-name">Council Debate (Münazara)</span>
              <span className="cost-stage-value">{formatCost(total.total_cost ?? total.total)}</span>
              <span className="cost-stage-percent">(100%)</span>
            </div>
            <div className="cost-stage-details">
              <span className="cost-detail">
                {formatTokens(total.total_prompt_tokens ?? total.prompt_tokens ?? 0)} prompt +{' '}
                {formatTokens(total.total_completion_tokens ?? total.completion_tokens ?? 0)} completion
              </span>
              <span className="cost-detail-models">Multi-Round Debate & Chairman</span>
            </div>
          </div>
        ) : (
          <>
            {/* Stage 1 */}
            <div className="cost-stage">
              <div className="cost-stage-header">
                <span className="cost-stage-name">Stage 1</span>
                <span className="cost-stage-value">{formatCost(stage1?.total_cost)}</span>
                <span className="cost-stage-percent">({getPercentage(stage1?.total_cost)}%)</span>
              </div>
              <div className="cost-stage-details">
                <span className="cost-detail">
                  {formatTokens(stage1?.total_prompt_tokens)} prompt +{' '}
                  {formatTokens(stage1?.total_completion_tokens)} completion
                </span>
                <span className="cost-detail-models">
                  {stage1?.model_count} model{stage1?.model_count !== 1 ? 's' : ''}
                </span>
              </div>
            </div>

            {/* Stage 2 */}
            <div className="cost-stage">
              <div className="cost-stage-header">
                <span className="cost-stage-name">Stage 2</span>
                <span className="cost-stage-value">{formatCost(stage2?.total_cost)}</span>
                <span className="cost-stage-percent">({getPercentage(stage2?.total_cost)}%)</span>
              </div>
              <div className="cost-stage-details">
                <span className="cost-detail">
                  {formatTokens(stage2?.total_prompt_tokens)} prompt +{' '}
                  {formatTokens(stage2?.total_completion_tokens)} completion
                </span>
                <span className="cost-detail-models">
                  {stage2?.model_count} model{stage2?.model_count !== 1 ? 's' : ''}
                </span>
              </div>
            </div>

            {/* Stage 3 */}
            <div className="cost-stage">
              <div className="cost-stage-header">
                <span className="cost-stage-name">Stage 3</span>
                <span className="cost-stage-value">{formatCost(stage3?.total_cost)}</span>
                <span className="cost-stage-percent">({getPercentage(stage3?.total_cost)}%)</span>
              </div>
              <div className="cost-stage-details">
                <span className="cost-detail">
                  {formatTokens(stage3?.total_prompt_tokens)} prompt +{' '}
                  {formatTokens(stage3?.total_completion_tokens)} completion
                </span>
                <span className="cost-detail-models">Chairman</span>
              </div>
            </div>
          </>
        )}
      </div>

      <div className="cost-footer">
        <div className="cost-footer-item">
          <span className="cost-footer-label">Total Tokens:</span>
          <span className="cost-footer-value">
            {formatTokens(total.total_tokens ?? ((total.prompt_tokens || 0) + (total.completion_tokens || 0)))}
          </span>
        </div>
        <div className="cost-footer-item">
          <span className="cost-footer-label">Input Cost:</span>
          <span className="cost-footer-value">{formatCost(total.total_input_cost ?? total.input_cost ?? 0)}</span>
        </div>
        <div className="cost-footer-item">
          <span className="cost-footer-label">Output Cost:</span>
          <span className="cost-footer-value">{formatCost(total.total_output_cost ?? total.output_cost ?? total.total ?? total.total_cost ?? 0)}</span>
        </div>
      </div>
    </div>
  );
}


/**
 * ModelCostBadge - Inline cost badge for individual model responses.
 *
 * Shows a small badge with token count and cost for a single model response.
 *
 * @param {Object} props
 * @param {Object} props.usage - Usage object with prompt_tokens, completion_tokens
 * @param {Object} props.cost - Cost object with total_cost
 */
export function ModelCostBadge({ usage, cost }) {
  if (!usage && !cost) {
    return null;
  }

  const formatCost = (value) => {
    if (!value || value < 0.0001) return '<$0.0001';
    if (value < 0.01) return `$${value.toFixed(4)}`;
    return `$${value.toFixed(3)}`;
  };

  const totalTokens = usage?.total_tokens || 0;
  const totalCost = cost?.total_cost || 0;

  return (
    <span className="model-cost-badge" title={`${totalTokens.toLocaleString()} tokens`}>
      <span className="model-cost-tokens">{totalTokens.toLocaleString()} tok</span>
      <span className="model-cost-divider">·</span>
      <span className="model-cost-value">{formatCost(totalCost)}</span>
    </span>
  );
}
