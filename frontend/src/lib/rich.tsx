import { Fragment, type ReactNode } from 'react';

const PAGE_LINK = /^\[([^\]]+)\]\((#[\w-]+)\)$/;

/**
 * Text with `code` spans and links to the GUI's pages (`[Trackio](#trackio)`), as the server writes
 * its messages and help texts.
 */
export function Rich({ text }: { text: string | null | undefined }): ReactNode {
  if (!text) return null;
  return text.split(/(`[^`]+`|\[[^\]]+\]\(#[\w-]+\))/g).map((part, i) => {
    if (part.length > 2 && part.startsWith('`') && part.endsWith('`')) return <code key={i}>{part.slice(1, -1)}</code>;
    const link = PAGE_LINK.exec(part);
    if (link)
      return (
        <a key={i} href={link[2]}>
          {link[1]}
        </a>
      );
    return <Fragment key={i}>{part}</Fragment>;
  });
}

const URL = /https?:\/\/[^\s"'<>`]+/g;

/** A command's output with its web addresses as links, opened in a new tab. */
export function withLinks(text: string): ReactNode[] {
  const out: ReactNode[] = [];
  let at = 0;
  for (const m of text.matchAll(URL)) {
    // punctuation that ends a sentence isn't part of the address
    const url = m[0].replace(/[.,;:!?)\]}'"]+$/, '');
    const start = m.index ?? 0;
    out.push(text.slice(at, start));
    out.push(
      <a key={start} href={url} target="_blank" rel="noopener noreferrer">
        {url}
      </a>,
    );
    at = start + url.length;
  }
  out.push(text.slice(at));
  return out;
}
