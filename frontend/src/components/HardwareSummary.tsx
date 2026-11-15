import { setPage } from '../state/app';
import { Card } from './Card';

export function HardwareSummary({ chips }: { chips: { label: string; value: string }[] }) {
  if (!chips.length) return null;
  return (
    <Card
      title="Hardware"
      extra={
        <button className="btn link" type="button" onClick={() => setPage('hardware')}>
          Edit
        </button>
      }
    >
      <div className="card-body" style={{ padding: '12px 16px' }}>
        <div className="summary">
          {chips.map((c) => (
            <span key={c.label} className="chip">
              <b>{c.label}</b>
              <span className="mono" title={c.value}>
                {c.value}
              </span>
            </span>
          ))}
        </div>
      </div>
    </Card>
  );
}
