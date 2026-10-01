import { useState } from 'react';
import './RosterSeatCard.css';

const SECTIONS = [
  { id: 'model', label: 'Model' },
  { id: 'role', label: 'Role' },
  { id: 'tools', label: 'Tools' },
];

function nameOf(baseModel) {
  const idx = baseModel.indexOf('/');
  return idx > 0 ? baseModel.slice(idx + 1) : baseModel;
}

function ToolsSection({ servers, loading, selected, onChange, onOpenMcpTab }) {
  const toggle = (name) =>
    onChange(selected.includes(name) ? selected.filter((n) => n !== name) : [...selected, name]);

  const setMany = (names, on) => {
    const rest = selected.filter((n) => !names.includes(n));
    onChange(on ? [...rest, ...names] : rest);
  };

  return (
    <div className="seat-tools">
      <p className="seat-hint">
        Built-in tools (web search, page fetch, papers, Wikipedia) are available to every seat. External MCP
        tools are opt-in: a seat can only call the ones ticked here, and only if the server's own policy for
        that tool is Ask or Auto.
      </p>

      {loading ? (
        <div className="seat-muted">Loading MCP servers...</div>
      ) : servers.length === 0 ? (
        <div className="seat-empty">
          <span>No MCP servers configured yet.</span>
          <button type="button" className="seat-link-btn" onClick={onOpenMcpTab}>
            Open MCP Servers
          </button>
        </div>
      ) : (
        servers.map((server) => {
          const usable = (server.tools || []).filter((t) => t.policy === 'ask' || t.policy === 'auto');
          const names = usable.map((t) => t.exposed_name);
          const allOn = names.length > 0 && names.every((n) => selected.includes(n));
          return (
            <div key={server.id} className={`seat-tool-group ${server.enabled ? '' : 'is-off'}`}>
              <div className="seat-tool-group-head">
                <span className="seat-tool-server">{server.name}</span>
                {!server.enabled && <span className="seat-tag muted">disabled</span>}
                {names.length > 0 && (
                  <button type="button" className="seat-link-btn" onClick={() => setMany(names, !allOn)}>
                    {allOn ? 'Clear server' : 'Select all'}
                  </button>
                )}
              </div>
              {(server.tools || []).length === 0 ? (
                <div className="seat-muted">No tools discovered. Refresh this server in MCP Servers.</div>
              ) : (
                <ul className="seat-tool-list">
                  {server.tools.map((tool) => {
                    const blocked = tool.policy === 'deny' || !server.enabled;
                    const checked = selected.includes(tool.exposed_name);
                    return (
                      <li key={tool.exposed_name} className={`seat-tool ${blocked ? 'is-blocked' : ''}`}>
                        <label>
                          <input
                            type="checkbox"
                            checked={checked}
                            disabled={blocked && !checked}
                            onChange={() => toggle(tool.exposed_name)}
                          />
                          <span className="seat-tool-name">{tool.name}</span>
                        </label>
                        <span className={`seat-tag ${tool.policy}`}>
                          {tool.policy === 'deny' ? 'denied on server' : tool.policy}
                        </span>
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>
          );
        })
      )}
    </div>
  );
}

export function SeatEditor({
  model,
  isLead,
  canRemove,
  skills,
  modelOptions,
  prompt,
  mcpSelected,
  mcpServers,
  mcpLoading,
  onModelChange,
  onSkillChange,
  onInspectSkill,
  onMakeLead,
  onRemove,
  onPromptChange,
  onMcpChange,
  onOpenPersona,
  onOpenMcpTab,
}) {
  const [section, setSection] = useState('model');
  const [baseModel, skillId = ''] = model.split('@');
  const hasPrompt = Boolean(prompt?.trim());
  const toolCount = mcpSelected.length;

  return (
    <div className="seat-drawer">
      <div className="seat-sections" role="tablist">
        {SECTIONS.map((s) => (
          <button
            key={s.id}
            type="button"
            role="tab"
            aria-selected={section === s.id}
            className={`seat-section-btn ${section === s.id ? 'active' : ''}`}
            onClick={() => setSection(s.id)}
          >
            {s.label}
            {s.id === 'tools' && toolCount > 0 && <span className="seat-section-count">{toolCount}</span>}
          </button>
        ))}
      </div>

      {section === 'model' && (
        <div className="seat-fields">
          <div className="seat-field">
            <label>Model</label>
            <select value={baseModel} onChange={(e) => onModelChange(e.target.value)}>
              {modelOptions}
            </select>
          </div>
          <div className="seat-field">
            <label>Domain skill</label>
            <div className="seat-skill-row">
              <select value={skillId} onChange={(e) => onSkillChange(e.target.value)}>
                <option value="">None (general chat)</option>
                {skills.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.badge ? `[${s.badge}] ` : ''}{s.title}
                  </option>
                ))}
              </select>
              {skillId && (
                <button type="button" className="seat-link-btn" onClick={() => onInspectSkill(skillId)}>
                  Inspect skill
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      {section === 'role' && (
        <div className="seat-fields">
          <div className="seat-field">
            <label>Role prompt for {nameOf(baseModel)}</label>
            <textarea
              rows={5}
              value={prompt || ''}
              placeholder={'Instructions for this seat only, e.g. "Review for correctness, cite RFCs, and do not agree without evidence."'}
              onChange={(e) => onPromptChange(e.target.value)}
            />
            {hasPrompt && (
              <button type="button" className="seat-link-btn" onClick={() => onPromptChange('')}>
                Clear role prompt
              </button>
            )}
          </div>
        </div>
      )}

      {section === 'tools' && (
        <ToolsSection
          servers={mcpServers}
          loading={mcpLoading}
          selected={mcpSelected}
          onChange={onMcpChange}
          onOpenMcpTab={onOpenMcpTab}
        />
      )}

      <div className="seat-drawer-foot">
        <button type="button" className="seat-btn" onClick={onOpenPersona}>
          Avatar and name
        </button>
        {!isLead && (
          <button type="button" className="seat-btn" onClick={onMakeLead}>
            Make lead
          </button>
        )}
        <button type="button" className="seat-btn danger" disabled={!canRemove} onClick={onRemove}>
          Remove from table
        </button>
      </div>
    </div>
  );
}
