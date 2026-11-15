import type {
  AccountStatus,
  AccountsResponse,
  ArmCheck,
  CapturedImage,
  HubModels,
  Discover,
  EnvironmentInfo,
  HfCloud,
  HfLocal,
  HfLocalItem,
  FormResponse,
  HardwareForm,
  JobInfo,
  OptionsListing,
  PageMeta,
  Ports,
  Preset,
  PresetInfo,
} from './types';

/** The API token the server put into the page (empty under `npm run dev`: the proxy adds it). */
export function pageToken(): string {
  const value = document.querySelector<HTMLMetaElement>('meta[name="lerobot-gui-token"]')?.content ?? '';
  return value === '__TOKEN__' ? '' : value;
}

export class ApiError extends Error {
  status: number;
  /** the server's `detail`: a message, or an object such as {message, preflight} */
  detail: unknown;

  constructor(status: number, message: string, detail: unknown) {
    super(message);
    this.status = status;
    this.detail = detail;
  }
}

export interface RequestOptions {
  method?: string;
  body?: unknown;
  signal?: AbortSignal;
}

async function request(path: string, opts: RequestOptions = {}): Promise<Response> {
  const headers: Record<string, string> = {};
  const token = pageToken();
  if (token) headers['X-Token'] = token;
  if (opts.body !== undefined) headers['Content-Type'] = 'application/json';
  const res = await fetch(`/api${path}`, {
    method: opts.method ?? (opts.body !== undefined ? 'POST' : 'GET'),
    headers,
    body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
    signal: opts.signal,
  });
  if (!res.ok) {
    let detail: unknown = null;
    try {
      detail = ((await res.json()) as { detail?: unknown }).detail ?? null;
    } catch {
      /* not JSON */
    }
    const message =
      typeof detail === 'string'
        ? detail
        : ((detail as { message?: string } | null)?.message ?? `${res.status} ${res.statusText}`);
    throw new ApiError(res.status, message, detail);
  }
  return res;
}

async function json<T>(path: string, opts?: RequestOptions): Promise<T> {
  return (await (await request(path, opts)).json()) as T;
}

/** A URL the browser fetches by itself (img src, EventSource): the token goes in the query. */
export function apiUrl(path: string, params: Record<string, string | number> = {}): string {
  const q = new URLSearchParams(Object.entries(params).map(([k, v]) => [k, String(v)]));
  const token = pageToken();
  if (token) q.set('token', token);
  const qs = q.toString();
  return `/api${path}${qs ? `?${qs}` : ''}`;
}

export type Values = Record<string, Record<string, unknown>>;

export interface FormBody {
  values: Values;
  /** the arm check that stopped the last Run of the page */
  preflight?: ArmCheck | null;
}

export const api = {
  pages: () => json<{ pages: PageMeta[]; nav: string[] }>('/pages'),
  discover: () => json<Discover>('/discover'),
  ports: () => json<Ports>('/ports'),
  form: (page: string, body: FormBody, signal?: AbortSignal) =>
    json<FormResponse>(`/form/${page}`, { body, signal }),
  hardware: (body: { hardware: Record<string, unknown>; arm_check: ArmCheck | null }, signal?: AbortSignal) =>
    json<HardwareForm>('/hardware', { body, signal }),
  formOptions: (page: string, body: FormBody, signal?: AbortSignal) =>
    json<OptionsListing>(`/form/${page}/options`, { body, signal }),
  run: (page: string, values: Values, force = false) =>
    json<JobInfo>(`/form/${page}/run`, { body: { values, force } }),
  jobs: () => json<JobInfo[]>('/jobs'),
  input: (id: string, text: string) => json<{ ok: boolean }>(`/jobs/${id}/input`, { body: { text } }),
  signal: (id: string, name: 'INT' | 'TERM' | 'KILL') => json<JobInfo>(`/jobs/${id}/signal`, { body: { name } }),
  checkArms: (hardware: Record<string, unknown>) => json<ArmCheck>('/check-arms', { body: { hardware } }),
  accounts: (refresh = false) => json<AccountsResponse>(`/accounts?refresh=${refresh ? 1 : 0}`),
  hfLogin: (secret: string) => json<AccountStatus>('/accounts/hf/login', { body: { secret } }),
  hfLogout: () => json<AccountStatus>('/accounts/hf/logout', { body: {} }),
  environment: () => json<EnvironmentInfo>('/environment'),
  presets: (page: string) => json<PresetInfo[]>(`/presets/${page}`),
  preset: (page: string, name: string) => json<Preset>(`/presets/${page}/${encodeURIComponent(name)}`),
  savePreset: (page: string, name: string, values: Record<string, unknown>) =>
    json<Preset>(`/presets/${page}/${encodeURIComponent(name)}`, { method: 'PUT', body: { values } }),
  deletePreset: (page: string, name: string) =>
    json<PresetInfo[]>(`/presets/${page}/${encodeURIComponent(name)}`, { method: 'DELETE' }),
  hfLocal: () => json<HfLocal>('/hf/local'),
  hfDelete: (item: HfLocalItem) => json<HfLocal>('/hf/local/delete', { body: item }),
  hfCloud: (refresh = false) => json<HfCloud>(`/hf/cloud?refresh=${refresh ? 1 : 0}`),
  hubModels: (refresh = false) => json<HubModels>(`/hub/models?refresh=${refresh ? 1 : 0}`),
  capturedImages: (dir: string, recordTime = '') =>
    json<CapturedImage[]>(`/captured-images?${new URLSearchParams({ dir, ...(recordTime ? { record_time: recordTime } : {}) })}`),
  deleteCapturedImage: (name: string, dir: string) =>
    json<{ ok: boolean }>(`/captured-images/${encodeURIComponent(name)}?${new URLSearchParams({ dir })}`, { method: 'DELETE' }),
};
