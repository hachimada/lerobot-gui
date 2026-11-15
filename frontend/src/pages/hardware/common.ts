import { useMemo } from 'react';
import type { CameraConfig } from '../../api/types';
import { useStore } from '../../lib/store';
import { app } from '../../state/app';

/** The cameras of the Hardware page, as stored (an entry that isn't an object is left out, as the server does). */
export function useCameras(): CameraConfig[] {
  const stored = useStore(app, (s) => s.values.hardware?.cameras);
  return useMemo(
    () => (Array.isArray(stored) ? stored.filter((c): c is CameraConfig => !!c && typeof c === 'object') : []),
    [stored],
  );
}
