import type { HardwareView, StatusItem } from '../../api/types';
import { ActionButtons } from '../../components/Alerts';
import { Card } from '../../components/Card';
import { Rich } from '../../lib/rich';

const MARK = { ok: '✓', warn: '!', err: '✕', todo: '' };

export function SetupStatus({ items }: { items: StatusItem[] }) {
  return (
    <Card title="Setup status">
      <div className="status-list">
        {items.map((it, i) => (
          <div key={i} className="status-item">
            <span className={`status-icon ${it.level}`}>{MARK[it.level]}</span>
            <div>
              <span>
                <Rich text={it.text} />
              </span>
              <ActionButtons actions={it.actions} />
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}

export function CalibrationFiles({ view }: { view: HardwareView }) {
  const list = (kind: 'robots' | 'teleoperators') =>
    view.calibrations[kind].map((x) => `${x.class}/${x.id}`).join(', ') || 'none';
  return (
    <Card title="Calibration files">
      <div className="hint">
        <div>
          <b>robots: </b>
          <span className="mono">{list('robots')}</span>
        </div>
        <div>
          <b>teleoperators: </b>
          <span className="mono">{list('teleoperators')}</span>
        </div>
      </div>
    </Card>
  );
}
