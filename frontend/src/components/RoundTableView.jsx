import { Children } from 'react';
import './RoundTableView.css';

function nameOf(model) {
  const base = model.split('@')[0];
  const idx = base.indexOf('/');
  return idx > 0 ? base.slice(idx + 1) : base;
}

function providerOf(model) {
  const base = model.split('@')[0];
  const idx = base.indexOf('/');
  return idx > 0 ? base.slice(0, idx) : '';
}

function monogram(model) {
  // qwen3.6-27b and qwen3.8-27b must not both read "QW": digits tell versions apart.
  const name = nameOf(model);
  const letters = name.replace(/[^a-zA-Z]/g, '');
  const digits = name.replace(/\D/g, '').slice(0, 2);
  const mark = digits ? letters.slice(0, 1) + digits : letters.slice(0, 2);
  return (mark || '?').toUpperCase();
}

// Stable tint per model so seats are told apart at a glance without a palette to maintain.
function hueOf(model) {
  const base = model.split('@')[0];
  let h = 0;
  for (let i = 0; i < base.length; i += 1) h = (h * 31 + base.charCodeAt(i)) % 360;
  return h;
}

// Seats sit clockwise from the head of the table (top). The lead/chairman takes the head, so
// it is rotated to the front of the drawing order; `index` always refers to the real roster.
// Open chairs continue the circle after the occupied ones.
function layout(seats, emptyCount) {
  const leadAt = Math.max(0, seats.findIndex((s) => s.isLead));
  const ordered = [...seats.slice(leadAt), ...seats.slice(0, leadAt)];
  return { ordered, slots: ordered.length + emptyCount };
}

// Armchair seen from above, drawn with the back at the top and rotated around the cushion
// centre so the back always faces away from the table.
function Chair() {
  return (
    <svg className="rtv-chair" viewBox="0 0 120 120" aria-hidden="true">
      <rect className="rtv-chair-arm" x="9" y="52" width="16" height="52" rx="8" />
      <rect className="rtv-chair-arm" x="95" y="52" width="16" height="52" rx="8" />
      <rect className="rtv-chair-seat" x="22" y="42" width="76" height="64" rx="22" />
      <rect className="rtv-chair-back" x="14" y="14" width="92" height="30" rx="15" />
    </svg>
  );
}

function RoundTableView({
  kicker = 'Round Table',
  title,
  leadLabel = 'Lead',
  seats,
  capacity = 8,
  selectedIndex,
  adding = false,
  onSelect,
  onAddSeat,
  children,
}) {
  const emptyCount = onAddSeat ? Math.max(capacity - seats.length, 1) : 0;
  const { ordered, slots } = layout(seats, emptyCount);
  const angleOf = (slot) => -Math.PI / 2 + (slot * 2 * Math.PI) / slots;
  const rotOf = (slot) => `${(angleOf(slot) * 180) / Math.PI + 90}deg`;
  // The name plate sits on the table side of the chair, so it never covers the backrest. Its
  // distance is the avatar radius plus how far the plate reaches along that direction
  // (plate is ~100 x 36px), which keeps it clear of the avatar at every angle.
  const placement = (slot) => {
    const cos = Math.cos(angleOf(slot));
    const sin = Math.sin(angleOf(slot));
    const dist = 36 + 50 * Math.abs(cos) + 18 * Math.abs(sin);
    return {
      left: `${50 + 38 * cos}%`,
      top: `${50 + 34 * sin}%`,
      '--rot': rotOf(slot),
      '--px': `${-cos * dist}px`,
      '--py': `${-sin * dist}px`,
      '--i': slot,
    };
  };
  const hasPanel = Children.toArray(children).length > 0;
  // A book lies on the table in front of each seated agent; the table ellipse is 62% x 50%.
  const bookPlacement = (slot) => ({
    left: `${50 + 12 * Math.cos(angleOf(slot))}%`,
    top: `${50 + 10 * Math.sin(angleOf(slot))}%`,
    '--rot': rotOf(slot),
  });
  const lead = seats.find((s) => s.isLead);

  return (
    <div className="rtv">
      <div className="rtv-stage">
        <div className="rtv-caption">
          <span className="rtv-table-kicker">{kicker}</span>
          <span className="rtv-table-title">{title}</span>
          <span className="rtv-table-meta">
            {seats.filter((s) => !s.external).length} seated
            {lead ? ` / ${leadLabel.toLowerCase()} ${nameOf(lead.model)}` : ''}
          </span>
        </div>

        <div className="rtv-table" aria-hidden="true" />

        <div className="rtv-books" aria-hidden="true">
          {ordered.map((seat, slot) => (
            <svg
              key={seat.key}
              className={`rtv-book ${seat.isLead ? 'is-lead' : ''}`}
              style={{ ...bookPlacement(slot), '--hue': hueOf(seat.model) }}
              viewBox="0 0 32 24"
            >
              <rect className="rtv-book-cover" x="1" y="1" width="30" height="22" rx="2.5" />
              <path className="rtv-book-spine" d="M6 1 V23" />
              <path className="rtv-book-lines" d="M11 8 H26 M11 12 H26 M11 16 H22" />
            </svg>
          ))}
        </div>

        <ul className="rtv-seats">
          {ordered.map((seat, slot) => {
            const selected = seat.index === selectedIndex;
            // second plate line: the most telling fact about the seat, the rest lives in the panel
            const sub = seat.isLead
              ? leadLabel
              : seat.skillTitle || (seat.toolCount > 0 ? `${seat.toolCount} MCP` : '') || providerOf(seat.model) || 'model';
            return (
              <li key={seat.key} className="rtv-seat-slot" style={placement(slot)}>
                <button
                  type="button"
                  className={`rtv-seat ${selected ? 'is-selected' : ''} ${seat.isLead ? 'is-lead' : ''}`}
                  style={{ '--hue': hueOf(seat.model) }}
                  aria-pressed={selected}
                  aria-label={`${seat.external ? leadLabel : `Seat ${seat.index + 1}`}: ${nameOf(seat.model)}${seat.isLead && !seat.external ? `, ${leadLabel.toLowerCase()}` : ''}`}
                  onClick={() => onSelect(selected ? null : seat.index)}
                >
                  <Chair />
                  <span className="rtv-avatar">
                    <span className="rtv-monogram">{monogram(seat.model)}</span>
                    <span className="rtv-seal">{seat.external ? 'CH' : String(seat.index + 1).padStart(2, '0')}</span>
                  </span>
                  <span className="rtv-plate">
                    <span className="rtv-seat-name">{nameOf(seat.model)}</span>
                    <span className="rtv-seat-provider">{sub}</span>
                  </span>
                </button>
              </li>
            );
          })}
          {Array.from({ length: emptyCount }, (_, n) => {
            const slot = ordered.length + n;
            const first = n === 0;
            return (
              <li key={`open-${n}`} className="rtv-seat-slot" style={placement(slot)}>
                <button
                  type="button"
                  className={`rtv-seat rtv-seat-add ${adding && first ? 'is-selected' : ''}`}
                  aria-label="Open seat: add a model"
                  onClick={onAddSeat}
                >
                  <Chair />
                  <span className="rtv-avatar rtv-avatar-empty">
                    <span className="rtv-monogram">+</span>
                  </span>
                  <span className="rtv-plate">
                    <span className="rtv-seat-name">Open seat</span>
                    <span className="rtv-seat-provider">click to fill</span>
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      </div>

      <aside className={`rtv-panel ${hasPanel ? 'is-open' : ''}`}>
        {hasPanel ? children : (
          <div className="rtv-panel-empty">
            <span className="rtv-panel-empty-title">Select a seat</span>
            <span>Click an agent to edit it, or an open chair to seat a new model.</span>
          </div>
        )}
      </aside>
    </div>
  );
}

export default RoundTableView;
