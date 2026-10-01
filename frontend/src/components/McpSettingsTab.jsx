import { useCallback, useEffect, useState } from 'react';
import { api } from '../api';
import McpLibraryPanel from './McpLibraryPanel.jsx';
import './McpSettingsTab.css';

const POLICIES = [
  { id: 'deny', label: 'Deny', hint: 'Never exposed to models' },
  { id: 'ask', label: 'Ask', hint: 'Each call needs your approval' },
  { id: 'auto', label: 'Auto', hint: 'Runs without asking' },
];

const EMPTY_FORM = { name: '', transport: 'http', url: '', command: '', args: '', headers: '', env: '' };

// "KEY=value" per line -> { KEY: 'value' }
function parsePairs(text) {
  const out = {};
  for (const line of text.split('\n')) {
    const idx = line.indexOf('=');
    if (idx > 0) out[line.slice(0, idx).trim()] = line.slice(idx + 1).trim();
  }
  return out;
}

function McpSettingsTab({ onError, onSuccess }) {
  const [servers, setServers] = useState([]);
  const [stdioAllowed, setStdioAllowed] = useState(false);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState(null);
  const [confirmDeleteId, setConfirmDeleteId] = useState(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [adding, setAdding] = useState(false);
  const [view, setView] = useState('servers'); // servers | library

  const load = useCallback(async () => {
    try {
      const data = await api.getMcpServers();
      setServers(data.servers || []);
      setStdioAllowed(Boolean(data.stdio_allowed));
    } catch (e) {
      onError?.(e.message);
    } finally {
      setLoading(false);
    }
  }, [onError]);

  useEffect(() => {
    load();
  }, [load]);

  const replaceServer = (updated) =>
    setServers((prev) => prev.map((s) => (s.id === updated.id ? updated : s)));

  const run = async (serverId, action, okMessage) => {
    setBusyId(serverId);
    try {
      const result = await action();
      if (result?.server) replaceServer(result.server);
      if (okMessage) onSuccess?.(okMessage);
    } catch (e) {
      onError?.(e.message);
      await load(); // a failed refresh still records last_error server-side
    } finally {
      setBusyId(null);
    }
  };

  const handleAdd = async (e) => {
    e.preventDefault();
    setAdding(true);
    try {
      const payload = { name: form.name.trim(), transport: form.transport };
      if (form.transport === 'http') {
        payload.url = form.url.trim();
        const headers = parsePairs(form.headers);
        if (Object.keys(headers).length) payload.headers = headers;
      } else {
        payload.command = form.command.trim();
        payload.args = form.args.split('\n').map((a) => a.trim()).filter(Boolean);
        const env = parsePairs(form.env);
        if (Object.keys(env).length) payload.env = env;
      }
      const { server } = await api.createMcpServer(payload);
      setServers((prev) => [...prev, server]);
      setForm(EMPTY_FORM);
      onSuccess?.(`Added ${server.name}. Refresh it to discover tools; new tools start as Deny.`);
    } catch (err) {
      onError?.(err.message);
    } finally {
      setAdding(false);
    }
  };

  const setPolicy = (server, tool, policy) =>
    run(server.id, () => api.updateMcpServer(server.id, { tool_policies: { [tool]: policy } }));

  const toggleEnabled = (server) =>
    run(server.id, () => api.updateMcpServer(server.id, { enabled: !server.enabled }));

  const handleDelete = async (serverId) => {
    setBusyId(serverId);
    try {
      await api.deleteMcpServer(serverId);
      setServers((prev) => prev.filter((s) => s.id !== serverId));
      setConfirmDeleteId(null);
      onSuccess?.('MCP server removed.');
    } catch (e) {
      onError?.(e.message);
    } finally {
      setBusyId(null);
    }
  };

  const canSubmit =
    form.name.trim() && (form.transport === 'http' ? form.url.trim() : form.command.trim());

  return (
    <div className="tab-pane-mcp">
      <div className="mcp-intro">
        <h3 className="mcp-title">MCP Servers</h3>
        <p className="mcp-subtitle">
          Every discovered tool starts as Deny. Set a tool to Ask to approve each call, or Auto to
          let models call it freely. Header and environment values are write-only.
        </p>
      </div>

      <div className="mcp-views" role="tablist">
        {[['servers', `Installed (${servers.length})`], ['library', 'Library']].map(([id, label]) => (
          <button
            key={id}
            type="button"
            role="tab"
            aria-selected={view === id}
            className={`mcp-view-btn ${view === id ? 'active' : ''}`}
            onClick={() => setView(id)}
          >
            {label}
          </button>
        ))}
      </div>

      {view === 'library' ? (
        <McpLibraryPanel
          onChanged={load}
          onError={onError}
          onSuccess={(msg) => {
            onSuccess?.(msg);
            setView('servers');
          }}
        />
      ) : loading ? (
        <div className="config-loading">Loading MCP servers...</div>
      ) : servers.length === 0 ? (
        <div className="mcp-empty">
          No MCP servers configured. Pick one from the Library or add your own below.
        </div>
      ) : (
        <div className="mcp-server-list">
          {servers.map((server) => {
            const busy = busyId === server.id;
            const target = server.transport === 'http' ? server.url : server.command;
            return (
              <section key={server.id} className={`mcp-server ${server.enabled ? '' : 'is-disabled'}`}>
                <header className="mcp-server-head">
                  <div className="mcp-server-id">
                    <span className="mcp-server-name">{server.name}</span>
                    <span className="mcp-badge">{server.transport}</span>
                    {!server.enabled && <span className="mcp-badge muted">disabled</span>}
                  </div>
                  <div className="mcp-server-actions">
                    <button type="button" className="mcp-btn" disabled={busy} onClick={() => toggleEnabled(server)}>
                      {server.enabled ? 'Disable' : 'Enable'}
                    </button>
                    <button
                      type="button"
                      className="mcp-btn primary"
                      disabled={busy || !server.enabled}
                      onClick={() => run(server.id, () => api.refreshMcpServer(server.id), `Refreshed ${server.name}.`)}
                    >
                      {busy ? 'Working...' : 'Refresh tools'}
                    </button>
                    {confirmDeleteId === server.id ? (
                      <>
                        <button type="button" className="mcp-btn danger" disabled={busy} onClick={() => handleDelete(server.id)}>
                          Confirm remove
                        </button>
                        <button type="button" className="mcp-btn" onClick={() => setConfirmDeleteId(null)}>
                          Cancel
                        </button>
                      </>
                    ) : (
                      <button type="button" className="mcp-btn" disabled={busy} onClick={() => setConfirmDeleteId(server.id)}>
                        Remove
                      </button>
                    )}
                  </div>
                </header>

                <div className="mcp-server-meta">
                  <code className="mcp-target">{target}</code>
                  {(server.headers_set?.length > 0 || server.env_set?.length > 0) && (
                    <span className="mcp-secrets">
                      Secrets set: {[...(server.headers_set || []), ...(server.env_set || [])].join(', ')}
                    </span>
                  )}
                </div>

                {server.last_error && <div className="mcp-error">{server.last_error}</div>}

                {server.tools?.length > 0 ? (
                  <ul className="mcp-tools">
                    {server.tools.map((tool) => (
                      <li key={tool.name} className="mcp-tool">
                        <div className="mcp-tool-info">
                          <span className="mcp-tool-name">{tool.name}</span>
                          {tool.definition_changed && (
                            <span className="mcp-badge warn" title="The server changed this tool's definition; it was reset to Deny. Review it before enabling.">
                              definition changed
                            </span>
                          )}
                          {tool.description && <span className="mcp-tool-desc">{tool.description}</span>}
                        </div>
                        <div className="mcp-policy" role="radiogroup" aria-label={`Policy for ${tool.name}`}>
                          {POLICIES.map((p) => (
                            <button
                              key={p.id}
                              type="button"
                              role="radio"
                              aria-checked={tool.policy === p.id}
                              title={p.hint}
                              disabled={busy}
                              className={`mcp-policy-btn ${p.id} ${tool.policy === p.id ? 'active' : ''}`}
                              onClick={() => tool.policy !== p.id && setPolicy(server, tool.name, p.id)}
                            >
                              {p.label}
                            </button>
                          ))}
                        </div>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <div className="mcp-empty small">No tools discovered yet.</div>
                )}
              </section>
            );
          })}
        </div>
      )}

      {view === 'servers' && (
      <form className="mcp-add" onSubmit={handleAdd}>
        <h4 className="mcp-add-title">Add server</h4>
        <div className="form-row-2col">
          <div className="form-group">
            <label htmlFor="mcp-name">Name *</label>
            <input id="mcp-name" type="text" value={form.name} placeholder="e.g. arXiv"
              onChange={(e) => setForm({ ...form, name: e.target.value })} required />
          </div>
          <div className="form-group">
            <label htmlFor="mcp-transport">Transport</label>
            <select id="mcp-transport" value={form.transport}
              onChange={(e) => setForm({ ...form, transport: e.target.value })}>
              <option value="http">HTTP (streamable)</option>
              <option value="stdio" disabled={!stdioAllowed}>
                {stdioAllowed ? 'stdio (local process)' : 'stdio (disabled on this server)'}
              </option>
            </select>
          </div>
        </div>

        {form.transport === 'http' ? (
          <>
            <div className="form-group">
              <label htmlFor="mcp-url">URL *</label>
              <input id="mcp-url" type="text" value={form.url} placeholder="https://host/mcp"
                onChange={(e) => setForm({ ...form, url: e.target.value })} required />
            </div>
            <div className="form-group">
              <label htmlFor="mcp-headers">Headers (one KEY=value per line)</label>
              <textarea id="mcp-headers" rows={2} value={form.headers} placeholder="Authorization=Bearer ..."
                onChange={(e) => setForm({ ...form, headers: e.target.value })} />
            </div>
          </>
        ) : (
          <>
            <div className="form-group">
              <label htmlFor="mcp-command">Command *</label>
              <input id="mcp-command" type="text" value={form.command} placeholder="npx"
                onChange={(e) => setForm({ ...form, command: e.target.value })} required />
            </div>
            <div className="form-group">
              <label htmlFor="mcp-args">Arguments (one per line)</label>
              <textarea id="mcp-args" rows={2} value={form.args}
                onChange={(e) => setForm({ ...form, args: e.target.value })} />
            </div>
            <div className="form-group">
              <label htmlFor="mcp-env">Environment (one KEY=value per line)</label>
              <textarea id="mcp-env" rows={2} value={form.env}
                onChange={(e) => setForm({ ...form, env: e.target.value })} />
            </div>
          </>
        )}

        <button type="submit" className="mcp-btn primary" disabled={adding || !canSubmit}>
          {adding ? 'Adding...' : 'Add server'}
        </button>
      </form>
      )}
    </div>
  );
}

export default McpSettingsTab;
