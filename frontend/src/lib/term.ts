/**
 * A small terminal emulator for command output: enough of the ANSI cursor codes for lerobot's
 * redrawn tables (`\x1b[nA` up, `\x1b[K` clear line, `\r`), colors and the rest ignored.
 */
export const MAX_LINES = 6000;

export class Term {
  lines: string[] = [''];
  row = 0;
  col = 0;
  private pending = '';
  private listeners = new Set<() => void>();
  version = 0;

  reset(): void {
    this.lines = [''];
    this.row = 0;
    this.col = 0;
    this.pending = '';
    this.changed();
  }

  get text(): string {
    return this.lines.join('\n');
  }

  subscribe(listener: () => void): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  private changed(): void {
    this.version++;
    this.listeners.forEach((l) => l());
  }

  private newline(): void {
    this.row++;
    this.col = 0;
    while (this.lines.length <= this.row) this.lines.push('');
  }

  private put(t: string): void {
    let line = this.lines[this.row] ?? '';
    if (line.length < this.col) line = line.padEnd(this.col);
    this.lines[this.row] = line.slice(0, this.col) + t + line.slice(this.col + t.length);
    this.col += t.length;
  }

  private csi(p: string, c: string): void {
    const n = Math.max(1, parseInt(p.replace(/^\?/, ''), 10) || 1);
    const m = parseInt(p, 10) || 0;
    const line = this.lines[this.row] ?? '';
    if (c === 'A') this.row = Math.max(0, this.row - n);
    else if (c === 'B') {
      this.row += n;
      while (this.lines.length <= this.row) this.lines.push('');
    } else if (c === 'C') this.col += n;
    else if (c === 'D') this.col = Math.max(0, this.col - n);
    else if (c === 'G') this.col = n - 1;
    else if (c === 'K') {
      this.lines[this.row] =
        m === 0 ? line.slice(0, this.col) : m === 1 ? ' '.repeat(this.col) + line.slice(this.col) : '';
    } else if (c === 'J') {
      if (m === 0) {
        this.lines[this.row] = line.slice(0, this.col);
        this.lines.length = this.row + 1;
      } else if (m >= 2) {
        this.lines = [''];
        this.row = 0;
        this.col = 0;
      }
    }
  }

  write(input: string): void {
    if (!input) return;
    const s = this.pending + input;
    this.pending = '';
    const n = s.length;
    let i = 0;
    while (i < n) {
      const ch = s.charCodeAt(i);
      if (ch === 27) {
        if (i + 1 >= n) {
          this.pending = s.slice(i);
          break;
        }
        const next = s[i + 1];
        if (next === '[') {
          let j = i + 2;
          while (j < n && !(s.charCodeAt(j) >= 0x40 && s.charCodeAt(j) <= 0x7e)) j++;
          if (j >= n) {
            this.pending = s.slice(i);
            break;
          }
          this.csi(s.slice(i + 2, j), s[j] ?? '');
          i = j + 1;
        } else if (next === ']') {
          const bel = s.indexOf('\x07', i);
          if (bel < 0) {
            this.pending = s.slice(i);
            break;
          }
          i = bel + 1;
        } else i += 2;
        continue;
      }
      if (ch === 10) {
        this.newline();
        i++;
      } else if (ch === 13) {
        this.col = 0;
        i++;
      } else if (ch === 8) {
        this.col = Math.max(0, this.col - 1);
        i++;
      } else if (ch === 9) {
        this.put(' '.repeat(8 - (this.col % 8)));
        i++;
      } else if (ch < 32) {
        i++;
      } else {
        let j = i + 1;
        while (j < n && s.charCodeAt(j) >= 32) j++;
        this.put(s.slice(i, j));
        i = j;
      }
    }
    if (this.lines.length > MAX_LINES) {
      const drop = this.lines.length - MAX_LINES;
      this.lines.splice(0, drop);
      this.row = Math.max(0, this.row - drop);
    }
    this.changed();
  }
}
