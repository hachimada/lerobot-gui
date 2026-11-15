import { api, ApiError, apiUrl } from '../api/client';
import type { ArmCheck, JobInfo, Message } from '../api/types';
import { createStore } from '../lib/store';
import { Term } from '../lib/term';
import { app, bump, discover, toast } from './app';

/** A command started from a page: its info, its output, the stream that feeds them. */
export interface JobEntry {
  info: JobInfo;
  term: Term;
  offset: number;
  es: EventSource | null;
}

export const jobs = createStore<{ byPage: Record<string, JobEntry>; captured: number }>({ byPage: {}, captured: 0 });

const pageOf = (info: JobInfo): string | null =>
  info.page ?? app.get().pages.find((p) => p.exe === info.command)?.id ?? null;

function update(page: string, patch: Partial<JobEntry>): void {
  jobs.set((s) => {
    const cur = s.byPage[page];
    return cur ? { byPage: { ...s.byPage, [page]: { ...cur, ...patch } } } : {};
  });
}

function ended(page: string): void {
  if (page === 'find-cameras') jobs.set((s) => ({ captured: s.captured + 1 }));
  void discover(true); // new datasets, checkpoints, calibration files
}

function openStream(page: string): void {
  const entry = jobs.get().byPage[page];
  if (!entry || typeof EventSource === 'undefined') return;
  entry.es?.close();
  const es = new EventSource(apiUrl(`/jobs/${entry.info.id}/stream`, { offset: entry.offset }));
  update(page, { es });
  es.onmessage = (e: MessageEvent<string>) => {
    const d = JSON.parse(e.data) as { text: string; offset: number; reset: boolean };
    const cur = jobs.get().byPage[page];
    if (!cur || cur.es !== es) return;
    if (d.reset) cur.term.reset();
    cur.term.write(d.text);
    cur.offset = d.offset; // not state: the stream position only
  };
  es.addEventListener('info', (e) => update(page, { info: JSON.parse((e as MessageEvent<string>).data) as JobInfo }));
  es.addEventListener('end', (e) => {
    es.close();
    update(page, { info: JSON.parse((e as MessageEvent<string>).data) as JobInfo, es: null });
    ended(page);
  });
  es.onerror = () => {
    es.close();
    const cur = jobs.get().byPage[page];
    if (cur?.es === es) update(page, { es: null });
    // the server restarted or the connection dropped: pick up where it left off
    if (cur?.info.running) setTimeout(() => jobs.get().byPage[page] === cur && !cur.es && openStream(page), 1500);
  };
}

/** Ask for the captured frames again (after one was deleted). */
export function refreshCaptured(): void {
  jobs.set((s) => ({ captured: s.captured + 1 }));
}

export function attach(info: JobInfo): void {
  const page = pageOf(info);
  if (!page) return;
  jobs.get().byPage[page]?.es?.close();
  jobs.set((s) => ({ byPage: { ...s.byPage, [page]: { info, term: new Term(), offset: 0, es: null } } }));
  openStream(page);
}

export async function loadJobs(): Promise<void> {
  try {
    for (const info of await api.jobs()) attach(info);
  } catch (e) {
    toast((e as Error).message);
  }
}

/** The robot command running on another page, if any (one runs at a time). */
export function busyWith(page: string): JobEntry | null {
  return (
    Object.entries(jobs.get().byPage).find(([id, j]) => id !== page && j.info.running && j.info.hardware)?.[1] ?? null
  );
}

export type RunResult = { ok: true } | { ok: false; messages?: Message[]; preflight?: ArmCheck };

/** Run a page's command: the server builds it from the values, exactly as previewed. */
export async function run(page: string, { force = false } = {}): Promise<RunResult> {
  const { values } = app.get();
  try {
    const info = await api.run(page, values, force);
    app.set((s) => {
      const blocked = { ...s.blocked };
      delete blocked[page];
      return { blocked };
    });
    attach(info);
    return { ok: true };
  } catch (e) {
    const detail = e instanceof ApiError ? (e.detail as { preflight?: ArmCheck; messages?: Message[] } | null) : null;
    if (detail?.preflight) {
      const preflight = detail.preflight;
      app.set((s) => ({ blocked: { ...s.blocked, [page]: preflight } }));
      bump();
      return { ok: false, preflight };
    }
    toast((e as Error).message);
    return { ok: false, messages: detail?.messages };
  }
}

export async function signal(page: string, name: 'INT' | 'KILL'): Promise<void> {
  const entry = jobs.get().byPage[page];
  if (!entry) return;
  try {
    update(page, { info: await api.signal(entry.info.id, name) });
  } catch (e) {
    toast((e as Error).message);
  }
}

export async function input(page: string, text: string): Promise<void> {
  const entry = jobs.get().byPage[page];
  if (!entry) return;
  try {
    await api.input(entry.info.id, text);
  } catch (e) {
    toast((e as Error).message);
  }
}

/** Forget a finished job's card (Find port's Dismiss). */
export function dismiss(page: string): void {
  jobs.set((s) => {
    const byPage = { ...s.byPage };
    if (byPage[page] && !byPage[page].info.running) delete byPage[page];
    return { byPage };
  });
}
