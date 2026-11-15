import { useEffect, useState } from 'react';
import { useStore } from '../lib/store';
import { app } from '../state/app';

export const TOAST_MS = 3800;

export function Toast() {
  const toast = useStore(app, (s) => s.toast);
  const [hidden, setHidden] = useState(0); // id of the last toast that timed out
  useEffect(() => {
    if (!toast) return;
    const id = setTimeout(() => setHidden(toast.id), TOAST_MS);
    return () => clearTimeout(id);
  }, [toast]);
  const shown = !!toast && toast.id !== hidden;
  return (
    <div className={`toast${shown ? ' show' : ''}`} role="status">
      {toast?.text}
    </div>
  );
}
