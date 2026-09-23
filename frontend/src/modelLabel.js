/**
 * Seat identifiers look like `local/claude-code@github-deep-review`: a provider
 * id, optionally decorated with a skill. The chat header shows the model name,
 * the provider's own label when one is configured (which is where a variant like
 * "Sonnet 4.5 - high effort" lives, since nothing else knows it), and the skill.
 */
export function formatSeatLabel(modelId, providerLabels = {}) {
  if (!modelId) return { name: '', label: '', skill: '', full: '' };

  const [baseModel, skill = ''] = modelId.split('@');
  const name = (baseModel.split('/')[1] || baseModel).replace(':free', '');

  return {
    name,
    label: (providerLabels && providerLabels[baseModel]) || '',
    skill,
    full: modelId,
  };
}
