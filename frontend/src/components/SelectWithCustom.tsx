import { useState } from 'react';
import type { Option, OptionGroup } from '../api/types';

const CUSTOM = '__custom__';

export const isGroup = (o: Option | OptionGroup): o is OptionGroup => 'group' in o;

interface Props {
  /** '' for none */
  value: string;
  options: (Option | OptionGroup)[];
  /** the empty choice's text; null: none offered */
  empty: string | null;
  /** null: the empty choice */
  onChange: (value: string | null) => void;
  /** the select's accessible name, and the text input's */
  label: string;
  customLabel: string;
  /** "Custom…" offered (a value not in the list can be typed) */
  allowCustom?: boolean;
  /** typed only: there is nothing to choose from */
  typedOnly?: boolean;
  mono?: boolean;
  /** shown as not set yet */
  unset?: boolean;
  placeholder?: string;
}

/**
 * A select whose last choice, "Custom…", adds a text input for a value the list doesn't have. A value not in the
 * list shows in that input; choosing "Custom…" clears a value chosen from the list.
 */
export function SelectWithCustom({
  value,
  options,
  empty,
  onChange,
  label,
  customLabel,
  allowCustom = true,
  typedOnly = false,
  mono = false,
  unset = false,
  placeholder,
}: Props) {
  const known = options.some((o) => (isGroup(o) ? o.items.some((i) => i.value === value) : o.value === value));
  const [customMode, setCustomMode] = useState(false);
  const custom = allowCustom && (customMode || typedOnly || (!known && value !== ''));
  const option = (o: Option) => (
    <option key={o.value} value={o.value} disabled={o.disabled}>
      {o.label}
    </option>
  );
  return (
    <div className={custom ? 'stack' : undefined}>
      <select
        className={`input${mono ? ' mono' : ''}${unset ? ' unset' : ''}`}
        aria-label={label}
        value={custom ? CUSTOM : known ? value : ''}
        onChange={(e) => {
          if (e.target.value === CUSTOM) {
            setCustomMode(true);
            if (known) onChange(null);
          } else {
            setCustomMode(false);
            onChange(e.target.value === '' ? null : e.target.value);
          }
        }}
      >
        {empty !== null && <option value="">{empty}</option>}
        {options.map((o) =>
          isGroup(o) ? (
            <optgroup key={o.group} label={o.group}>
              {o.items.map(option)}
            </optgroup>
          ) : (
            option(o)
          ),
        )}
        {allowCustom && <option value={CUSTOM}>Custom…</option>}
      </select>
      {custom && (
        <input
          className={`input${mono ? ' mono' : ''}`}
          aria-label={customLabel}
          value={value}
          spellCheck={false}
          placeholder={placeholder}
          onChange={(e) => onChange(e.target.value)}
        />
      )}
    </div>
  );
}
