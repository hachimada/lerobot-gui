import { afterEach, describe, expect, it, vi } from 'vitest';
import { resolveTheme, saveTheme, storedTheme, THEME_KEY } from './theme';

afterEach(() => localStorage.clear());

describe('theme', () => {
  it('is kept in this browser; auto is not stored', () => {
    expect(storedTheme()).toBe('auto');
    saveTheme('dark');
    expect(localStorage.getItem(THEME_KEY)).toBe('dark');
    expect(storedTheme()).toBe('dark');
    saveTheme('auto');
    expect(localStorage.getItem(THEME_KEY)).toBeNull();
    localStorage.setItem(THEME_KEY, 'purple');
    expect(storedTheme()).toBe('auto');
  });

  it('auto follows the system', () => {
    expect(resolveTheme('auto', true)).toBe('dark');
    expect(resolveTheme('auto', false)).toBe('light');
    expect(resolveTheme('light', true)).toBe('light');
    expect(resolveTheme('dark', false)).toBe('dark');
  });

  it('survives storage that throws', () => {
    const broken = { getItem: vi.fn(() => { throw new Error('denied'); }), setItem: vi.fn(() => { throw new Error('denied'); }) } as unknown as Storage;
    expect(storedTheme(broken)).toBe('auto');
    expect(() => saveTheme('dark', broken)).not.toThrow();
  });
});
