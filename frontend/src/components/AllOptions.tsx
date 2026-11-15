import { useMemo, useState } from 'react';
import type { OptionInfo, OptionsQuery } from '../api/types';
import { useOptions } from '../hooks/useOptions';
import { isSet } from '../lib/format';
import { Rich } from '../lib/rich';
import { useStore } from '../lib/store';
import { app, setValues, toggleOpen } from '../state/app';
import { Alerts } from './Alerts';
import { Card } from './Card';

type Values = Record<string, unknown>;
const NO_VALUES: Values = {};

function OptionRow({ option: o, value, onChange }: { option: OptionInfo; value: string; onChange: (v: string) => void }) {
  const dflt = o.kind === 'choice' ? (o.selected ?? o.default ?? 'none') : (o.default ?? (o.required ? 'required' : 'None'));
  const choices = o.kind === 'bool' ? ['true', 'false'] : (o.choices ?? []);
  return (
    <div className={`opt-row${isSet(value) ? ' is-set' : ''}`}>
      <div className="opt-text">
        <div className="opt-head">
          <span className="opt-flag mono">--{o.flag}</span>
          <span className="opt-type mono">{o.kind === 'choice' ? 'type' : o.type}</span>
        </div>
        {o.help && <div className="help">{o.help}</div>}
      </div>
      <div className="opt-ctl">
        {['bool', 'enum', 'choice'].includes(o.kind) ? (
          <select className="input mono" aria-label={`--${o.flag}`} value={value} onChange={(e) => onChange(e.target.value)}>
            <option value="">default: {dflt}</option>
            {choices.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        ) : (
          <input
            className="input mono"
            aria-label={`--${o.flag}`}
            value={value}
            spellCheck={false}
            placeholder={`default: ${dflt}`}
            inputMode={['int', 'float'].includes(o.kind) ? 'decimal' : undefined}
            onChange={(e) => onChange(e.target.value)}
          />
        )}
      </div>
    </div>
  );
}

/** Every `--help` option for the current selection that the fields above don't set. */
export function AllOptions({ page, exe, query }: { page: string; exe: string; query: OptionsQuery | null }) {
  const { loading, listing, error } = useOptions(page, query);
  // the page's values, keyed by flag like the options (the fields above use the same ones)
  const values = useStore(app, (s) => (s.values[page] as Values | undefined) ?? NO_VALUES);
  const openAdv = useStore(app, (s) => s.openAdv);
  const [search, setSearch] = useState('');
  const valueOf = (flag: string): string => (isSet(values[flag]) ? String(values[flag]) : '');
  const setExtra = (flag: string, value: string) => setValues(page, { [flag]: value });
  const listedFlags = (listing?.options ?? []).map((o) => o.flag);
  const nSet = listedFlags.filter((f) => isSet(values[f])).length;
  const groups = useMemo(() => {
    const q = search.trim().toLowerCase();
    const shown = (listing?.options ?? []).filter(
      (o) => !q || o.flag.toLowerCase().includes(q) || (o.help || '').toLowerCase().includes(q),
    );
    const out = new Map<string, OptionInfo[]>();
    for (const o of shown) {
      const g = o.flag.includes('.') ? o.flag.split('.')[0]! : 'general';
      out.set(g, [...(out.get(g) ?? []), o]);
    }
    return [...out].sort(([a], [b]) => (a === 'general' ? '' : a).localeCompare(b === 'general' ? '' : b));
  }, [listing, search]);

  const head = nSet ? (
    <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
      <span className="pill ok">{nSet} set</span>
      <button
        className="btn ghost small"
        type="button"
        onClick={() => setValues(page, Object.fromEntries(listedFlags.map((f) => [f, null])))}
      >
        Reset
      </button>
    </div>
  ) : null;
  const intro = (
    <div className="hint" style={{ paddingBottom: 4 }}>
      <Rich text={`Every \`${exe} --help\` option for the current selection that isn't set above. Empty uses lerobot's default.`} />
    </div>
  );
  if (loading && !listing) {
    return (
      <Card title="All options" extra={head}>
        {intro}
        <div className="dev-empty">Reading the options from lerobot… (the first time takes a few seconds)</div>
      </Card>
    );
  }
  if (error) {
    return (
      <Card title="All options" extra={head}>
        {intro}
        <div className="card-body">
          <Alerts items={[{ level: 'err', text: error }]} />
        </div>
      </Card>
    );
  }
  const total = listing?.options.length ?? 0;
  return (
    <Card title="All options" extra={head}>
      {intro}
      <div className="card-body">
        {listing?.errors.length ? <Alerts items={listing.errors.map((text) => ({ level: 'warn' as const, text }))} /> : null}
        <input
          className="input"
          type="search"
          aria-label="Search options"
          placeholder={`Search ${total} options (flag or help text)…`}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <div className="opt-groups">
          {groups.length === 0 && <div className="dev-empty">No option matches.</div>}
          {groups.map(([g, items]) => {
            const key = `${page}:opt:${g}`;
            const nG = items.filter((o) => isSet(values[o.flag])).length;
            return (
              <details
                key={g}
                className="opt-group"
                open={!!search.trim() || nG > 0 || openAdv.includes(key)}
                onToggle={(e) => {
                  if (!search.trim()) toggleOpen(key, (e.currentTarget as HTMLDetailsElement).open);
                }}
              >
                <summary>
                  <span className="mono">{g === 'general' ? 'general' : `${g}.*`}</span>
                  <span className="muted tiny">{items.length}</span>
                  {nG > 0 && <span className="pill ok">{nG} set</span>}
                </summary>
                <div className="opt-rows">
                  {items.map((o) => (
                    <OptionRow key={o.flag} option={o} value={valueOf(o.flag)} onChange={(v) => setExtra(o.flag, v)} />
                  ))}
                </div>
              </details>
            );
          })}
        </div>
      </div>
    </Card>
  );
}
