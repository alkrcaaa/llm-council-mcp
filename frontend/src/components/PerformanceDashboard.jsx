import { useState, useEffect } from 'react';
import { api } from '../api';
import './PerformanceDashboard.css';

/**
 * PerformanceDashboard - Displays model performance analytics.
 *
 * Shows:
 * - Summary statistics (total queries, unique models, date range)
 * - Model leaderboard sorted by win rate
 * - Detailed per-model statistics (rank distribution, costs, tokens)
 * - Chairman model usage statistics
 *
 * @param {Object} props
 * @param {function} props.onClose - Callback to close the dashboard
 */
export default function PerformanceDashboard({ onClose }) {
  const [analytics, setAnalytics] = useState(null);
  const [chairmanStats, setChairmanStats] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showClearConfirm, setShowClearConfirm] = useState(false);
  const [activeTab, setActiveTab] = useState('leaderboard');

  useEffect(() => {
    loadAnalytics();
  }, []);

  const loadAnalytics = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [analyticsData, chairmanData] = await Promise.all([
        api.getAnalytics(),
        api.getChairmanAnalytics(),
      ]);
      setAnalytics(analyticsData);
      setChairmanStats(chairmanData);
    } catch (err) {
      setError('Failed to load analytics data');
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  };

  const handleClearAnalytics = async () => {
    try {
      await api.clearAnalytics();
      setShowClearConfirm(false);
      loadAnalytics();
    } catch (err) {
      setError('Failed to clear analytics');
      console.error(err);
    }
  };

  const formatDate = (isoString) => {
    if (!isoString) return 'N/A';
    const date = new Date(isoString);
    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
  };

  const formatCost = (cost) => {
    if (cost === 0 || cost === null || cost === undefined) return '$0.00';
    if (cost < 0.01) return `$${cost.toFixed(4)}`;
    return `$${cost.toFixed(2)}`;
  };

  const formatModelDisplay = (model) => {
    if (!model) return '';
    if (model.startsWith('local/')) {
      const name = model.replace('local/', '');
      return (
        <span className="dash-model-badge">
          <span className="dash-local-tag">local/</span>
          <span className="dash-model-name">{name}</span>
        </span>
      );
    }
    const parts = model.split('/');
    if (parts.length > 1) {
      return (
        <span className="dash-model-badge">
          <span className="dash-provider-tag">{parts[0]}/</span>
          <span className="dash-model-name">{parts[1]}</span>
        </span>
      );
    }
    return <span className="dash-model-name">{model}</span>;
  };

  const getWinRateClass = (winRate) => {
    if (winRate >= 50) return 'rate-high';
    if (winRate >= 30) return 'rate-med';
    if (winRate >= 15) return 'rate-fair';
    return 'rate-low';
  };

  const getRankClass = (rank) => {
    if (rank <= 1.5) return 'rank-top';
    if (rank <= 2.5) return 'rank-good';
    if (rank <= 3.5) return 'rank-mid';
    return 'rank-low';
  };

  if (isLoading) {
    return (
      <div className="performance-dashboard">
        <div className="dashboard-header">
          <h2>Performance Dashboard</h2>
          <button className="close-btn" onClick={onClose} aria-label="Close">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <line x1="18" y1="6" x2="6" y2="18"></line>
              <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
          </button>
        </div>
        <div className="dashboard-loading">
          <div className="dash-spinner"></div>
          <span>Loading analytics engine...</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="performance-dashboard">
        <div className="dashboard-header">
          <h2>Performance Dashboard</h2>
          <button className="close-btn" onClick={onClose} aria-label="Close">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <line x1="18" y1="6" x2="6" y2="18"></line>
              <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
          </button>
        </div>
        <div className="dashboard-error">
          <p>{error}</p>
          <button className="retry-btn" onClick={loadAnalytics}>Retry</button>
        </div>
      </div>
    );
  }

  const { models, summary } = analytics || { models: {}, summary: {} };
  const modelList = Object.entries(models);
  const hasData = modelList.length > 0;

  return (
    <div className="performance-dashboard">
      <div className="dashboard-header">
        <h2>Performance Dashboard</h2>
        <button className="close-btn" onClick={onClose} aria-label="Close">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <line x1="18" y1="6" x2="6" y2="18"></line>
            <line x1="6" y1="6" x2="18" y2="18"></line>
          </svg>
        </button>
      </div>

      {/* Summary Section */}
      <div className="dashboard-summary">
        <div className="summary-stat">
          <span className="stat-value">{summary.total_queries || 0}</span>
          <span className="stat-label">Total Queries</span>
        </div>
        <div className="summary-stat">
          <span className="stat-value">{summary.unique_models || 0}</span>
          <span className="stat-label">Unique Models</span>
        </div>
        <div className="summary-stat">
          <span className="stat-value">{chairmanStats?.total_syntheses || 0}</span>
          <span className="stat-label">Syntheses</span>
        </div>
        {summary.date_range?.start && (
          <div className="summary-stat date-range">
            <span className="stat-value">
              {formatDate(summary.date_range.start)} — {formatDate(summary.date_range.end)}
            </span>
            <span className="stat-label">Observation Window</span>
          </div>
        )}
      </div>

      {/* Tabs */}
      <div className="dashboard-tabs">
        <button
          className={`tab-btn ${activeTab === 'leaderboard' ? 'active' : ''}`}
          onClick={() => setActiveTab('leaderboard')}
        >
          Leaderboard
        </button>
        <button
          className={`tab-btn ${activeTab === 'details' ? 'active' : ''}`}
          onClick={() => setActiveTab('details')}
        >
          Model Details
        </button>
        <button
          className={`tab-btn ${activeTab === 'chairman' ? 'active' : ''}`}
          onClick={() => setActiveTab('chairman')}
        >
          Chairman Stats
        </button>
      </div>

      {!hasData ? (
        <div className="no-data">
          <div className="no-data-icon">◈</div>
          <p>No council deliberation records recorded yet.</p>
          <p className="hint">Execute deliberations in the chamber to populate model metrics.</p>
        </div>
      ) : (
        <div className="dashboard-content">
          {/* Leaderboard Tab */}
          {activeTab === 'leaderboard' && (
            <div className="leaderboard">
              <table className="leaderboard-table">
                <thead>
                  <tr>
                    <th className="rank-col">Rank</th>
                    <th className="model-col">Model</th>
                    <th className="stat-col">Win Rate</th>
                    <th className="stat-col">Avg Rank</th>
                    <th className="stat-col">Avg Conf</th>
                    <th className="stat-col">Queries</th>
                  </tr>
                </thead>
                <tbody>
                  {modelList.map(([model, stats], index) => (
                    <tr key={model} className={index < 3 ? 'top-three' : ''}>
                      <td className="rank-col">
                        <span className={`rank-badge rank-${index + 1}`}>
                          {index + 1}
                        </span>
                      </td>
                      <td className="model-col">
                        {formatModelDisplay(model)}
                      </td>
                      <td className="stat-col">
                        <div className="win-rate-cell">
                          <span className={`win-rate ${getWinRateClass(stats.win_rate)}`}>
                            {stats.win_rate}%
                          </span>
                          <span className="wins-count">({stats.wins} wins)</span>
                        </div>
                      </td>
                      <td className="stat-col">
                        <span className={`avg-rank ${getRankClass(stats.average_rank)}`}>
                          {stats.average_rank ? stats.average_rank.toFixed(2) : 'N/A'}
                        </span>
                      </td>
                      <td className="stat-col">
                        {stats.average_confidence !== null ? (
                          <span className="confidence">{stats.average_confidence.toFixed(1)}/10</span>
                        ) : (
                          <span className="na">—</span>
                        )}
                      </td>
                      <td className="stat-col queries">
                        {stats.total_queries}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Model Details Tab */}
          {activeTab === 'details' && (
            <div className="model-details">
              {modelList.map(([model, stats]) => (
                <div key={model} className="model-card">
                  <div className="model-card-header">
                    <div className="model-card-title">
                      {formatModelDisplay(model)}
                    </div>
                    <span className={`win-badge ${getWinRateClass(stats.win_rate)}`}>
                      {stats.win_rate}% win rate
                    </span>
                  </div>
                  <div className="model-card-stats">
                    <div className="stat-group">
                      <div className="stat-group-header">Performance Metrics</div>
                      <div className="stat-row">
                        <span className="stat-row-label">Consensus Wins:</span>
                        <span className="stat-row-val">{stats.wins} / {stats.total_queries}</span>
                      </div>
                      <div className="stat-row">
                        <span className="stat-row-label">Average Rank:</span>
                        <span className={`stat-row-val ${getRankClass(stats.average_rank)}`}>
                          {stats.average_rank ? stats.average_rank.toFixed(2) : 'N/A'}
                        </span>
                      </div>
                      <div className="stat-row">
                        <span className="stat-row-label">Avg Confidence:</span>
                        <span className="stat-row-val">
                          {stats.average_confidence !== null ? `${stats.average_confidence.toFixed(1)}/10` : 'N/A'}
                        </span>
                      </div>
                    </div>
                    <div className="stat-group">
                      <div className="stat-group-header">Resource Consumption</div>
                      <div className="stat-row">
                        <span className="stat-row-label">Total Cost:</span>
                        <span className="stat-row-val mono-accent">{formatCost(stats.total_cost)}</span>
                      </div>
                      <div className="stat-row">
                        <span className="stat-row-label">Total Tokens:</span>
                        <span className="stat-row-val">{stats.total_tokens?.toLocaleString() || 0}</span>
                      </div>
                      <div className="stat-row">
                        <span className="stat-row-label">Deliberation Runs:</span>
                        <span className="stat-row-val">{stats.total_queries}</span>
                      </div>
                    </div>
                    {stats.rank_distribution && Object.keys(stats.rank_distribution).length > 0 && (
                      <div className="stat-group rank-dist-group">
                        <div className="stat-group-header">Rank Distribution</div>
                        <div className="rank-distribution">
                          {Object.entries(stats.rank_distribution).map(([rank, count]) => (
                            <div key={rank} className="rank-bar-container">
                              <div className="rank-bar-bg">
                                <div
                                  className={`rank-bar rank-${rank}`}
                                  style={{
                                    height: `${Math.max(8, (count / Math.max(1, stats.total_queries)) * 100)}%`,
                                  }}
                                  title={`Rank #${rank}: ${count} times`}
                                />
                              </div>
                              <span className="rank-label">#{rank}</span>
                              <span className="rank-count">{count}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Chairman Stats Tab */}
          {activeTab === 'chairman' && (
            <div className="chairman-stats">
              <p className="chairman-intro">
                The Chairman model synthesizes the final council verdict by analyzing peer cross-examinations and consensus rankings.
              </p>
              {chairmanStats && Object.keys(chairmanStats.models).length > 0 ? (
                <table className="chairman-table">
                  <thead>
                    <tr>
                      <th className="model-col">Chairman Model</th>
                      <th className="stat-col">Syntheses Presided</th>
                      <th className="stat-col">Cumulative Cost</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(chairmanStats.models).map(([model, stats]) => (
                      <tr key={model}>
                        <td className="model-col">
                          {formatModelDisplay(model)}
                        </td>
                        <td className="stat-col">{stats.times_used}</td>
                        <td className="stat-col mono-accent">{formatCost(stats.total_cost)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <div className="no-chairman-data">
                  <p>No chairman syntheses recorded yet.</p>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Footer Actions */}
      <div className="dashboard-footer">
        <button className="refresh-btn" onClick={loadAnalytics}>
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="23 4 23 10 17 10"></polyline>
            <polyline points="1 20 1 14 7 14"></polyline>
            <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"></path>
          </svg>
          Refresh Data
        </button>
        {hasData && (
          <>
            {showClearConfirm ? (
              <div className="clear-confirm">
                <span>Permanently clear analytics history?</span>
                <button className="confirm-yes" onClick={handleClearAnalytics}>
                  Yes, Clear
                </button>
                <button className="confirm-no" onClick={() => setShowClearConfirm(false)}>
                  Cancel
                </button>
              </div>
            ) : (
              <button
                className="clear-btn"
                onClick={() => setShowClearConfirm(true)}
              >
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <polyline points="3 6 5 6 21 6"></polyline>
                  <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                </svg>
                Clear Data
              </button>
            )}
          </>
        )}
      </div>
    </div>
  );
}
