/**
 * Light or dark: "auto" follows the system, or the user picks one. The choice is kept in this
 * browser; the page's <html data-theme> holds the theme in use, which the styles follow.
 * index.html sets it before the first paint (the same rule as `resolveTheme`).
 */
export type ThemeChoice = 'auto' | 'light' | 'dark';
export const THEME_KEY = 'lerobot-gui:theme';
export const THEMES: ThemeChoice[] = ['auto', 'light', 'dark'];

const DARK_QUERY = '(prefers-color-scheme: dark)';

export function storedTheme(storage: Storage | undefined = globalThis.localStorage): ThemeChoice {
  try {
    const value = storage?.getItem(THEME_KEY);
    return value === 'light' || value === 'dark' ? value : 'auto';
  } catch {
    return 'auto';
  }
}

export function systemDark(): boolean {
  return typeof window !== 'undefined' && !!window.matchMedia?.(DARK_QUERY).matches;
}

export const resolveTheme = (choice: ThemeChoice, dark = systemDark()): 'light' | 'dark' =>
  choice === 'auto' ? (dark ? 'dark' : 'light') : choice;

export function applyTheme(choice: ThemeChoice): void {
  document.documentElement.dataset.theme = resolveTheme(choice);
}

export function saveTheme(choice: ThemeChoice, storage: Storage | undefined = globalThis.localStorage): void {
  try {
    if (choice === 'auto') storage?.removeItem(THEME_KEY);
    else storage?.setItem(THEME_KEY, choice);
  } catch {
    /* not kept: it still applies to this page */
  }
}

/** While "auto": follow the system when it switches. */
export function followSystem(onChange: () => void): () => void {
  const query = typeof window !== 'undefined' ? window.matchMedia?.(DARK_QUERY) : undefined;
  if (!query) return () => {};
  query.addEventListener('change', onChange);
  return () => query.removeEventListener('change', onChange);
}
