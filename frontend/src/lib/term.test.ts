import { describe, expect, it } from 'vitest';
import { MAX_LINES, Term } from './term';

describe('Term', () => {
  it('writes lines and handles carriage return', () => {
    const t = new Term();
    t.write('hello\nworld\rW');
    expect(t.text).toBe('hello\nWorld');
  });

  it('redraws a table in place with cursor-up and clear-line', () => {
    const t = new Term();
    t.write('NAME | NORM\nshoulder | 1.0\n');
    t.write('\x1b[2A\x1b[KNAME | NORM\n\x1b[Kshoulder | 2.0\n');
    expect(t.text).toBe('NAME | NORM\nshoulder | 2.0\n');
  });

  it('keeps an escape sequence split across writes', () => {
    const t = new Term();
    t.write('abc\x1b[');
    t.write('1Dx');
    expect(t.text).toBe('abx');
  });

  it('ignores colors and OSC titles', () => {
    const t = new Term();
    t.write('\x1b[31mred\x1b[0m \x1b]0;title\x07ok');
    expect(t.text).toBe('red ok');
  });

  it('expands tabs, clears the screen and resets', () => {
    const t = new Term();
    t.write('a\tb');
    expect(t.text).toBe('a       b');
    t.write('\x1b[2Jfresh');
    expect(t.text).toBe('fresh');
    t.reset();
    expect(t.text).toBe('');
  });

  it('drops the oldest lines past the limit', () => {
    const t = new Term();
    t.write(Array.from({ length: MAX_LINES + 10 }, (_, i) => `line ${i}`).join('\n'));
    expect(t.lines.length).toBe(MAX_LINES);
    expect(t.lines[0]).toBe('line 10');
  });

  it('notifies subscribers', () => {
    const t = new Term();
    let n = 0;
    const off = t.subscribe(() => n++);
    t.write('x');
    off();
    t.write('y');
    expect(n).toBe(1);
  });
});
