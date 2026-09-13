// Shared @mention helpers used by LiveFeed (de-anonymized "Response A" -> model)
// and by ChatInterface (user-typed "@ModelName" -> model). Kept in one place
// so both sides render mention pills identically.

const USERNAME_PALETTE = [
  '#f27878', '#f2a65a', '#e0c341', '#8bc98a',
  '#5fc7c7', '#6fa8dc', '#a892e0', '#e08ad0',
];

function hashString(str) {
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    hash = (hash * 31 + str.charCodeAt(i)) >>> 0;
  }
  return hash;
}

export function colorForModel(modelId) {
  if (!modelId) return USERNAME_PALETTE[0];
  return USERNAME_PALETTE[hashString(modelId) % USERNAME_PALETTE.length];
}

export function shortModelName(modelId) {
  if (!modelId) return 'Unknown';
  const [baseModel] = modelId.split('@');
  return (baseModel.split('/')[1] || baseModel).replace(':free', '');
}

export function initialsFor(modelId) {
  const name = shortModelName(modelId);
  const parts = name.split(/[-_.\s]/).filter(Boolean);
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
  return name.slice(0, 2).toUpperCase();
}

// Turns anonymized "Response A" style labels into markdown mention links
// (`[@Name](mention:modelId)`) so ReactMarkdown's own parser handles the
// splitting — safer than hand-rolling regex-based text splitting.
export function toMentionMarkdown(text, labelToModel) {
  if (!labelToModel || !text) return text || '';
  let result = text;
  Object.entries(labelToModel).forEach(([label, model]) => {
    const name = shortModelName(model);
    result = result.split(label).join(`[@${name}](mention:${encodeURIComponent(model)})`);
  });
  return result;
}

const REGEX_SPECIAL = /[.*+?^${}()|[\]\\]/g;

// Turns user-typed "@ModelName" tokens (matched against the active council's
// seats) into the same markdown mention links, word-boundary safe.
export function linkifyUserMentions(text, councilModels) {
  if (!councilModels?.length || !text) return text || '';
  let result = text;
  const seats = [...councilModels].sort(
    (a, b) => shortModelName(b).length - shortModelName(a).length
  );
  seats.forEach((model) => {
    const name = shortModelName(model);
    const pattern = new RegExp(`@${name.replace(REGEX_SPECIAL, '\\$&')}\\b`, 'gi');
    result = result.replace(pattern, `[@${name}](mention:${encodeURIComponent(model)})`);
  });
  return result;
}

export const mentionMarkdownComponents = {
  a({ href, children }) {
    if (href?.startsWith('mention:')) {
      const model = decodeURIComponent(href.slice('mention:'.length));
      return (
        <span className="feed-mention" style={{ '--mention-color': colorForModel(model) }}>
          {children}
        </span>
      );
    }
    return (
      <a href={href} target="_blank" rel="noreferrer">
        {children}
      </a>
    );
  },
};
