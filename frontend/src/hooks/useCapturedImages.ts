import { useEffect, useState } from 'react';
import { api } from '../api/client';
import type { CapturedImage } from '../api/types';
import { useStore } from '../lib/store';
import { jobs } from '../state/jobs';

/**
 * The frames lerobot-find-cameras saved in `dir` (empty: its default dir), asked for again after
 * each run or delete. `recordTime`: its --record-time-s as entered (tells an earlier run's frames).
 */
export function useCapturedImages(dir: string, recordTime = ''): CapturedImage[] {
  const capturedVersion = useStore(jobs, (s) => s.captured);
  const [images, setImages] = useState<CapturedImage[]>([]);
  useEffect(() => {
    let live = true;
    api
      .capturedImages(dir, recordTime)
      .then((list) => live && setImages(list))
      .catch(() => live && setImages([]));
    return () => {
      live = false;
    };
  }, [dir, recordTime, capturedVersion]);
  return images;
}
