import { api, type Values } from '../api/client';
import type { AccountsResponse, Action, ArmCheck, CameraConfig, Discover, PageMeta, Ports } from '../api/types';
import { withIds } from '../lib/hardware';
import { createStore } from '../lib/store';

/** What survives a reload: the page and the values the user changed (per page). */
export interface Persisted {
  page: string;
  values: Values;
  openAdv: string[];
  /** page -> the preset its values were loaded from or saved as */
  presets: Record<string, string>;
}

/** each page's values keyed by lerobot flag (`dataset.repo_id`), as the server's fields are */
export const STORAGE_KEY = 'lerobot-gui:v2';

export function loadPersisted(storage: Storage | undefined = globalThis.localStorage): Persisted {
  // the first step of the setup
  const empty: Persisted = { page: 'hardware', values: {}, openAdv: [], presets: {} };
  try {
    const raw = storage?.getItem(STORAGE_KEY);
    if (!raw) return empty;
    const data = JSON.parse(raw) as Partial<Persisted>;
    const values = data.values && typeof data.values === 'object' ? data.values : {};
    const cameras = values.hardware?.cameras;
    // cameras saved before they had ids get theirs now, so their rows keep their keys
    if (Array.isArray(cameras)) values.hardware = { ...values.hardware, cameras: withIds(cameras as CameraConfig[]) };
    return {
      page: typeof data.page === 'string' ? data.page : empty.page,
      values,
      openAdv: Array.isArray(data.openAdv) ? data.openAdv.filter((x) => typeof x === 'string') : [],
      presets:
        data.presets && typeof data.presets === 'object'
          ? Object.fromEntries(Object.entries(data.presets).filter(([, v]) => typeof v === 'string'))
          : {},
    };
  } catch {
    return empty; // unreadable
  }
}

export interface ArmCheckState {
  loading: boolean;
  result: ArmCheck | null;
  error: string | null;
  at: number;
}

export interface AppState extends Persisted {
  pages: PageMeta[];
  nav: string[];
  /** ports and calibration files, polled */
  ports: Ports | null;
  discover: Discover | null;
  accounts: AccountsResponse | null;
  accountsBusy: boolean;
  armCheck: ArmCheckState;
  /** page -> the arm check that stopped its last Run */
  blocked: Record<string, ArmCheck>;
  toast: { text: string; id: number } | null;
  /** bumped when something the forms depend on changed (workspace, logins, option listings) */
  version: number;
}

const NO_CHECK: ArmCheckState = { loading: false, result: null, error: null, at: 0 };

export const app = createStore<AppState>({
  ...loadPersisted(),
  pages: [],
  nav: [],
  ports: null,
  discover: null,
  accounts: null,
  accountsBusy: false,
  armCheck: NO_CHECK,
  blocked: {},
  toast: null,
  version: 0,
});

let saved = '';
app.subscribe(() => {
  const { page, values, openAdv, presets } = app.get();
  const text = JSON.stringify({ page, values, openAdv, presets });
  if (text === saved) return;
  saved = text;
  try {
    localStorage.setItem(STORAGE_KEY, text);
  } catch {
    /* private mode / full: values just don't persist */
  }
});

// ------------------------------------------------------------------ values

/** `values` with `patch` applied: a value that is null or empty is removed. */
function patched(values: Record<string, unknown> | undefined, patch: Record<string, unknown>): Record<string, unknown> {
  const merged: Record<string, unknown> = { ...(values ?? {}) };
  for (const [k, v] of Object.entries(patch)) {
    if (v === null || v === undefined || v === '') delete merged[k];
    else merged[k] = v;
  }
  return merged;
}

/**
 * Change values of a command page. A value that is null or empty is removed: for a lerobot flag that
 * means "not entered", so it leaves the command and lerobot's default applies.
 */
export function setValues(page: string, patch: Record<string, unknown>): void {
  app.set((s) => ({ values: { ...s.values, [page]: patched(s.values[page], patch) } }));
}

export interface HardwareOptions {
  /** keep the Check arms result (the change doesn't move an arm) */
  keepCheck?: boolean;
}

/**
 * Change Hardware values (null or empty removes one). The Check arms result and the runs it stopped
 * go with it, unless the change moves no arm (`keepCheck`: a board remembered, the cameras).
 */
export function setHardware(patch: Record<string, unknown>, opts: HardwareOptions = {}): void {
  app.set((s) => ({
    values: { ...s.values, hardware: patched(s.values.hardware, patch) },
    ...(opts.keepCheck ? {} : { armCheck: NO_CHECK, blocked: {} }),
  }));
}

/** Replace all the values of a page (loading a preset), and remember which preset they came from. */
export function replaceValues(page: string, values: Record<string, unknown>, preset: string | null): void {
  const clean = Object.fromEntries(Object.entries(values).filter(([, v]) => v !== null && v !== undefined && v !== ''));
  app.set((s) => {
    const presets = { ...s.presets };
    if (preset) presets[page] = preset;
    else delete presets[page];
    return { values: { ...s.values, [page]: clean }, presets };
  });
}

/** Remember (or forget) the preset a page's values are saved as. */
export function markPreset(page: string, preset: string | null): void {
  app.set((s) => {
    const presets = { ...s.presets };
    if (preset) presets[page] = preset;
    else delete presets[page];
    return { presets };
  });
}

export function pageMeta(id: string): PageMeta | undefined {
  return app.get().pages.find((p) => p.id === id);
}

/** Pages without a sidebar entry (find-port, find-cameras) live on the Hardware page. */
export function navId(id: string): string {
  const meta = pageMeta(id);
  if (!meta) return app.get().pages.length ? 'hardware' : id;
  return meta.nav ? id : 'hardware';
}

export function setPage(id: string): void {
  const page = navId(id);
  app.set({ page });
  if (typeof history !== 'undefined') history.replaceState(null, '', `#${page}`);
  document.querySelector('.main')?.scrollTo?.({ top: 0 });
}

export function toggleOpen(key: string, open: boolean): void {
  app.set((s) => ({ openAdv: s.openAdv.filter((x) => x !== key).concat(open ? [key] : []) }));
}

let toastId = 0;
export function toast(text: string): void {
  app.set({ toast: { text, id: ++toastId } });
}

export function bump(): void {
  app.set((s) => ({ version: s.version + 1 }));
}

// ---------------------------------------------------------------- loading

export async function loadPages(): Promise<void> {
  const { pages, nav } = await api.pages();
  app.set({ pages, nav });
  app.set((s) => ({ page: navId(s.page) }));
}

export async function discover(quiet = true): Promise<void> {
  try {
    const d = await api.discover();
    app.set({ discover: d, ports: { ports: d.ports, calibrations: d.calibrations } });
    bump();
    if (!quiet) {
      toast(
        `Found ${d.ports.length} port(s), ${d.datasets} dataset(s), ` +
          `${d.policies} training run(s)`,
      );
    }
  } catch (e) {
    toast(`Scan failed: ${(e as Error).message}`);
  }
}

let portsSig = '';
/** Keep ports, cameras and calibration files current (things get plugged in and out). */
export async function refreshPorts(): Promise<void> {
  if (typeof document !== 'undefined' && document.hidden) return;
  try {
    const ports = await api.ports();
    const sig = JSON.stringify(ports);
    if (sig === portsSig) return;
    portsSig = sig;
    app.set({ ports });
  } catch {
    /* server restarting */
  }
}

export async function loadAccounts(refresh = false): Promise<void> {
  try {
    app.set({ accounts: await api.accounts(refresh) });
  } catch (e) {
    toast((e as Error).message);
  }
  bump();
}

/** Log in to Hugging Face with a token (`secret`), or log out (null). */
export async function hfAccount(secret: string | null): Promise<void> {
  app.set({ accountsBusy: true });
  try {
    const status = secret === null ? await api.hfLogout() : await api.hfLogin(secret);
    app.set({ accounts: { hf: status } });
    toast(secret === null ? 'Logged out' : `Logged in${status.user ? ` as ${status.user}` : ''}`);
    bump();
  } catch (e) {
    toast((e as Error).message);
  }
  app.set({ accountsBusy: false });
}

// --------------------------------------------------------------- arm check

export async function checkArms(): Promise<void> {
  app.set({ armCheck: { ...app.get().armCheck, loading: true, error: null } });
  try {
    const result = await api.checkArms(app.get().values.hardware ?? {});
    app.set({ armCheck: { loading: false, result, error: null, at: Date.now() / 1000 } });
    // the arms whose motors hold their own calibration are on the right port: their boards are remembered
    if (result.remember) runAction(result.remember);
  } catch (e) {
    app.set({ armCheck: { loading: false, result: null, error: (e as Error).message, at: 0 } });
  }
}

// ----------------------------------------------------------------- actions

export interface ActionContext {
  /** Run the current page again, skipping the arm check */
  runForce?: () => void;
}

export function runAction(action: Action, ctx: ActionContext = {}): void {
  switch (action.type) {
    case 'go':
      setPage(action.page);
      break;
    case 'set':
      setValues(action.page, action.values);
      if (action.toast) toast(action.toast);
      if (action.go) setPage(action.go);
      break;
    case 'hardware':
      setHardware(action.values, { keepCheck: action.keep_check });
      if (action.toast) toast(action.toast);
      break;
    case 'check_arms':
      void checkArms();
      break;
    case 'scroll':
      document.getElementById(action.target)?.scrollIntoView?.({ behavior: 'smooth', block: 'start' });
      break;
    case 'run_force':
      if (!action.confirm || window.confirm(action.confirm)) ctx.runForce?.();
      break;
  }
}
