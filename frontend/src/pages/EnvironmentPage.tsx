import { api } from '../api/client';
import { Alerts } from '../components/Alerts';
import { Card } from '../components/Card';
import { Icon } from '../components/Icon';
import { useFetch } from '../hooks/useFetch';
import { Rich } from '../lib/rich';

/** The environment the commands run in (they inherit the GUI's), as the server reports it. */
export function EnvironmentPage() {
  const { data: info, error, reload: readAgain } = useFetch(() => api.environment());

  const reload = (
    <button className="btn ghost small" type="button" onClick={() => readAgain()}>
      <Icon name="refresh" />
      Read again
    </button>
  );
  if (error || !info) {
    return (
      <div className="content single">
        {error ? <Alerts items={[{ level: 'err', text: `Could not read the environment: ${error}` }]} /> : <div className="muted">Reading the environment…</div>}
      </div>
    );
  }
  return (
    <div className="content single">
      <section className="form">
        <Card title="lerobot's data dirs" extra={reload}>
          <div className="env-list">
            {info.locations.map((l) =>
              l.error ? (
                <div key={l.name} className="env-row">
                  <Alerts items={[{ level: 'err', text: `${l.name}: ${l.error}` }]} />
                </div>
              ) : (
                <div key={l.name} className="env-row">
                  <div className="env-name">
                    <span className="mono">{l.name}</span>
                    <span className={`pill${l.from_env ? ' ok' : ''}`}>{l.from_env ? 'set in the environment' : 'default'}</span>
                  </div>
                  <div className="env-value mono">{l.value}</div>
                  <div className="muted tiny">from {l.read_from}</div>
                </div>
              ),
            )}
          </div>
        </Card>
        <Card title="Environment variables">
          <div className="env-list">
            {info.variables.map((v) => (
              <div key={v.name} className="env-row">
                <div className="env-name">
                  <span className="mono">{v.name}</span>
                  {!v.set && <span className="muted tiny">not set</span>}
                  {v.set && v.secret && <span className="pill">set · hidden</span>}
                </div>
                {v.set && !v.secret && <div className="env-value mono">{v.value}</div>}
                {v.note && (
                  <div className="muted tiny">
                    <Rich text={v.note} />
                  </div>
                )}
              </div>
            ))}
          </div>
        </Card>
      </section>
      <section className="side">
        <Card title="What runs">
          <div className="env-list">
            {info.runtime.map((r) => (
              <div key={r.name} className="env-row kv">
                <span>{r.name}</span>
                <span className="env-value mono">{r.value}</span>
              </div>
            ))}
          </div>
        </Card>
      </section>
    </div>
  );
}
