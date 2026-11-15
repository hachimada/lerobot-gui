import type { FieldSpec, Option } from '../api/types';
import { isSet } from '../lib/format';
import { Rich } from '../lib/rich';
import { setValues } from '../state/app';
import { PolicyPicker } from './PolicyPicker';
import { SelectWithCustom } from './SelectWithCustom';


/** What the field shows: the value typed here (stored), else the server's (none, or the GUI choice). */
export function fieldValue(f: FieldSpec, stored: Record<string, unknown> | undefined): unknown {
  return stored && f.key in stored ? stored[f.key] : f.value;
}

/** The values stored along with `v` (a Hardware port: the board on it), as the server said. */
export function alsoFor(f: FieldSpec, v: unknown): Record<string, unknown> {
  if (!f.also) return {};
  return (isSet(v) ? f.also.values[String(v)] : undefined) ?? f.also.other;
}

/** The text of an empty field: lerobot's default, else an example. */
export function emptyText(f: FieldSpec): string {
  return f.default !== null && f.default !== undefined ? `default: ${f.default}` : f.placeholder;
}

interface FieldProps {
  page: string;
  field: FieldSpec;
  stored: Record<string, unknown> | undefined;
  /** where the value (and the values stored along with it) goes, when not the page's values: the Hardware
   * values, a camera's settings */
  onSet?: (patch: Record<string, unknown>) => void;
}

export function Field({ page, field: f, stored, onSet }: FieldProps) {
  const value = fieldValue(f, stored);
  // empty clears the value: the flag leaves the command and lerobot's default applies
  const set = (v: unknown) => {
    const patch = { [f.key]: v, ...alsoFor(f, v) };
    if (onSet) onSet(patch);
    else setValues(page, patch);
  };
  const label = (
    <div className="field-label">
      <span>
        {f.label}
        {f.required && <span className="muted tiny"> · required</span>}
      </span>
      {f.flag && (
        <span className="flag" title={f.flag}>
          {f.flag}
        </span>
      )}
    </div>
  );
  const help = f.help ? (
    <div className="help">
      <Rich text={f.help} />
    </div>
  ) : null;
  const cls = `field${f.half ? ' half' : ''}`;

  if (f.kind === 'seg') {
    return (
      <div className={cls}>
        {label}
        <div className="seg" role="group" aria-label={f.label}>
          {(f.options as Option[]).map((o) => (
            <button
              key={o.value}
              type="button"
              className={o.value === value ? 'active' : ''}
              aria-pressed={o.value === value}
              disabled={o.disabled}
              title={o.title || undefined}
              onClick={() => set(o.value)}
            >
              {o.label}
            </button>
          ))}
        </div>
        {help}
      </div>
    );
  }
  if (f.kind === 'toggle') {
    // on writes the flag as true; off leaves it out (lerobot's default)
    const on = value === true || value === 'true';
    return (
      <div className={cls}>
        <label className="toggle">
          <button
            type="button"
            role="switch"
            className="switch"
            aria-checked={on}
            aria-label={f.label}
            onClick={() => set(on ? null : true)}
          />
          <span className="toggle-label">{f.label}</span>
          {f.flag && (
            <span className="flag" title={f.flag}>
              {f.flag}
            </span>
          )}
        </label>
        {help}
      </div>
    );
  }
  if (f.kind === 'bool') {
    const text = value === true || value === 'true' ? 'true' : value === false || value === 'false' ? 'false' : '';
    return (
      <div className={cls}>
        {label}
        <select
          className={`input mono${text ? '' : ' unset'}`}
          aria-label={f.label}
          value={text}
          onChange={(e) => set(e.target.value === '' ? null : e.target.value === 'true')}
        >
          <option value="">{f.default !== null ? `default: ${f.default}` : 'default'}</option>
          <option value="true">true</option>
          <option value="false">false</option>
        </select>
        {help}
      </div>
    );
  }
  if (f.kind === 'picker') {
    return (
      <div className={cls}>
        {label}
        <PolicyPicker page={page} field={f} value={value} />
        {help}
      </div>
    );
  }
  if (f.kind === 'choice') {
    return (
      <div className={cls}>
        {label}
        <ChoiceField field={f} value={value} set={set} />
        {help}
      </div>
    );
  }
  const suggestions = f.suggest.filter((x) => x !== value);
  return (
    <div className={cls}>
      {label}
      <input
        className={`input${f.mono ? ' mono' : ''}`}
        type={f.kind === 'number' ? 'number' : 'text'}
        step={f.kind === 'number' ? 'any' : undefined}
        aria-label={f.label}
        value={String(value ?? '')}
        placeholder={emptyText(f)}
        spellCheck={false}
        autoComplete="off"
        onChange={(e) => set(e.target.value)}
      />
      {suggestions.length > 0 && (
        <div className="assign">
          <span className="muted tiny">Suggestions</span>
          {suggestions.map((x) => (
            <button key={x} className="chip-btn" type="button" onClick={() => set(x)}>
              {x}
            </button>
          ))}
        </div>
      )}
      {help}
    </div>
  );
}

/** A select: lerobot's or the GUI's choices; for a flag, the first entry leaves it to lerobot's default. */
function ChoiceField({ field: f, value, set }: { field: FieldSpec; value: unknown; set: (v: unknown) => void }) {
  return (
    <SelectWithCustom
      value={isSet(value) ? String(value) : ''}
      options={f.options}
      empty={f.gui ? null : emptyText(f) || (f.required ? 'Select…' : 'default')}
      onChange={set}
      label={f.label}
      customLabel={`${f.label} (custom)`}
      allowCustom={f.custom}
      mono={f.mono}
      unset={!isSet(value) && !f.gui}
      placeholder={f.placeholder || 'type a value'}
    />
  );
}
