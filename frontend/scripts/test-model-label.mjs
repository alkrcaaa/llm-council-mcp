/** Tests for the seat label helper. Run: node frontend/scripts/test-model-label.mjs */
import assert from 'node:assert/strict';
import { formatSeatLabel } from '../src/modelLabel.js';

const labels = {
  'local/claude-code': 'Sonnet 4.5 · high effort',
  'custom/groq': 'Llama 3.3 70B',
};

// plain model, no label configured
assert.deepEqual(formatSeatLabel('local/qwen3.6-27b', labels), {
  name: 'qwen3.6-27b',
  label: '',
  skill: '',
  full: 'local/qwen3.6-27b',
});

// provider label is surfaced
assert.deepEqual(formatSeatLabel('local/claude-code', labels), {
  name: 'claude-code',
  label: 'Sonnet 4.5 · high effort',
  skill: '',
  full: 'local/claude-code',
});

// the @skill suffix is split off and never sent to the label lookup
assert.deepEqual(formatSeatLabel('local/claude-code@github-deep-review', labels), {
  name: 'claude-code',
  label: 'Sonnet 4.5 · high effort',
  skill: 'github-deep-review',
  full: 'local/claude-code@github-deep-review',
});

// missing input degrades instead of throwing
assert.deepEqual(formatSeatLabel('', labels), { name: '', label: '', skill: '', full: '' });
assert.equal(formatSeatLabel('custom/groq').label, '');

console.log('ok: formatSeatLabel');
