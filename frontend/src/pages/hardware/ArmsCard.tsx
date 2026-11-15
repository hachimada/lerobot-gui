import { Fragment } from 'react';
import type { ArmResult, GroupSpec, HardwareView } from '../../api/types';
import { ActionButtons, Alerts } from '../../components/Alerts';
import { Card, StepTitle } from '../../components/Card';
import { Field } from '../../components/Field';
import { basename, cap, clock } from '../../lib/format';
import { Rich } from '../../lib/rich';
import { useStore } from '../../lib/store';
import { app, checkArms, runAction, setHardware } from '../../state/app';

const MARK = { ok: '✓', warn: '!', err: '✕' } as const;

function ArmResultRow({ arm }: { arm: ArmResult }) {
  const g = arm.guide;
  if (!g) return null;
  return (
    <div className="arm-result">
      <div className="arm-result-head">
        <span className={`status-icon ${g.level}`}>{MARK[g.level]}</span>
        <b>
          {cap(arm.role)} on {basename(arm.port)}
        </b>
        <span className={`pill ${g.level === 'ok' ? 'ok' : g.level === 'err' ? 'fail' : ''}`}>{g.title}</span>
      </div>
      <div className="arm-result-text">
        <Rich text={g.text} />
      </div>
      {g.steps && (
        <ol className="arm-steps">
          {g.steps.map((t) => (
            <li key={t}>
              <Rich text={t} />
            </li>
          ))}
        </ol>
      )}
      {g.actions && (
        <div className="arm-actions">
          <ActionButtons actions={g.actions} />
        </div>
      )}
    </div>
  );
}

/** Step 2: the port and calibration id of each arm, what is plugged in, and Check arms. */
export function ArmsCard({ groups, view }: { groups: GroupSpec[]; view: HardwareView }) {
  const stored = useStore(app, (s) => s.values.hardware);
  const armCheck = useStore(app, (s) => s.armCheck);
  const result = view.arm_check;
  return (
    <Card id="arms-card" title={<StepTitle n={2}>Follower &amp; leader</StepTitle>}>
      <div className="card-body">
        {/* a group per arm: its port and id */}
        {groups.map((g) => (
          <Fragment key={g.title}>
            <div className="sub-title">{g.title}</div>
            <div className="fields">
              {g.fields.map((f) => (
                <Field key={f.key} page="hardware" field={f} stored={stored} onSet={setHardware} />
              ))}
            </div>
          </Fragment>
        ))}
      </div>
      <div className="sub-head">
        <div className="sub-title" style={{ margin: 0 }}>
          Plugged in now
        </div>
        <div className="muted tiny">One port per arm (its USB motor board). Updates by itself when something is plugged or unplugged.</div>
      </div>
      <div className="card-body flush">
        {view.ttys.length ? (
          <table className="dev-table">
            <tbody>
              {view.ttys.map((t) => (
                <tr key={t.tty}>
                  <td>
                    <div className="mono" style={{ fontWeight: 600 }}>
                      {t.tty}
                    </div>
                    <div className="muted tiny">{t.serial ? `board ${t.serial}` : 'no board serial'}</div>
                  </td>
                  <td style={{ textAlign: 'right', whiteSpace: 'nowrap' }}>
                    {view.roles.map(({ name, label }) => {
                      const assign = t.assign[name];
                      return assign ? (
                        <button key={name} className="btn ghost small" style={{ marginLeft: 6 }} onClick={() => runAction(assign)}>
                          {label}
                        </button>
                      ) : (
                        <span key={name} className="pill ok" style={{ marginLeft: 6 }}>
                          {name}
                        </span>
                      );
                    })}
                    {Object.entries(t.confirm).map(([name, confirm]) => (
                      <div key={name}>
                        <button
                          className="btn link"
                          type="button"
                          style={{ fontSize: 12 }}
                          title={`Remember that board ${t.serial} is the ${name}`}
                          onClick={() => runAction(confirm)}
                        >
                          {confirm.label}
                        </button>
                      </div>
                    ))}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div className="dev-empty">Nothing plugged in. Is the arm connected by USB and powered?</div>
        )}
      </div>
      <div className="sub-head">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
          <div className="sub-title" style={{ margin: 0 }}>
            Check arms
          </div>
          <button className="btn ghost small" type="button" disabled={armCheck.loading} onClick={() => void checkArms()}>
            {armCheck.loading ? 'Checking…' : armCheck.result ? 'Check again' : 'Check arms'}
          </button>
        </div>
        <div className="muted tiny">{view.arm_explain}</div>
      </div>
      {armCheck.error && (
        <div className="card-body">
          <Alerts items={[{ level: 'err', text: armCheck.error }]} />
        </div>
      )}
      {result && (
        <div className="arm-check">
          <div className="muted tiny" style={{ padding: '8px 16px 0' }}>
            Checked at {clock(armCheck.at)}
          </div>
          {result.arms.map((a) => (
            <ArmResultRow key={a.role} arm={a} />
          ))}
        </div>
      )}
    </Card>
  );
}
