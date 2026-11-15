export const isSet = (x: unknown): boolean => x !== '' && x !== null && x !== undefined;

export const basename = (p: unknown): string =>
  String(p ?? '')
    .split('/')
    .filter(Boolean)
    .pop() ?? '';

/** `1:05` / `1:02:03` from seconds. */
export function fmtDuration(seconds: number): string {
  const s = Math.max(0, Math.floor(seconds));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const x = String(s % 60).padStart(2, '0');
  return h ? `${h}:${String(m).padStart(2, '0')}:${x}` : `${m}:${x}`;
}

export const clock = (ts: number): string =>
  new Date(ts * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });

export function ago(ts: number, now = Date.now() / 1000): string {
  const s = now - ts;
  if (s < 60) return 'just now';
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`;
  return new Date(ts * 1000).toLocaleString();
}

/** `1.2 GB` from bytes. */
export function fmtBytes(n: number | null | undefined): string {
  if (n === null || n === undefined) return '';
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  let v = n;
  let i = 0;
  while (v >= 1000 && i < units.length - 1) {
    v /= 1000;
    i += 1;
  }
  return `${i === 0 ? v : v.toFixed(v < 10 ? 1 : 0)} ${units[i]}`;
}

/** `1 file` / `3 files`. */
export const plural = (n: number, word: string): string => `${n} ${word}${n === 1 ? '' : 's'}`;

/** `2026-01-06` from an ISO time. */
export const day = (iso: string | null | undefined): string => (iso ? iso.slice(0, 10) : '');

export const cap = (t: string): string => (t ? t[0]!.toUpperCase() + t.slice(1) : t);
