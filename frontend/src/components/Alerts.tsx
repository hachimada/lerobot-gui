import type { Action, Level } from '../api/types';
import { Rich } from '../lib/rich';
import { runAction, type ActionContext } from '../state/app';
import { Icon } from './Icon';

export interface AlertItem {
  level: Level;
  text: string;
  actions?: Action[];
}

export function ActionButtons({ actions, ctx }: { actions?: Action[]; ctx?: ActionContext }) {
  if (!actions?.length) return null;
  return (
    <div className="alert-actions">
      {actions.map((a, i) => (
        <button key={i} className="btn link" type="button" onClick={() => runAction(a, ctx)}>
          {a.label}
        </button>
      ))}
    </div>
  );
}

export function Alerts({ items, ctx }: { items: AlertItem[]; ctx?: ActionContext }) {
  if (!items.length) return null;
  const order = { err: 0, warn: 1, info: 2 };
  return (
    <div className="alerts">
      {[...items]
        .sort((a, b) => order[a.level] - order[b.level])
        .map((m, i) => (
          <div key={i} className={`alert ${m.level}`} role={m.level === 'err' ? 'alert' : undefined}>
            <Icon name={m.level} />
            <div className="alert-body">
              <div>
                <Rich text={m.text} />
              </div>
              <ActionButtons actions={m.actions} ctx={ctx} />
            </div>
          </div>
        ))}
    </div>
  );
}
