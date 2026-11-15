import { useStore } from '../../lib/store';
import { app, toggleOpen } from '../../state/app';

/** A part of a card folded away (Options, Output), open or closed as the user left it (remembered under `id`). */
export function Folding({ id, title, children }: { id: string; title: string; children: React.ReactNode }) {
  const open = useStore(app, (s) => s.openAdv.includes(id));
  return (
    <details className="fp-out" open={open} onToggle={(e) => toggleOpen(id, (e.currentTarget as HTMLDetailsElement).open)}>
      <summary>{title}</summary>
      {children}
    </details>
  );
}
