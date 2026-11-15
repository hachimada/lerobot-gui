import { useEffect, useRef, useState } from 'react';
import { api } from '../api/client';
import type { OptionsListing, OptionsQuery } from '../api/types';
import { useStore } from '../lib/store';
import { app, bump } from '../state/app';

export interface OptionsState {
  loading: boolean;
  listing: OptionsListing | null;
  error: string | null;
}

/**
 * Every `--help` option of the page's command that its visible fields don't set. The first
 * listing for a selection imports lerobot on the server (a few seconds); after it the form is
 * asked again so the extras get checked against it. Filtering again on a value change is cheap.
 */
export function useOptions(page: string, query: OptionsQuery | null): OptionsState {
  const key = query ? JSON.stringify(query) : '';
  const pageValues = useStore(app, (s) => s.values[page]);
  const [state, setState] = useState<OptionsState>({ loading: !!query, listing: null, error: null });
  const loadedKey = useRef('');

  useEffect(() => {
    if (!key) return;
    const ctrl = new AbortController();
    const fresh = key !== loadedKey.current;
    if (fresh) setState((s) => ({ ...s, loading: true, error: null }));
    const timer = setTimeout(
      () => {
        const { values } = app.get();
        api
          .formOptions(page, { values: { hardware: values.hardware ?? {}, [page]: values[page] ?? {} } }, ctrl.signal)
          .then((listing) => {
            setState({ loading: false, listing, error: null });
            if (fresh) {
              loadedKey.current = key;
              bump();
            }
          })
          .catch((e: Error) => {
            if (e.name !== 'AbortError') setState({ loading: false, listing: null, error: e.message });
          });
      },
      fresh ? 0 : 150,
    );
    return () => {
      clearTimeout(timer);
      ctrl.abort();
    };
  }, [page, key, pageValues]);

  return state;
}
