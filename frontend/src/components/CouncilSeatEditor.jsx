// Panel contents for the Council Deliberation table: seat editor, external chairman note and
// the "new seat" form. Council seats have no role prompt or MCP tools, so this is smaller than
// SeatEditor in RosterSeatCard.
import { useState } from 'react';
import './RosterSeatCard.css';

function nameOf(model) {
  const base = model.split('@')[0];
  const idx = base.indexOf('/');
  return idx > 0 ? base.slice(idx + 1) : base;
}

export function SkillSelect({ value, skills, noneLabel, onChange }) {
  return (
    <select value={value} onChange={(e) => onChange(e.target.value)}>
      <option value="">{noneLabel}</option>
      {skills.map((s) => (
        <option key={s.id} value={s.id}>
          {s.badge ? `[${s.badge}] ` : ''}{s.title}
        </option>
      ))}
    </select>
  );
}

export function CouncilSeatEditor({
  model,
  isChairman,
  canRemove,
  canMoveUp,
  canMoveDown,
  skills,
  modelOptions,
  onModelChange,
  onSkillChange,
  onReadSkill,
  onMakeChairman,
  onOpenPersona,
  onMoveUp,
  onMoveDown,
  onRemove,
}) {
  const [baseModel, skillId = ''] = model.split('@');
  return (
    <div className="seat-drawer">
      <div className="seat-fields">
        <div className="seat-field">
          <label>Model</label>
          <select value={baseModel} onChange={(e) => onModelChange(e.target.value)}>
            {modelOptions}
          </select>
        </div>
        <div className="seat-field">
          <label>Domain skill for {nameOf(baseModel)}</label>
          <div className="seat-skill-row">
            <SkillSelect value={skillId} skills={skills} noneLabel="No domain skill (default)" onChange={onSkillChange} />
            {skillId && (
              <button type="button" className="seat-link-btn" onClick={onReadSkill}>
                Read skill
              </button>
            )}
          </div>
        </div>
      </div>

      <div className="seat-drawer-foot">
        {isChairman ? (
          <span className="seat-tag lead">Chairman</span>
        ) : (
          <button type="button" className="seat-btn" onClick={onMakeChairman}>
            Make chairman
          </button>
        )}
        <button type="button" className="seat-btn" onClick={onOpenPersona}>
          Avatar and name
        </button>
        <button type="button" className="seat-btn" disabled={!canMoveUp} onClick={onMoveUp}>
          Seat earlier
        </button>
        <button type="button" className="seat-btn" disabled={!canMoveDown} onClick={onMoveDown}>
          Seat later
        </button>
        <button
          type="button"
          className="seat-btn danger"
          disabled={!canRemove}
          title={canRemove ? 'Remove seat' : 'A council needs at least 2 seats'}
          onClick={onRemove}
        >
          Remove from table
        </button>
      </div>
    </div>
  );
}

export function ExternalChairmanNote({ model }) {
  return (
    <div className="seat-drawer">
      <div className="seat-fields">
        <div className="seat-field">
          <label>Chairman: {nameOf(model)}</label>
          <p className="seat-hint">
            This chairman is not one of the seats; it only writes the Stage 3 verdict. Change it with the
            Chairman selector below the table, or make one of the seated models chairman.
          </p>
        </div>
      </div>
    </div>
  );
}

// Seat a new model. Shared by Council and Round Table; `onAdd(model, skillId)` does the work.
export function AddSeatPanel({ modelOptions, skills, addLabel = 'Seat at table', onAdd, onClose }) {
  const [model, setModel] = useState('');
  const [skillId, setSkillId] = useState('');
  return (
    <div className="seat-drawer">
      <div className="seat-fields">
        <div className="seat-field">
          <label>Model</label>
          <select value={model} onChange={(e) => setModel(e.target.value)}>
            <option value="">Select a model...</option>
            {modelOptions}
          </select>
        </div>
        <div className="seat-field">
          <label>Domain skill (optional)</label>
          <SkillSelect value={skillId} skills={skills} noneLabel="No domain skill (default)" onChange={setSkillId} />
        </div>
      </div>
      <div className="seat-drawer-foot">
        <button
          type="button"
          className="seat-btn primary"
          disabled={!model}
          onClick={() => {
            onAdd(model, skillId || null);
            setModel('');
            setSkillId('');
          }}
        >
          {addLabel}
        </button>
        <button type="button" className="seat-btn" onClick={onClose}>
          Cancel
        </button>
      </div>
    </div>
  );
}
