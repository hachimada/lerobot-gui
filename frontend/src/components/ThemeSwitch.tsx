import { useEffect, useState } from 'react';
import { applyTheme, followSystem, saveTheme, storedTheme, THEMES, type ThemeChoice } from '../lib/theme';
import { Icon } from './Icon';

const LABELS: Record<ThemeChoice, string> = { auto: 'Auto (system)', light: 'Light', dark: 'Dark' };
const ICONS: Record<ThemeChoice, string> = { auto: 'auto', light: 'sun', dark: 'moon' };

/** Light, dark, or the system's; kept in this browser. */
export function ThemeSwitch() {
  const [choice, setChoice] = useState<ThemeChoice>(storedTheme);
  useEffect(() => {
    applyTheme(choice);
    return choice === 'auto' ? followSystem(() => applyTheme('auto')) : undefined;
  }, [choice]);
  return (
    <div className="seg theme-switch" role="group" aria-label="Theme">
      {THEMES.map((t) => (
        <button
          key={t}
          type="button"
          className={t === choice ? 'active' : ''}
          aria-pressed={t === choice}
          aria-label={`Theme: ${LABELS[t]}`}
          title={LABELS[t]}
          onClick={() => {
            saveTheme(t);
            setChoice(t);
          }}
        >
          <Icon name={ICONS[t]} />
        </button>
      ))}
    </div>
  );
}
