import { useState, useEffect, useRef } from 'react';
import './ProcessMonitor.css';

/**
 * ProcessMonitor - Side panel showing real-time council deliberation events.
 *
 * Features:
 * - Verbosity knob (0-3) to control event detail level
 * - Auto-scrolling event log
 * - Color-coded events by category
 * - Timestamps for each event
 * - Collapsible panel
 *
 * @param {Object} props
 * @param {Array} props.events - Array of process events to display
 * @param {number} props.verbosity - Current verbosity level (0-3)
 * @param {function} props.onVerbosityChange - Callback when verbosity changes
 * @param {boolean} props.isOpen - Whether the panel is open
 * @param {function} props.onToggle - Callback to toggle panel open/closed
 */
export default function ProcessMonitor({
  events = [],
  verbosity = 0,
  onVerbosityChange,
  isOpen = false,
  onToggle,
}) {
  const eventListRef = useRef(null);
  const [autoScroll, setAutoScroll] = useState(true);

  // Auto-scroll to bottom when new events arrive
  useEffect(() => {
    if (autoScroll && eventListRef.current) {
      eventListRef.current.scrollTop = eventListRef.current.scrollHeight;
    }
  }, [events, autoScroll]);

  // Handle scroll to detect if user scrolled up
  const handleScroll = () => {
    if (eventListRef.current) {
      const { scrollTop, scrollHeight, clientHeight } = eventListRef.current;
      const isAtBottom = scrollHeight - scrollTop - clientHeight < 50;
      setAutoScroll(isAtBottom);
    }
  };

  const formatTimestamp = (isoString) => {
    const date = new Date(isoString);
    return date.toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false,
    });
  };

  const getCategoryIcon = (category) => {
    switch (category) {
      case 'stage':
        return <span className="cat-icon cat-stage">◈</span>;
      case 'model':
        return <span className="cat-icon cat-model">◇</span>;
      case 'success':
        return <span className="cat-icon cat-success">✓</span>;
      case 'warning':
        return <span className="cat-icon cat-warning">▲</span>;
      case 'error':
        return <span className="cat-icon cat-error">✕</span>;
      case 'data':
        return <span className="cat-icon cat-data">▤</span>;
      case 'info':
      default:
        return <span className="cat-icon cat-info">•</span>;
    }
  };

  const verbosityLabels = [
    '0 • Kapalı (Sessiz)',
    '1 • Aşamalar (Milestones)',
    '2 • Metrikler & Hız',
    '3 • Ham Canlı Akış',
  ];

  const verbosityDescriptions = [
    'Minimal: Sadece oturum başlangıcı ve nihai hakem sentezi bildirilir; ara loglar gizlenir.',
    'Aşamalar: Konsey aşama geçişleri (1. Aşama Bağımsız Görüşler → 2. Aşama Çapraz İnceleme → 3. Aşama Sentez).',
    'Metrikler: Model yanıt gecikmeleri (ms), token üretim hızları ve oylama konsensüs verileri.',
    'Ham Akış: Modellerden dönen anlık token parçacıkları ve SSE telemetri olayları.',
  ];

  if (!isOpen) {
    return (
      <button
        className="process-monitor-toggle collapsed"
        onClick={onToggle}
        title="Canlı Telemetri Panelini Aç"
      >
        <span className="toggle-icon">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="15 18 9 12 15 6"></polyline>
          </svg>
        </span>
        <span className="toggle-label">TELEMETRY</span>
        {events.length > 0 && (
          <span className="event-count">{events.length}</span>
        )}
      </button>
    );
  }

  return (
    <aside className="process-monitor" aria-label="Process Monitor">
      <div className="process-monitor-header">
        <div className="header-title">
          <div className="title-with-pill">
            <span className="pulse-indicator"></span>
            <div>
              <h3 style={{ margin: 0, fontSize: '13px' }}>Canlı Süreç Telemetrisi</h3>
              <span style={{ fontSize: '10px', color: '#8b949e' }}>Modellerin anlık düşünce ve aşama akışı</span>
            </div>
          </div>
          <button
            className="close-btn"
            onClick={onToggle}
            title="Paneli Kapat (Esc)"
            aria-label="Collapse Process Monitor"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="9 18 15 12 9 6"></polyline>
            </svg>
          </button>
        </div>
        <div className="verbosity-control">
          <div className="verbosity-header">
            <label>Telemetri Detay Seviyesi</label>
            <span className="verbosity-label">{verbosityLabels[verbosity]}</span>
          </div>
          <div className="verbosity-slider">
            <input
              type="range"
              min="0"
              max="3"
              value={verbosity}
              onChange={(e) => onVerbosityChange(parseInt(e.target.value, 10))}
              aria-label="Verbosity range"
            />
          </div>
          <div className="verbosity-dots">
            {[0, 1, 2, 3].map((level) => (
              <button
                key={level}
                className={`verbosity-dot ${verbosity >= level ? 'active' : ''} ${verbosity === level ? 'current' : ''}`}
                onClick={() => onVerbosityChange(level)}
                title={`Seviye ${level}: ${verbosityLabels[level]}`}
              >
                {level}
              </button>
            ))}
          </div>
          <div className="verbosity-description-box">
            <span className="desc-icon">💡</span>
            <span className="desc-text">{verbosityDescriptions[verbosity]}</span>
          </div>
        </div>
      </div>

      <div
        className="event-list"
        ref={eventListRef}
        onScroll={handleScroll}
      >
        {verbosity === 0 ? (
          <div className="no-events-message">
            <span className="no-events-icon">◎</span>
            <p>Telemetri Duraklatıldı (Sessiz Mod)</p>
            <p className="hint">Canlı model yanıtlarını, aşama geçişlerini ve konsensüs skorlarını izlemek için yukarıdaki seviyeyi (1-3) yükseltin.</p>
          </div>
        ) : events.length === 0 ? (
          <div className="no-events-message">
            <span className="no-events-icon">◈</span>
            <p>Canlı Dinleme Hazır</p>
            <p className="hint">Sohbet alanından bir soru gönderdiğinizde konsey üyelerinin paralel yanıt üretimi, çapraz değerlendirmeleri ve hakem sentezi burada canlı akacaktır.</p>
          </div>
        ) : (

          events.map((event, index) => (
            <div
              key={index}
              className={`event-item category-${event.category || 'info'}`}
            >
              <div className="event-icon-wrapper">
                {getCategoryIcon(event.category)}
              </div>
              <div className="event-body">
                <span className="event-time">
                  {formatTimestamp(event.timestamp)}
                </span>
                <span className="event-message">{event.message}</span>
              </div>
            </div>
          ))
        )}
      </div>

      {events.length > 0 && (
        <div className="process-monitor-footer">
          <span className="event-count-label">
            <span className="count-num">{events.length}</span> event{events.length !== 1 ? 's' : ''} recorded
          </span>
          {!autoScroll && (
            <button
              className="scroll-to-bottom"
              onClick={() => {
                setAutoScroll(true);
                if (eventListRef.current) {
                  eventListRef.current.scrollTop = eventListRef.current.scrollHeight;
                }
              }}
            >
              <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="6 9 12 15 18 9"></polyline>
              </svg>
              Latest
            </button>
          )}
        </div>
      )}
    </aside>
  );
}

/**
 * VerbosityControl - Standalone verbosity control component.
 *
 * Can be used separately from the ProcessMonitor panel.
 *
 * @param {Object} props
 * @param {number} props.verbosity - Current verbosity level (0-3)
 * @param {function} props.onChange - Callback when verbosity changes
 * @param {boolean} props.compact - Use compact display mode
 */
export function VerbosityControl({ verbosity, onChange, compact = false }) {
  const verbosityLabels = ['Off', 'Basic', 'Standard', 'Verbose'];

  if (compact) {
    return (
      <div className="verbosity-control-compact">
        <label title="Process Monitor Verbosity">V:</label>
        <select
          value={verbosity}
          onChange={(e) => onChange(parseInt(e.target.value, 10))}
        >
          {verbosityLabels.map((label, level) => (
            <option key={level} value={level}>
              {label}
            </option>
          ))}
        </select>
      </div>
    );
  }

  return (
    <div className="verbosity-control-inline">
      <span className="label">Telemetry:</span>
      <div className="verbosity-buttons">
        {verbosityLabels.map((label, level) => (
          <button
            key={level}
            className={`verbosity-btn ${verbosity === level ? 'active' : ''}`}
            onClick={() => onChange(level)}
            title={`${label} - Level ${level}`}
          >
            {level}
          </button>
        ))}
      </div>
    </div>
  );
}
