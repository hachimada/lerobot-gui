import { useCallback, useEffect, useState } from 'react';

export interface Fetched<T> {
  data: T | null;
  error: string | null;
  loading: boolean;
  /** ask again (`refresh`: past the server's cache) */
  reload: (refresh?: boolean) => void;
  /** replace the data with what an action returned */
  set: (data: T) => void;
}

/** Data the page asks the server for when it opens, with a way to ask again. */
export function useFetch<T>(load: (refresh: boolean) => Promise<T>, enabled = true): Fetched<T> {
  const [state, setState] = useState<{ data: T | null; error: string | null; done: boolean }>({ data: null, error: null, done: false });
  const [ask, setAsk] = useState({ n: 0, refresh: false });
  useEffect(() => {
    if (!enabled) return;
    let live = true;
    load(ask.refresh)
      .then((data) => live && setState({ data, error: null, done: true }))
      .catch((e: Error) => live && setState((s) => ({ ...s, error: e.message, done: true })));
    return () => {
      live = false;
    };
    // `load` is a new function on each render; asking again is what `ask` is for
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ask, enabled]);
  const reload = useCallback((refresh = false) => setAsk((a) => ({ n: a.n + 1, refresh })), []);
  const set = useCallback((data: T) => setState({ data, error: null, done: true }), []);
  return { data: state.data, error: state.error, loading: enabled && !state.done, reload, set };
}
