// Client-side attachment helpers. The backend is the authority (it checks content, not names);
// these checks only save a round trip and keep the picker honest.

export const MAX_BYTES = { image: 10_000_000, pdf: 20_000_000, text: 1_000_000 };
export const MAX_FILES = 8;
export const ACCEPT = 'image/png,image/jpeg,image/gif,image/webp,application/pdf,text/*,.md,.txt,.csv,.json,.log,.py,.js,.ts,.yaml,.yml';

const TEXT_EXT = /\.(txt|md|csv|json|log|py|js|jsx|ts|tsx|yaml|yml|toml|ini|sh|html|css|xml)$/i;

export function classify(file) {
  if (/^image\/(png|jpeg|gif|webp)$/.test(file.type)) return 'image';
  if (file.type === 'application/pdf') return 'pdf';
  if (file.type.startsWith('text/') || TEXT_EXT.test(file.name || '')) return 'text';
  return null;
}

export function formatSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1_000_000) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / 1_000_000).toFixed(1)} MB`;
}

// Returns an error string, or null when the file may be attached.
export function validateFile(file) {
  const kind = classify(file);
  if (!kind) return `${file.name || 'File'}: unsupported type (images, PDF or text only)`;
  if (file.size === 0) return `${file.name || 'File'}: empty file`;
  if (file.size > MAX_BYTES[kind]) {
    return `${file.name || 'File'}: too large for ${kind} (limit ${formatSize(MAX_BYTES[kind])})`;
  }
  return null;
}

// Local description of a file that is about to be uploaded, shaped like the server's metadata.
export function describeLocal(file, previewUrl) {
  return { name: file.name || 'pasted', kind: classify(file), size: file.size, previewUrl };
}
