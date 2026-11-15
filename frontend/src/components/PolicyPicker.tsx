import { useState } from 'react';
import type { FieldSpec } from '../api/types';
import { useHubModels } from '../hooks/useHubModels';
import { setValues } from '../state/app';
import { Alerts } from './Alerts';
import { Icon } from './Icon';
import { isGroup } from './SelectWithCustom';

type Source = 'hub' | 'local';

interface Item {
  value: string;
  label: string;
  group: string;
  meta?: string;
}


export const fmtCount = (n: number): string =>
  n >= 1_000_000 ? `${(n / 1_000_000).toFixed(1)}M` : n >= 1_000 ? `${Math.round(n / 1_000)}k` : String(n);

function localItems(f: FieldSpec): Item[] {
  return f.options.flatMap((o) =>
    isGroup(o) ? o.items.map((i) => ({ value: i.value, label: i.label, group: o.group })) : [{ value: o.value, label: o.label, group: '' }],
  );
}

/** A policy: pick where it comes from (the Hub or a local checkpoint), then search the candidates. */
export function PolicyPicker({ page, field: f, value }: { page: string; field: FieldSpec; value: unknown }) {
  const [source, setSource] = useState<Source | null>(null);
  const [query, setQuery] = useState('');
  const hub = useHubModels(source === 'hub');
  const current = typeof value === 'string' ? value : '';
  const set = (v: string | null) => {
    setValues(page, { [f.key]: v });
    setSource(null);
    setQuery('');
  };

  const local = localItems(f);
  const hubItems: Item[] =
    hub.data?.groups.flatMap((g) =>
      g.models.map((m) => ({
        value: m.id,
        label: m.id,
        group: g.title,
        meta: [`${fmtCount(m.downloads)} downloads`, m.created, m.private ? 'private' : null].filter(Boolean).join(' · '),
      })),
    ) ?? [];
  const items = source === 'hub' ? hubItems : local;
  const q = query.trim();
  const shown = q ? items.filter((i) => `${i.value} ${i.label}`.toLowerCase().includes(q.toLowerCase())) : items;
  // what was typed, when it looks like a repo id or a path and isn't listed
  const typed = q.includes('/') && !items.some((i) => i.value === q) ? q : null;
  const what = source === 'hub' ? 'models on the Hub' : 'local checkpoints';

  return (
    <div className="picker">
      <div className={`picked${current ? '' : ' empty'}`}>
        {current ? (
          <>
            <span className="mono">{current}</span>
            <button className="btn link" type="button" onClick={() => set(null)}>
              Clear
            </button>
          </>
        ) : (
          <span>No policy chosen yet: browse {f.hub ? 'the Hub or ' : ''}the local checkpoints.</span>
        )}
      </div>
      <div className="pick-sources" role="group" aria-label={`${f.label}: browse`}>
        {f.hub && (
          <button
            type="button"
            className={`btn ghost small${source === 'hub' ? ' active' : ''}`}
            aria-pressed={source === 'hub'}
            onClick={() => setSource(source === 'hub' ? null : 'hub')}
          >
            <Icon name="cloud" />
            Hugging Face Hub
          </button>
        )}
        <button
          type="button"
          className={`btn ghost small${source === 'local' ? ' active' : ''}`}
          aria-pressed={source === 'local'}
          onClick={() => setSource(source === 'local' ? null : 'local')}
        >
          <Icon name="folder" />
          Local checkpoints · {local.length}
        </button>
      </div>
      {source && (
        <div className="pick-panel">
          <label className="pick-search">
            <Icon name="search" />
            <input
              type="search"
              aria-label={`Search ${what}`}
              placeholder={`Search ${items.length} ${what}, or type a ${source === 'hub' ? 'repo id' : 'path'}…`}
              value={query}
              autoFocus
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => {
                if (e.key !== 'Enter') return;
                e.preventDefault();
                const pick = shown[0]?.value ?? typed;
                if (pick) set(pick);
              }}
            />
          </label>
          {source === 'hub' && hub.error && <Alerts items={[{ level: 'warn', text: hub.error }]} />}
          <div className="pick-list" role="listbox" aria-label={what}>
            {typed && (
              <button className="pick-item" type="button" role="option" aria-selected={false} onClick={() => set(typed)}>
                Use <span className="mono">{typed}</span>
              </button>
            )}
            {source === 'hub' && hub.loading && <div className="dev-empty">Listing the models on the Hub…</div>}
            {shown.map((item, i) => (
              <div key={`${item.group}/${item.value}`}>
                {item.group && item.group !== shown[i - 1]?.group && <div className="pick-group">{item.group}</div>}
                <button
                  className={`pick-item${item.value === current ? ' active' : ''}`}
                  type="button"
                  role="option"
                  aria-selected={item.value === current}
                  title={item.value}
                  onClick={() => set(item.value)}
                >
                  <span className="mono">{item.label}</span>
                  {item.meta && <span className="pick-meta">{item.meta}</span>}
                </button>
              </div>
            ))}
            {!shown.length && !typed && !(source === 'hub' && hub.loading) && (
              <div className="dev-empty">{items.length ? 'No match.' : `No ${what}.`}</div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
