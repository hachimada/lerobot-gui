import { vi } from 'vitest';
import type { FieldSpec, FormResponse, PageMeta } from '../api/types';
import { app, type AppState } from '../state/app';
import { jobs } from '../state/jobs';

const initial: AppState = { ...app.get() };

/** Reset the singleton stores between tests. */
export function resetStores(patch: Partial<AppState> = {}): void {
  app.set({
    ...initial,
    page: 'rollout',
    values: {},
    openAdv: [],
    presets: {},
    armCheck: { loading: false, result: null, error: null, at: 0 },
    blocked: {},
    version: 0,
    ...patch,
  });
  jobs.set({ byPage: {}, captured: 0 });
}

export interface Call {
  path: string;
  method: string;
  body: unknown;
}

type Handler = (body: unknown, path: string) => unknown;

/** Stub fetch with routes like 'POST /api/form/teleoperate' (a handler or a JSON value). */
export function mockApi(routes: Record<string, Handler | unknown>): Call[] {
  const calls: Call[] = [];
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string, init: RequestInit = {}) => {
      const method = init.method ?? 'GET';
      const path = String(url).split('?')[0]!;
      const body = init.body ? JSON.parse(String(init.body)) : undefined;
      calls.push({ path, method, body });
      const route = routes[`${method} ${path}`];
      if (route === undefined) return new Response(JSON.stringify({ detail: `no mock for ${method} ${path}` }), { status: 404 });
      const out = typeof route === 'function' ? (route as Handler)(body, path) : route;
      if (out instanceof Response) return out;
      return new Response(JSON.stringify(out), { status: 200, headers: { 'Content-Type': 'application/json' } });
    }),
  );
  return calls;
}

export const jsonError = (status: number, detail: unknown) =>
  new Response(JSON.stringify({ detail }), { status, headers: { 'Content-Type': 'application/json' } });

export function field(patch: Partial<FieldSpec> & Pick<FieldSpec, 'key' | 'kind'>): FieldSpec {
  return {
    label: patch.key,
    gui: patch.key.startsWith('gui.'),
    flag: patch.key.startsWith('gui.') ? null : `--${patch.key}`,
    value: null,
    default: null,
    required: false,
    options: [],
    help: null,
    placeholder: '',
    custom: false,
    hub: false,
    mono: false,
    half: false,
    advanced: false,
    suggest: [],
    also: null,
    ...patch,
  };
}

export function formResponse(patch: Partial<FormResponse> = {}): FormResponse {
  return {
    page: 'teleoperate',
    groups: [],
    values: {},
    hardware_summary: [],
    command: { exe: 'lerobot-teleoperate', args: ['--fps=30'], preview: 'uv run lerobot-teleoperate \\\n    --fps=30' },
    messages: [],
    errors: 0,
    options_query: null,
    listing_ready: true,
    ...patch,
  };
}

export const PAGES: PageMeta[] = [
  { id: 'hardware', title: 'Hardware', icon: 'hardware', nav: 'Setup', exe: null, desc: '', hints: [], hardware: false, presets: false },
  { id: 'environment', title: 'Environment', icon: 'env', nav: 'Setup', exe: null, desc: '', hints: [], hardware: false, presets: false },
  { id: 'find-port', title: 'Find port', icon: 'port', nav: null, exe: 'lerobot-find-port', desc: '', hints: [], hardware: true, presets: false },
  { id: 'teleoperate', title: 'Teleoperate', icon: 'teleop', nav: 'Data', exe: 'lerobot-teleoperate', desc: 'Drive the follower.', hints: ['Stop sends Ctrl+C.'], hardware: true, presets: true },
  { id: 'train', title: 'Train', icon: 'train', nav: 'Policy', exe: 'lerobot-train', desc: '', hints: [], hardware: false, presets: true },
  { id: 'rollout', title: 'Rollout', icon: 'rollout', nav: 'Policy', exe: 'lerobot-rollout', desc: '', hints: [], hardware: true, presets: true },
  { id: 'huggingface', title: 'Hugging Face', icon: 'huggingface', nav: 'Services', exe: null, desc: '', hints: [], hardware: false, presets: false },
  { id: 'trackio', title: 'Trackio', icon: 'chart', nav: 'Services', exe: 'trackio', desc: '', hints: ['Stop sends Ctrl+C.'], hardware: false, presets: false },
];
