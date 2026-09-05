/**
 * Export utilities for LLM Council conversations.
 * Supports standard multi-stage deliberation, iterative debate rounds,
 * and standardized Architecture Decision Record (ADR) exports.
 */

/**
 * Helper to extract human-readable model and skill label.
 * @param {string} modelStr - Identifier like 'local/qwen3.6-27b@red-team-reasoning'
 * @returns {string} Clean label like 'qwen3.6-27b (Red Team Reasoning)'
 */
export function formatModelLabel(modelStr) {
  if (!modelStr) return 'Unknown Specialist';
  const [baseModel, skill] = modelStr.split('@');
  const rawName = baseModel.split('/').pop() || baseModel;
  if (!skill) return rawName;

  const formattedSkill = skill
    .split('-')
    .map(w => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ');

  return `${rawName} [${formattedSkill}]`;
}

/**
 * Export conversation to Markdown format.
 * @param {Object} conversation - The conversation object
 */
export function exportToMarkdown(conversation) {
  const markdown = generateMarkdown(conversation);
  const filename = sanitizeFilename(conversation.title || 'conversation') + '.md';
  downloadFile(markdown, filename, 'text/markdown');
}

/**
 * Export conversation to JSON format.
 * @param {Object} conversation - The conversation object
 */
export function exportToJSON(conversation) {
  const json = JSON.stringify(conversation, null, 2);
  const filename = sanitizeFilename(conversation.title || 'conversation') + '.json';
  downloadFile(json, filename, 'application/json');
}

/**
 * Export conversation as a standardized Architecture Decision Record (ADR).
 * @param {Object} conversation - The conversation object
 */
export function exportToADR(conversation) {
  const adr = generateADR(conversation);
  const filename = 'ADR-' + sanitizeFilename(conversation.title || 'decision') + '.md';
  downloadFile(adr, filename, 'text/markdown');
}

/**
 * Copy ADR markdown directly to clipboard.
 * @param {Object} conversation - The conversation object
 * @returns {Promise<boolean>} True if copy succeeded
 */
export async function copyADRToClipboard(conversation) {
  try {
    const adr = generateADR(conversation);
    if (navigator.clipboard && navigator.clipboard.writeText) {
      await navigator.clipboard.writeText(adr);
      return true;
    }
    // Fallback for older environments
    const textarea = document.createElement('textarea');
    textarea.value = adr;
    textarea.style.position = 'fixed';
    textarea.style.opacity = '0';
    document.body.appendChild(textarea);
    textarea.select();
    const success = document.execCommand('copy');
    document.body.removeChild(textarea);
    return success;
  } catch (err) {
    console.error('Failed to copy ADR to clipboard:', err);
    return false;
  }
}

/**
 * Generate Markdown content from a conversation (supports both standard and debate mode).
 * @param {Object} conversation - The conversation object
 * @returns {string} Markdown content
 */
export function generateMarkdown(conversation) {
  let md = `# ${conversation.title || 'LLM Council Deliberation'}\n\n`;
  md += `*Date:* ${new Date(conversation.created_at || Date.now()).toLocaleString()}\n`;
  if (conversation.council_name) {
    md += `*Council Profile:* ${conversation.council_name}\n`;
  }
  md += `\n---\n\n`;

  for (const msg of conversation.messages || []) {
    if (msg.role === 'user') {
      md += `## 💬 User Question\n\n`;
      md += `${msg.content}\n\n`;
      md += `---\n\n`;
    } else {
      const isDebate = !!(
        msg.isDebating ||
        msg.debateRound ||
        msg.debateRebuttals?.length > 0 ||
        msg.stage3?.rebuttals?.length > 0 ||
        msg.debateCritiques?.length > 0
      );

      if (isDebate) {
        // --- DEBATE MODE EXPORT ---
        md += `## 🏛️ Council Debate Process\n\n`;

        // Round 1: Initial Positions
        const positions = msg.stage1 || [];
        if (positions.length > 0) {
          md += `### 1. Opening Positions (Round 1)\n\n`;
          for (const p of positions) {
            const label = formatModelLabel(p.model);
            md += `#### ${label}\n\n`;
            md += `${p.response || p.position || ''}\n\n`;
          }
        }

        // Round 2: Peer Critiques & Red Teaming
        const critiques = msg.debateCritiques || msg.stage2 || [];
        if (critiques.length > 0) {
          md += `### 2. Peer Critiques & Adversarial Audits (Round 2)\n\n`;
          for (const c of critiques) {
            const criticName = formatModelLabel(c.model || c.critic);
            const targetName = c.target ? ` -> ${formatModelLabel(c.target)}` : '';
            md += `#### Critic: ${criticName}${targetName}\n\n`;
            md += `${c.ranking || c.critique || ''}\n\n`;
          }
        }

        // Round 3: Rebuttals & Defenses
        const rebuttals = msg.debateRebuttals || msg.stage3?.rebuttals || [];
        if (rebuttals.length > 0) {
          md += `### 3. Rebuttals & Final Arguments (Round 3)\n\n`;
          for (const r of rebuttals) {
            const debaterName = formatModelLabel(r.model || r.debater);
            md += `#### ${debaterName}\n\n`;
            md += `${r.response || r.rebuttal || ''}\n\n`;
          }
        }

        // Final Judgment
        const judgment = msg.debateJudgment || msg.stage3?.response;
        if (judgment) {
          const chairman = formatModelLabel(msg.chairmanModel || msg.stage3?.model || 'Chairman');
          md += `### ⚖️ Final Synthesis & Verdict\n\n`;
          md += `*Synthesized by ${chairman}*\n\n`;
          md += `${judgment}\n\n`;
        }
      } else {
        // --- STANDARD COUNCIL MODE EXPORT ---
        if (msg.stage1 && msg.stage1.length > 0) {
          md += `## Stage 1: Individual Perspectives\n\n`;
          for (const resp of msg.stage1) {
            const label = formatModelLabel(resp.model);
            md += `### ${label}\n\n`;
            md += `${resp.response}\n\n`;
          }
        }

        if (msg.stage2 && msg.stage2.length > 0) {
          md += `## Stage 2: Peer Evaluations & Rankings\n\n`;
          for (const ranking of msg.stage2) {
            const label = formatModelLabel(ranking.model);
            md += `### ${label}'s Evaluation\n\n`;
            md += `${ranking.ranking}\n\n`;
            if (ranking.parsed_ranking && ranking.parsed_ranking.length > 0) {
              md += `**Ranking Order:** ${ranking.parsed_ranking.join(' > ')}\n\n`;
            }
          }
        }

        if (msg.stage3) {
          md += `## Stage 3: Chairman Synthesis\n\n`;
          const chairmanName = formatModelLabel(msg.stage3.model || 'Chairman');
          md += `*Chairman: ${chairmanName}*\n\n`;
          md += `${msg.stage3.response || ''}\n\n`;
        }
      }

      md += `---\n\n`;
    }
  }

  md += `\n*Deliberated and synthesized via LLM Council*\n`;
  return md;
}

/**
 * Generate a clean, standardized Architecture Decision Record (ADR).
 * Formatted for immediate commit into a project's `docs/adr/` or CLI prompt feeding.
 * @param {Object} conversation - The conversation object
 * @returns {string} ADR markdown
 */
export function generateADR(conversation) {
  const title = conversation.title || 'Architecture Decision';
  const dateStr = new Date(conversation.created_at || Date.now()).toISOString().split('T')[0];
  const councilName = conversation.council_name || 'LLM Council Architecture Board';

  // Find user prompt
  const userMsg = conversation.messages?.find(m => m.role === 'user');
  const assistantMsg = conversation.messages?.find(m => m.role === 'assistant' || m.stage3 || m.debateJudgment);

  let adr = `# ADR: ${title}\n\n`;
  adr += `- **Status:** Accepted / Decided\n`;
  adr += `- **Date:** ${dateStr}\n`;
  adr += `- **Council:** ${councilName}\n`;

  if (conversation.council_models && conversation.council_models.length > 0) {
    const debatersList = conversation.council_models.map(m => formatModelLabel(m)).join(', ');
    adr += `- **Council Members:** ${debatersList}\n`;
  }
  if (conversation.chairman_model) {
    adr += `- **Chairman / Judge:** ${formatModelLabel(conversation.chairman_model)}\n`;
  }

  adr += `\n---\n\n`;

  // 1. Context and Problem Statement
  adr += `## 1. Context & Problem Statement\n\n`;
  if (userMsg && userMsg.content) {
    adr += `${userMsg.content.trim()}\n\n`;
  } else {
    adr += `Evaluation of architectural direction and trade-offs for ${title}.\n\n`;
  }

  // 2. Deliberation & Perspectives
  adr += `## 2. Council Deliberation & Perspectives\n\n`;
  if (assistantMsg) {
    const positions = assistantMsg.stage1 || [];
    if (positions.length > 0) {
      adr += `### Specialist Analyses\n\n`;
      for (const p of positions) {
        const label = formatModelLabel(p.model);
        adr += `#### ${label}\n`;
        adr += `${(p.response || p.position || '').trim()}\n\n`;
      }
    }

    const critiques = assistantMsg.debateCritiques || assistantMsg.stage2 || [];
    if (critiques.length > 0) {
      adr += `### Adversarial Critiques & Failure Modes Identified\n\n`;
      for (const c of critiques) {
        const criticName = formatModelLabel(c.model || c.critic);
        adr += `- **${criticName}:** ${(c.ranking || c.critique || '').trim()}\n\n`;
      }
    }
  }

  // 3. Decision Outcome
  adr += `## 3. Decision Outcome\n\n`;
  const finalJudgment = assistantMsg?.debateJudgment || assistantMsg?.stage3?.response;
  if (finalJudgment) {
    adr += `${finalJudgment.trim()}\n\n`;
  } else {
    adr += `*Deliberation in progress or pending synthesis.*\n\n`;
  }

  // 4. Consequences & Trade-offs
  adr += `## 4. Key Consequences & Trade-offs\n\n`;
  adr += `- **Type-1 vs Type-2 Assessment:** Verified reversible vs irreversible paths based on council analysis.\n`;
  adr += `- **Actionable Directive:** Review the decision outcome above before commencing code implementation.\n\n`;

  adr += `---\n`;
  adr += `*Architecture Decision Record generated by LLM Council*\n`;

  return adr;
}

/**
 * Sanitize a string for use as a filename.
 * @param {string} name - The original name
 * @returns {string} Sanitized filename
 */
function sanitizeFilename(name) {
  return name
    .replace(/[<>:"/\\|?*]/g, '') // Remove invalid characters
    .replace(/\s+/g, '_')          // Replace spaces with underscores
    .substring(0, 50);              // Limit length
}

/**
 * Trigger a file download in the browser.
 * @param {string} content - File content
 * @param {string} filename - Name of the file
 * @param {string} mimeType - MIME type of the file
 */
function downloadFile(content, filename, mimeType) {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
