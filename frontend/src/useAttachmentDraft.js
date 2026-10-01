import { useCallback, useEffect, useRef, useState } from 'react';
import { MAX_FILES, classify, validateFile } from './attachments';

// Files picked for the next message. They are uploaded at send time (the conversation may not
// exist yet on the landing screen), so a draft holds File objects and local preview URLs only.
export default function useAttachmentDraft() {
  const [items, setItems] = useState([]);
  const [error, setError] = useState(null);
  // The ref is the source of truth so paste/drop bursts see each other's files immediately.
  const itemsRef = useRef([]);

  const commit = useCallback((next) => {
    itemsRef.current = next;
    setItems(next);
  }, []);

  const add = useCallback((fileList) => {
    const incoming = Array.from(fileList || []);
    if (incoming.length === 0) return;
    const problems = [];
    const next = [...itemsRef.current];
    for (const file of incoming) {
      const problem = validateFile(file);
      if (problem) {
        problems.push(problem);
      } else if (next.length >= MAX_FILES) {
        problems.push(`At most ${MAX_FILES} files per message`);
        break;
      } else {
        const previewUrl = classify(file) === 'image' ? URL.createObjectURL(file) : null;
        next.push({ key: `${file.name}-${file.size}-${Math.random().toString(36).slice(2, 8)}`, file, previewUrl });
      }
    }
    if (next.length !== itemsRef.current.length) commit(next);
    setError(problems.length ? [...new Set(problems)].join(' · ') : null);
  }, [commit]);

  const remove = useCallback((key) => {
    const gone = itemsRef.current.find((i) => i.key === key);
    if (gone?.previewUrl) URL.revokeObjectURL(gone.previewUrl);
    commit(itemsRef.current.filter((i) => i.key !== key));
  }, [commit]);

  // Hands the files to the caller and forgets them. Preview URLs stay valid for the message
  // bubble that is about to show them, so they are not revoked here.
  const take = useCallback(() => {
    const taken = itemsRef.current;
    commit([]);
    setError(null);
    return taken;
  }, [commit]);

  useEffect(
    () => () => {
      itemsRef.current.forEach((i) => i.previewUrl && URL.revokeObjectURL(i.previewUrl));
    },
    []
  );

  return { items, error, add, remove, take };
}
