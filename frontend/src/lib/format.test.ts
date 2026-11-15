import { describe, expect, it } from 'vitest';
import { ago, basename, fmtDuration, isSet } from './format';

describe('format', () => {
  it('formats durations', () => {
    expect(fmtDuration(5)).toBe('0:05');
    expect(fmtDuration(65)).toBe('1:05');
    expect(fmtDuration(3723)).toBe('1:02:03');
    expect(fmtDuration(-3)).toBe('0:00');
  });

  it('says how long ago', () => {
    expect(ago(100, 130)).toBe('just now');
    expect(ago(0, 600)).toBe('10 min ago');
    expect(ago(0, 7200)).toBe('2 h ago');
  });

  it('names devices', () => {
    expect(basename('/dev/ttyACM0')).toBe('ttyACM0');
    expect([isSet(''), isSet(null), isSet(undefined), isSet(0), isSet(false)]).toEqual([false, false, false, true, true]);
  });
});
