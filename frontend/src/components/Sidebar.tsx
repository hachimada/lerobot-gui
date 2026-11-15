import { useStore } from '../lib/store';
import { app, discover, navId, setPage } from '../state/app';
import { jobs } from '../state/jobs';
import { Icon } from './Icon';
import { ThemeSwitch } from './ThemeSwitch';

export function Sidebar() {
  const pages = useStore(app, (s) => s.pages);
  const nav = useStore(app, (s) => s.nav);
  const current = useStore(app, (s) => s.page);
  const running = useStore(jobs, (s) => s.byPage);
  // a page's own command, or one run from it (find-port and find-cameras on Hardware)
  const isRunning = (id: string) => Object.entries(running).some(([page, e]) => e?.info.running && navId(page) === id);
  return (
    <aside className="sidebar">
      <div className="brand">
        <span className="brand-mark" aria-hidden="true">
          <svg viewBox="0 0 24 24">
            <path d="M7 16l4-8 2 4 2-2 2 6" />
          </svg>
        </span>
        <div className="brand-name">LeRobot GUI</div>
      </div>
      <nav className="nav" aria-label="Pages">
        {nav.map((group) => (
          <div key={group}>
            <div className="nav-group-title">{group}</div>
            {pages
              .filter((p) => p.nav === group)
              .map((p) => (
                <button
                  key={p.id}
                  className={`nav-item${p.id === current ? ' active' : ''}`}
                  aria-current={p.id === current ? 'page' : undefined}
                  onClick={() => setPage(p.id)}
                >
                  <Icon name={p.icon} />
                  {p.title}
                  {isRunning(p.id) && <span className="dot" title="Running" />}
                </button>
              ))}
          </div>
        ))}
      </nav>
      <div className="sidebar-foot">
        <div className="sidebar-tools">
          <button className="btn ghost small" title="Rescan ports, cameras, datasets and checkpoints" onClick={() => void discover(false)}>
            <Icon name="refresh" />
            Rescan
          </button>
          <ThemeSwitch />
        </div>
      </div>
    </aside>
  );
}
