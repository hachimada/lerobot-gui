import { useEffect, useState } from 'react';
import { api } from '../api/client';
import type { HubModels } from '../api/types';
import { useStore } from '../lib/store';
import { app } from '../state/app';

export interface HubState {
  loading: boolean;
  data: HubModels | null;
  error: string | null;
}

/** The listing asked for, by the Hugging Face account logged in ('' for none): it has that account's models. */
const pending = new Map<string, Promise<HubModels>>();

/** Forget the listings (tests; the server caches them for an hour anyway). */
export function resetHubModels(): void {
  pending.clear();
}

/** The Hub's models, asked for the first time a picker opens its Hub list (needs the network), and again
 * after logging in or out. */
export function useHubModels(enabled: boolean): HubState {
  const user = useStore(app, (s) => s.accounts?.hf.user ?? '');
  const [result, setResult] = useState<{ user: string; data: HubModels | null; error: string | null } | null>(null);
  useEffect(() => {
    if (!enabled) return;
    let live = true;
    let request = pending.get(user);
    if (!request) {
      request = api.hubModels();
      pending.set(user, request);
    }
    const asked = request;
    asked
      .then((data) => live && setResult({ user, data, error: data.error }))
      .catch((e: Error) => {
        if (pending.get(user) === asked) pending.delete(user); // try again next time
        if (live) setResult({ user, data: null, error: e.message });
      });
    return () => {
      live = false;
    };
  }, [enabled, user]);
  const current = result?.user === user ? result : null;
  return { loading: enabled && current === null, data: current?.data ?? null, error: current?.error ?? null };
}
