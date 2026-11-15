import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it } from 'vitest';
import { THEME_KEY } from '../lib/theme';
import { ThemeSwitch } from './ThemeSwitch';

afterEach(() => {
  localStorage.clear();
  delete document.documentElement.dataset.theme;
});

describe('ThemeSwitch', () => {
  it('switches the page between light and dark, and back to the system’s', async () => {
    render(<ThemeSwitch />);
    expect(screen.getByRole('button', { name: 'Theme: Auto (system)' })).toHaveAttribute('aria-pressed', 'true');
    expect(document.documentElement.dataset.theme).toBe('light'); // the test browser's system is light
    await userEvent.click(screen.getByRole('button', { name: 'Theme: Dark' }));
    expect(document.documentElement.dataset.theme).toBe('dark');
    expect(localStorage.getItem(THEME_KEY)).toBe('dark');
    await userEvent.click(screen.getByRole('button', { name: 'Theme: Light' }));
    expect(document.documentElement.dataset.theme).toBe('light');
    await userEvent.click(screen.getByRole('button', { name: 'Theme: Auto (system)' }));
    expect(localStorage.getItem(THEME_KEY)).toBeNull();
  });

  it('starts from the choice kept in this browser', () => {
    localStorage.setItem(THEME_KEY, 'dark');
    render(<ThemeSwitch />);
    expect(screen.getByRole('button', { name: 'Theme: Dark' })).toHaveAttribute('aria-pressed', 'true');
    expect(document.documentElement.dataset.theme).toBe('dark');
  });
});
