import type { ReactNode } from 'react';

export function Card({ title, extra, id, children }: { title: ReactNode; extra?: ReactNode; id?: string; children?: ReactNode }) {
  return (
    <div className="card" id={id}>
      <div className="card-head">
        <div className="card-title">{title}</div>
        {extra}
      </div>
      {children}
    </div>
  );
}

export function StepTitle({ n, children }: { n: number; children: ReactNode }) {
  return (
    <span className="step-title">
      <span className="step-num">{n}</span>
      {children}
    </span>
  );
}
