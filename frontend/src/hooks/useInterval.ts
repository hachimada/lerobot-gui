import { useEffect, useState } from 'react';

/** The time in seconds, updated every `ms` while `active` (e.g. a running job's clock). */
export function useNow(ms: number, active: boolean): number {
  const [now, setNow] = useState(() => Date.now() / 1000);
  useEffect(() => {
    if (!active) return;
    const id = setInterval(() => setNow(Date.now() / 1000), ms);
    return () => clearInterval(id);
  }, [ms, active]);
  return now;
}
