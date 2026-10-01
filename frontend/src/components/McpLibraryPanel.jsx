import { useCallback, useEffect, useState } from 'react';
import { api } from '../api';

// Installs a catalog entry, then discovers its tools. The first run downloads the package.
function McpLibraryPanel({ onChanged, onError, onSuccess }) {
  const [library, setLibrary] = useState(null);
  const [installingId, setInstallingId] = useState(null);

  const load = useCallback(async () => {
    try {
      setLibrary(await api.getMcpLibrary());
    } catch (e) {
      onError?.(e.message);
    }
  }, [onError]);

  useEffect(() => {
    load();
  }, [load]);

  const install = async (entry) => {
    setInstallingId(entry.id);
    try {
      await api.installMcpLibraryEntry(entry.id);
      onSuccess?.(`Installed ${entry.name}. Discovering its tools; the first run downloads the package.`);
      await api.refreshMcpServer(entry.id);
      onSuccess?.(`${entry.name} is ready. Its tools start as Deny: choose which ones to allow below.`);
    } catch (e) {
      onError?.(e.message);
    } finally {
      setInstallingId(null);
      await load();
      onChanged?.();
    }
  };

  if (!library) return <div className="config-loading">Loading library...</div>;

  return (
    <div className="mcp-library">
      <p className="mcp-subtitle">
        Curated servers pinned to an exact version. Each entry runs a fixed command inside the backend
        container, so nothing here lets you run an arbitrary command.
      </p>
      {!library.runner_available && (
        <div className="mcp-error">The backend has no uvx, so library servers cannot be installed.</div>
      )}
      <div className="mcp-library-grid">
        {library.entries.map((entry) => (
          <section key={entry.id} className="mcp-library-card">
            <header className="mcp-library-head">
              <span className="mcp-server-name">{entry.name}</span>
              <span className="mcp-badge">{entry.category}</span>
            </header>
            <p className="mcp-library-summary">{entry.summary}</p>
            <dl className="mcp-library-meta">
              <div><dt>Package</dt><dd>{entry.pinned}</dd></div>
              <div><dt>Maintainer</dt><dd>{entry.maintainer}</dd></div>
              <div><dt>License</dt><dd>{entry.license}</dd></div>
              <div><dt>Checked</dt><dd>{entry.verified}</dd></div>
            </dl>
            {entry.warnings?.map((w) => (
              <p key={w} className="mcp-library-warning">{w}</p>
            ))}
            <footer className="mcp-library-foot">
              <a href={entry.source} target="_blank" rel="noopener noreferrer" className="mcp-link">
                Source
              </a>
              {entry.installed ? (
                <span className="mcp-badge">Installed</span>
              ) : (
                <button
                  type="button"
                  className="mcp-btn primary"
                  disabled={installingId !== null || !library.runner_available}
                  onClick={() => install(entry)}
                >
                  {installingId === entry.id ? 'Installing...' : 'Install'}
                </button>
              )}
            </footer>
          </section>
        ))}
      </div>
    </div>
  );
}

export default McpLibraryPanel;
