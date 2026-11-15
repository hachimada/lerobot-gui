import { useEffect } from 'react';
import { Sidebar } from './components/Sidebar';
import { Toast } from './components/Toast';
import { Rich } from './lib/rich';
import { useStore } from './lib/store';
import { CommandPage } from './pages/CommandPage';
import { EnvironmentPage } from './pages/EnvironmentPage';
import { HardwarePage } from './pages/HardwarePage';
import { HuggingFacePage } from './pages/HuggingFacePage';
import { TrackioPage } from './pages/TrackioPage';
import { app, discover, loadAccounts, loadPages, navId, refreshPorts, setPage, toast } from './state/app';
import { loadJobs } from './state/jobs';

export const PORTS_POLL_MS = 3000;

/** Load what every page needs, then keep the plugged-in hardware current. */
export function useBoot(): void {
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        await loadPages();
      } catch (e) {
        toast(`Could not reach the server: ${(e as Error).message}`);
        return;
      }
      if (cancelled) return;
      const fromHash = location.hash.slice(1);
      if (fromHash) setPage(fromHash);
      await discover(true);
      void loadAccounts();
      void loadJobs();
    })();
    const poll = setInterval(() => void refreshPorts(), PORTS_POLL_MS);
    const onFocus = () => void refreshPorts();
    const onHash = () => {
      const id = location.hash.slice(1);
      if (id && navId(id) !== app.get().page) setPage(id);
    };
    window.addEventListener('focus', onFocus);
    window.addEventListener('hashchange', onHash);
    return () => {
      cancelled = true;
      clearInterval(poll);
      window.removeEventListener('focus', onFocus);
      window.removeEventListener('hashchange', onHash);
    };
  }, []);
}

export function App() {
  useBoot();
  const pages = useStore(app, (s) => s.pages);
  const current = useStore(app, (s) => s.page);
  const meta = pages.find((p) => p.id === current);
  let body = null;
  if (meta?.id === 'hardware') body = <HardwarePage />;
  else if (meta?.id === 'huggingface') body = <HuggingFacePage />;
  else if (meta?.id === 'environment') body = <EnvironmentPage />;
  else if (meta?.id === 'trackio') body = <TrackioPage meta={meta} />;
  else if (meta) body = <CommandPage key={meta.id} meta={meta} />;
  return (
    <div className="app">
      <Sidebar />
      <main className="main">
        <header className="page-head">
          <div>
            <h1>{meta?.title ?? 'LeRobot GUI'}</h1>
            <p className="muted">
              <Rich text={meta?.desc} />
            </p>
          </div>
        </header>
        {body}
      </main>
      <Toast />
    </div>
  );
}
