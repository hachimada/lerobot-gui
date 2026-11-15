import { useState } from 'react';
import { api } from '../api/client';
import type { PresetInfo } from '../api/types';
import { useFetch } from '../hooks/useFetch';
import { useStore } from '../lib/store';
import { app, markPreset, replaceValues, toast } from '../state/app';
import { Card } from './Card';
import { Icon } from './Icon';

/** The same values, whatever their order. */
function same(a: Record<string, unknown> | undefined, b: Record<string, unknown> | undefined): boolean {
  const norm = (v: Record<string, unknown> | undefined) => JSON.stringify(Object.entries(v ?? {}).sort(([x], [y]) => x.localeCompare(y)));
  return norm(a) === norm(b);
}

/**
 * Presets of a command page: its values saved under a name (in the GUI's settings dir), loaded back
 * in place of the page's values. The Hardware page isn't part of them.
 */
export function PresetCard({ page }: { page: string }) {
  const values = useStore(app, (s) => s.values[page]);
  const current = useStore(app, (s) => s.presets[page] ?? null);
  const list = useFetch(() => api.presets(page));
  const loaded = useFetch(() => api.preset(page, current ?? ''), !!current);
  const [naming, setNaming] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const presets: PresetInfo[] = list.data ?? [];
  const changed = !!current && !!loaded.data && !same(loaded.data.values, values);
  const hasValues = Object.keys(values ?? {}).length > 0;

  const run = async (action: () => Promise<void>) => {
    setBusy(true);
    try {
      await action();
    } catch (e) {
      toast((e as Error).message);
    }
    setBusy(false);
  };
  const load = (name: string) =>
    run(async () => {
      if (hasValues && (!current || changed || current !== name) && !window.confirm(`Replace the values on this page with the preset “${name}”?`)) return;
      const preset = await api.preset(page, name);
      replaceValues(page, preset.values, preset.name);
      loaded.set(preset);
      toast(`Loaded “${preset.name}”`);
    });
  const save = (name: string) =>
    run(async () => {
      const preset = await api.savePreset(page, name, values ?? {});
      markPreset(page, preset.name);
      loaded.set(preset);
      setNaming(null);
      list.reload();
      toast(`Saved “${preset.name}”`);
    });
  const saveAs = (name: string) => {
    const trimmed = name.trim();
    if (!trimmed) return;
    if (presets.some((p) => p.name === trimmed) && !window.confirm(`Replace the preset “${trimmed}”?`)) return;
    void save(trimmed);
  };
  const remove = () =>
    run(async () => {
      if (!current || !window.confirm(`Delete the preset “${current}”?`)) return;
      list.set(await api.deletePreset(page, current));
      markPreset(page, null);
      toast(`Deleted “${current}”`);
    });

  return (
    <Card title="Presets">
      <div className="card-body preset-body">
        <div className="preset-row">
          <select
            className="input"
            aria-label="Load a preset"
            value=""
            disabled={busy || presets.length === 0}
            onChange={(e) => e.target.value && void load(e.target.value)}
          >
            <option value="">{presets.length ? 'Load a preset…' : 'No presets yet'}</option>
            {presets.map((p) => (
              <option key={p.name} value={p.name}>{`${p.name}  ·  ${p.count} value${p.count === 1 ? '' : 's'}`}</option>
            ))}
          </select>
          <button className="btn ghost small" type="button" disabled={busy} onClick={() => setNaming(current ?? '')}>
            <Icon name="plus" />
            Save as…
          </button>
        </div>
        {current && (
          <div className="preset-row preset-current">
            <span>
              From <b>{current}</b>
              {changed && <span className="pill">changed</span>}
            </span>
            <span className="preset-actions">
              <button className="btn ghost small" type="button" disabled={busy || !changed} onClick={() => void save(current)}>
                Save
              </button>
              <button className="btn danger small" type="button" disabled={busy} aria-label={`Delete the preset ${current}`} onClick={() => void remove()}>
                <Icon name="trash" />
              </button>
            </span>
          </div>
        )}
        {naming !== null && (
          <form
            className="preset-row"
            onSubmit={(e) => {
              e.preventDefault();
              saveAs(naming);
            }}
          >
            <input
              className="input"
              aria-label="Preset name"
              placeholder="Name"
              autoFocus
              value={naming}
              maxLength={80}
              onChange={(e) => setNaming(e.target.value)}
            />
            <button className="btn primary small" type="submit" disabled={busy || !naming.trim()}>
              Save
            </button>
            <button className="btn ghost small" type="button" onClick={() => setNaming(null)}>
              Cancel
            </button>
          </form>
        )}
        <div className="muted tiny">The values entered on this page, without the Hardware page. Loading one replaces them.</div>
      </div>
    </Card>
  );
}
