import { useEffect, useState } from 'react';
import { api } from '../api/client';
import type { ArmCheck, FormResponse, HardwareForm } from '../api/types';
import { useStore } from '../lib/store';
import { app } from '../state/app';

export const FORM_DEBOUNCE_MS = 80;

/** What `ask` answers, asked again (debounced, the previous request dropped) whenever `deps` change. */
function useAnswer<T>(ask: (signal: AbortSignal) => Promise<T>, deps: unknown[]): T | null {
  const [data, setData] = useState<T | null>(null);
  useEffect(() => {
    const ctrl = new AbortController();
    const timer = setTimeout(() => {
      ask(ctrl.signal)
        .then(setData)
        .catch((e: Error) => {
          if (e.name !== 'AbortError') console.error(e);
        });
    }, FORM_DEBOUNCE_MS);
    return () => {
      clearTimeout(timer);
      ctrl.abort();
    };
    // `ask` is a new function on each render; `deps` are what it reads
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  return data;
}

/**
 * The server's answer for command page `page` with the values entered so far: fields, command line, messages.
 * Asked again whenever the values, the plugged-in hardware or the workspace change.
 */
export function useForm(page: string): FormResponse | null {
  const pageValues = useStore(app, (s) => s.values[page]);
  const hwValues = useStore(app, (s) => s.values.hardware);
  const ports = useStore(app, (s) => s.ports);
  const version = useStore(app, (s) => s.version);
  const preflight = useStore(app, (s) => s.blocked[page] ?? null);
  const data = useAnswer(
    (signal) => api.form(page, { values: { hardware: hwValues ?? {}, [page]: pageValues ?? {} }, preflight }, signal),
    [page, pageValues, hwValues, ports, version, preflight],
  );
  // a different page: don't show the previous page's form meanwhile
  return data?.page === page ? data : null;
}

/**
 * The Hardware page for its values: each arm's port and id fields, what is plugged in, the setup status and
 * `armCheck` (the last Check arms result) explained. Asked again whenever they or what is plugged in change.
 */
export function useHardwareForm(armCheck: ArmCheck | null): HardwareForm | null {
  const hwValues = useStore(app, (s) => s.values.hardware);
  const ports = useStore(app, (s) => s.ports);
  const version = useStore(app, (s) => s.version);
  return useAnswer((signal) => api.hardware({ hardware: hwValues ?? {}, arm_check: armCheck }, signal), [
    hwValues,
    ports,
    version,
    armCheck,
  ]);
}
