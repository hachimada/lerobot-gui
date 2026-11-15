import { useState } from 'react';
import { api } from '../api/client';
import type { HfLocal, HfLocalItem, HubRepo } from '../api/types';
import { HfAccountCard } from '../components/AccountCard';
import { Alerts } from '../components/Alerts';
import { Card } from '../components/Card';
import { Icon } from '../components/Icon';
import { useFetch } from '../hooks/useFetch';
import { ago, day, fmtBytes, plural } from '../lib/format';
import { useStore } from '../lib/store';
import { app, discover, toast } from '../state/app';

function Reload({ onClick, label = 'Read again' }: { onClick: () => void; label?: string }) {
  return (
    <button className="btn ghost small" type="button" onClick={onClick}>
      <Icon name="refresh" />
      {label}
    </button>
  );
}

/** A row of a listing: what it is, details, and its actions on the right. */
function Item({ title, meta, children }: { title: React.ReactNode; meta?: React.ReactNode; children?: React.ReactNode }) {
  return (
    <div className="item-row">
      <div className="item-main">
        <div className="item-title">{title}</div>
        {meta && <div className="muted tiny">{meta}</div>}
      </div>
      {children && <div className="item-actions">{children}</div>}
    </div>
  );
}

/** Local data: lerobot's datasets, calibration files and the two Hub caches, each deletable. */
function LocalCards() {
  const local = useFetch(() => api.hfLocal());
  const [busy, setBusy] = useState<string | null>(null);
  const remove = async (key: string, what: string, size: number | null, item: HfLocalItem) => {
    const sized = size ? ` (${fmtBytes(size)})` : '';
    if (!window.confirm(`Delete ${what}${sized} from this computer? This can't be undone.`)) return;
    setBusy(key);
    try {
      const after = await api.hfDelete(item);
      local.set(after);
      toast(after.message ?? 'Deleted');
      void discover(true); // the datasets the other pages offer
    } catch (e) {
      toast((e as Error).message);
    }
    setBusy(null);
  };
  const del = (key: string, what: string, size: number | null, item: HfLocalItem) => (
    <button className="btn danger small" type="button" disabled={busy !== null} aria-label={`Delete ${what}`} onClick={() => void remove(key, what, size, item)}>
      <Icon name="trash" />
      {busy === key ? 'Deleting…' : 'Delete'}
    </button>
  );
  if (local.error) return <Alerts items={[{ level: 'err', text: `Could not read the local data: ${local.error}` }]} />;
  const d: HfLocal | null = local.data;
  if (!d) return <div className="muted">Reading the local data…</div>;
  const total = d.datasets.reduce((n, x) => n + x.size, 0);
  return (
    <>
      <Card title={<span>Datasets · <span className="mono">HF_LEROBOT_HOME</span></span>} extra={<Reload onClick={() => local.reload()} />}>
        <div className="item-list">
          <div className="item-row muted tiny">
            <span className="mono">{d.home}</span>
            {d.datasets.length > 0 && ` · ${plural(d.datasets.length, 'dataset')} · ${fmtBytes(total)}`}
          </div>
          {d.datasets.length === 0 && <div className="item-row muted">No datasets in HF_LEROBOT_HOME.</div>}
          {d.datasets.map((x) => (
            <Item
              key={x.repo_id}
              title={<span className="mono">{x.repo_id}</span>}
              meta={[
                x.episodes !== null ? plural(x.episodes, 'episode') : null,
                x.frames !== null ? plural(x.frames, 'frame') : null,
                x.fps ? `${x.fps} fps` : null,
                x.cameras.length ? `cameras: ${x.cameras.join(', ')}` : null,
                fmtBytes(x.size),
                ago(x.mtime),
              ]
                .filter(Boolean)
                .join(' · ')}
            >
              {del(`dataset/${x.repo_id}`, `the dataset ${x.repo_id}`, x.size, { kind: 'dataset', repo_id: x.repo_id })}
            </Item>
          ))}
        </div>
      </Card>
      <Card title="Calibration files">
        <div className="item-list">
          {d.calibrations.length === 0 && <div className="item-row muted">No calibration files.</div>}
          {d.calibrations.map((c) => (
            <Item key={`${c.kind}/${c.class}/${c.id}`} title={<span className="mono">{c.id}</span>} meta={`${c.kind} · ${c.class} · ${c.path}`}>
              {del(`calibration/${c.kind}/${c.class}/${c.id}`, `the calibration file ${c.id} (${c.class})`, null, {
                kind: 'calibration',
                calibration_kind: c.kind,
                cls: c.class,
                id: c.id,
              })}
            </Item>
          ))}
        </div>
      </Card>
      {d.caches.map((cache) => (
        <Card key={cache.name} title={<span>Downloaded · <span className="mono">{cache.name}</span></span>}>
          <div className="item-list">
            <div className="item-row muted tiny">
              <span className="mono">{cache.path ?? '—'}</span>
              {cache.repos.length > 0 && ` · ${fmtBytes(cache.size)}`}
            </div>
            {cache.error && (
              <div className="item-row">
                <Alerts items={[{ level: 'warn', text: cache.error }]} />
              </div>
            )}
            {cache.repos.length === 0 && !cache.error && <div className="item-row muted">Nothing downloaded here.</div>}
            {cache.repos.map((r) => (
              <Item
                key={`${r.repo_type}/${r.repo_id}`}
                title={
                  <>
                    <span className="tag">{r.repo_type}</span> <span className="mono">{r.repo_id}</span>
                  </>
                }
                meta={[fmtBytes(r.size), plural(r.files, 'file'), r.last_accessed ? `used ${ago(r.last_accessed)}` : null].filter(Boolean).join(' · ')}
              >
                {del(`cache/${cache.name}/${r.repo_type}/${r.repo_id}`, `${r.repo_id} (${r.repo_type}) from ${cache.name}`, r.size, {
                  kind: 'cache',
                  cache: cache.name,
                  repo_type: r.repo_type,
                  repo_id: r.repo_id,
                })}
              </Item>
            ))}
          </div>
        </Card>
      ))}
    </>
  );
}

function Repos({ title, repos }: { title: string; repos: HubRepo[] }) {
  return (
    <>
      <div className="item-row item-head">{`${title} · ${repos.length}`}</div>
      {repos.length === 0 && <div className="item-row muted tiny">None.</div>}
      {repos.map((r) => (
        <Item
          key={r.id}
          title={
            <a className="mono" href={r.url} target="_blank" rel="noopener noreferrer">
              {r.id}
            </a>
          }
          meta={[r.private ? 'private' : 'public', plural(r.downloads, 'download'), r.updated ? `updated ${day(r.updated)}` : null]
            .filter(Boolean)
            .join(' · ')}
        />
      ))}
    </>
  );
}

/** The account's and its organizations' datasets and models on the Hub. */
function CloudCard() {
  const loggedIn = useStore(app, (s) => !!s.accounts?.hf?.logged_in);
  const cloud = useFetch((refresh) => api.hfCloud(refresh), loggedIn);
  let body;
  if (!loggedIn) body = <div className="item-row muted">Log in to list your datasets and models on the Hub.</div>;
  else if (cloud.error) body = <Alerts items={[{ level: 'err', text: cloud.error }]} />;
  else if (!cloud.data) body = <div className="item-row muted">Asking the Hub…</div>;
  else {
    body = cloud.data.owners.map((o) => (
      <div key={o.owner} className="item-group">
        <div className="item-row item-owner">
          <span className="mono">{o.owner}</span>
          <span className="muted tiny">{o.kind === 'user' ? 'you' : 'organization'}</span>
        </div>
        {o.error && (
          <div className="item-row">
            <Alerts items={[{ level: 'warn', text: o.error }]} />
          </div>
        )}
        <Repos title="Datasets" repos={o.datasets} />
        <Repos title="Models" repos={o.models} />
      </div>
    ));
  }
  return (
    <Card title="On the Hub" extra={loggedIn ? <Reload label="Ask again" onClick={() => cloud.reload(true)} /> : null}>
      <div className="item-list">{body}</div>
    </Card>
  );
}

export function HuggingFacePage() {
  return (
    <div className="content">
      <section className="form">
        <HfAccountCard />
        <LocalCards />
      </section>
      <section className="side">
        <CloudCard />
      </section>
    </div>
  );
}
