import { useState, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import { api } from '../api';
import './SkillViewerModal.css';

export default function SkillViewerModal({ initialSkillId = null, onClose }) {
  const [skills, setSkills] = useState([]);
  const [selectedSkillId, setSelectedSkillId] = useState(initialSkillId);
  const [skillDetails, setSkillDetails] = useState(null);
  const [isLoadingList, setIsLoadingList] = useState(true);
  const [isLoadingDetails, setIsLoadingDetails] = useState(false);
  const [error, setError] = useState(null);

  // Load list of available skills
  useEffect(() => {
    const fetchSkills = async () => {
      try {
        setIsLoadingList(true);
        const res = await api.getSkills();
        const list = res.skills || [];
        setSkills(list);
        if (!selectedSkillId && list.length > 0) {
          setSelectedSkillId(list[0].id);
        }
      } catch (err) {
        setError('Failed to load skills list');
        console.error(err);
      } finally {
        setIsLoadingList(false);
      }
    };
    fetchSkills();
  }, []);

  // Load details when selectedSkillId changes
  useEffect(() => {
    if (!selectedSkillId) return;

    const fetchDetails = async () => {
      try {
        setIsLoadingDetails(true);
        setError(null);
        const data = await api.getSkillDetails(selectedSkillId);
        setSkillDetails(data);
      } catch (err) {
        setError(`Failed to load details for "${selectedSkillId}"`);
        console.error(err);
      } finally {
        setIsLoadingDetails(false);
      }
    };
    fetchDetails();
  }, [selectedSkillId]);

  // Handle ESC key to close
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  return (
    <div className="skill-viewer-backdrop" onClick={onClose}>
      <div className="skill-viewer-modal" onClick={(e) => e.stopPropagation()}>
        {/* Modal Header */}
        <div className="skill-viewer-header">
          <div className="skill-header-title-wrap">
            <span className="skill-header-icon">📚</span>
            <h2>Domain Skills & Persona Guidelines</h2>
          </div>
          <button className="skill-close-btn" onClick={onClose} title="Close (Esc)">
            &times;
          </button>
        </div>

        <div className="skill-viewer-body">
          {/* Left Sidebar: Skill List */}
          <aside className="skill-sidebar">
            <div className="skill-sidebar-header">
              <span>AVAILABLE PERSONAS</span>
              <span className="skill-count">{skills.length}</span>
            </div>

            {isLoadingList ? (
              <div className="skill-loading-inline">Loading skills...</div>
            ) : (
              <div className="skill-list">
                {skills.map((s) => {
                  const isSelected = s.id === selectedSkillId;
                  return (
                    <button
                      key={s.id}
                      type="button"
                      className={`skill-list-item ${isSelected ? 'active' : ''}`}
                      onClick={() => setSelectedSkillId(s.id)}
                    >
                      <div className="skill-item-top">
                        <span className="skill-badge-tag">{s.badge || 'SKILL'}</span>
                        <span className="skill-item-category">{s.category || 'General'}</span>
                      </div>
                      <div className="skill-item-title">{s.title}</div>
                    </button>
                  );
                })}
              </div>
            )}
          </aside>

          {/* Right Main Panel: Details & Instructions */}
          <main className="skill-content-panel">
            {isLoadingDetails ? (
              <div className="skill-loading-panel">
                <span className="skill-spinner" />
                <p>Reading skill instructions & operative checklist...</p>
              </div>
            ) : error ? (
              <div className="skill-error-panel">{error}</div>
            ) : skillDetails ? (
              <div className="skill-details-scroll">
                {/* Meta Banner */}
                <div className="skill-meta-banner">
                  <div className="skill-badge-large">{skillDetails.badge || 'SKILL'}</div>
                  <div className="skill-meta-text">
                    <h3>{skillDetails.title}</h3>
                    <span className="skill-id-code">@{skillDetails.id}</span>
                    <p className="skill-banner-desc">{skillDetails.description}</p>
                  </div>
                </div>

                {/* Operative Gate / Guidelines Box */}
                {skillDetails.guidelines && (
                  <div className="skill-gate-box">
                    <div className="skill-gate-header">
                      <span className="gate-icon">⚖️</span>
                      <h4>Mandatory Council Gate & Operative Checklist</h4>
                    </div>
                    <p className="skill-gate-info">
                      Models assigned this skill must strictly enforce these domain rules in Stage 1 answers and Stage 2 peer scoring:
                    </p>
                    <div className="skill-gate-content markdown-content">
                      <ReactMarkdown>{skillDetails.guidelines}</ReactMarkdown>
                    </div>
                  </div>
                )}

                {/* Full Documentation */}
                <div className="skill-full-doc">
                  <div className="doc-section-header">
                    <h4>Complete Skill Documentation</h4>
                  </div>
                  <div className="skill-markdown-body markdown-content">
                    <ReactMarkdown>{skillDetails.content}</ReactMarkdown>
                  </div>
                </div>
              </div>
            ) : (
              <div className="skill-empty-panel">Select a skill to inspect its instructions</div>
            )}
          </main>
        </div>
      </div>
    </div>
  );
}
