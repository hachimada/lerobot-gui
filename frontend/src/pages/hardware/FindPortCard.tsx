import type { HardwareView, Role } from '../../api/types';
import { Alerts } from '../../components/Alerts';
import { Card, StepTitle } from '../../components/Card';
import { Icon } from '../../components/Icon';
import { TermView } from '../../components/Terminal';
import { useEnterKey } from '../../hooks/useEnterKey';
import { basename, clock } from '../../lib/format';
import { Rich } from '../../lib/rich';
import { useStore } from '../../lib/store';
import { runAction } from '../../state/app';
import { busyWith, dismiss, input, jobs, run, signal, type JobEntry } from '../../state/jobs';
import { Folding } from './Folding';

type FindPortState = 'idle' | 'scan' | 'unplug' | 'done' | 'error';

export function findPortState(entry: JobEntry | undefined): FindPortState {
  const info = entry?.info;
  if (!info) return 'idle';
  if (info.running) return info.phase === 'unplug' ? 'unplug' : 'scan';
  if (info.find_port) return 'done';
  if (info.failure) return 'error';
  return 'idle';
}

function Step({ n, text, active }: { n: number; text: string; active: boolean }) {
  return (
    <div className={`fp-step${active ? ' active' : ''}`}>
      <span className="fp-num">{n}</span>
      <span>
        <Rich text={text} />
      </span>
    </div>
  );
}

/** Step 1: which port an arm is on (lerobot-find-port, driven with buttons). */
export function FindPortCard({ view }: { view: HardwareView }) {
  const entry = useStore(jobs, (s) => s.byPage['find-port']);
  const busy = useStore(jobs, () => busyWith('find-port'));
  const st = findPortState(entry);
  useEnterKey(st === 'unplug', () => void input('find-port', ''));
  const start = (label: string) => (
    <button
      className="btn primary small"
      type="button"
      disabled={!!busy}
      title={busy ? `${busy.info.command} is using the robot` : ''}
      onClick={() => void run('find-port')}
    >
      <Icon name="port" />
      {label}
    </button>
  );

  let body;
  if (st === 'scan' || st === 'unplug') {
    body = (
      <>
        <Step n={1} text={st === 'scan' ? 'Reading the ports…' : 'Unplug the USB cable of one arm (only one).'} active={st === 'unplug'} />
        <Step n={2} text="Click Enter (or press the Enter key)." active={false} />
        <div className="run-bar" style={{ marginTop: 12 }}>
          <button
            className="btn primary small"
            type="button"
            disabled={st !== 'unplug'}
            title="Or press the Enter key"
            aria-keyshortcuts="Enter"
            onClick={() => void input('find-port', '')}
          >
            <Icon name="enter" />
            Enter
          </button>
          <button className="btn ghost small" type="button" onClick={() => void signal('find-port', 'INT')}>
            Cancel
          </button>
        </div>
      </>
    );
  } else if (st === 'done' && entry?.info.find_port) {
    const r = entry.info.find_port;
    // its port now that it is plugged back in, found by its board (the number can differ from the one it had)
    const row = r.by_id ? view.ttys.find((t) => t.board === r.by_id) : view.ttys.find((t) => t.tty === r.tty);
    const now = row?.tty ?? null;
    // the board's serial as the server read it (its by-id name while it isn't back yet)
    const serial = r.by_id ? (row?.serial ?? basename(r.by_id)) : null;
    const assign = ({ name }: Role) => {
      const here = !!row?.roles.includes(name);
      // none while it isn't plugged back in, or when the arm is on it already
      const action = row?.assign[name];
      return (
        <button
          key={name}
          className={`btn ${here ? 'ghost' : 'primary'} small`}
          type="button"
          disabled={!action}
          onClick={() => action && runAction(action)}
        >
          {here ? `${name} ✓` : `Use as ${name}`}
        </button>
      );
    };
    const note = !r.by_id
      ? "This board has no serial number, so a renumbering after replugging can't be detected: run Find port again after replugging."
      : !now
        ? `Board ${serial}.`
        : now === r.tty
          ? `Board ${serial}. It is remembered, so a later renumbering is caught.`
          : `Board ${serial}: it was \`${r.tty}\` when unplugged and came back as \`${now}\`.`;
    body = (
      <>
        <div className="muted tiny">The arm you unplugged at {clock(entry.info.ended ?? entry.info.started)}</div>
        <div className="mono" style={{ fontSize: 14, fontWeight: 600, margin: '3px 0 4px' }}>
          {now ?? r.tty}
        </div>
        <div className="muted tiny">
          <Rich text={note} />
        </div>
        {!now && (
          <div className="muted tiny" style={{ marginTop: 4, color: 'var(--warn)' }}>
            Plug it back in to assign it.
          </div>
        )}
        <div className="run-bar" style={{ marginTop: 12, flexWrap: 'wrap' }}>
          {view.roles.map(assign)}
          <button className="btn ghost small" type="button" disabled={!!busy} onClick={() => void run('find-port')}>
            Find another
          </button>
        </div>
      </>
    );
  } else if (st === 'error' && entry) {
    body = (
      <>
        <Alerts items={[{ level: 'err', text: entry.info.failure ?? '' }]} />
        <div className="muted tiny" style={{ margin: '8px 0 10px' }}>
          Run at {clock(entry.info.started)}.
        </div>
        <div className="run-bar">
          {start('Try again')}
          <button className="btn ghost small" type="button" onClick={() => dismiss('find-port')}>
            Dismiss
          </button>
        </div>
      </>
    );
  } else {
    body = (
      <>
        <div className="muted" style={{ fontSize: 12.5 }}>
          <Rich text="Tells which port an arm is on: start it, unplug that arm's USB when asked, and click Enter. You get its port as lerobot names it, ready to assign." />
        </div>
        <div className="run-bar" style={{ marginTop: 12 }}>
          {start('Find port')}
          {busy && <span className="muted tiny">{busy.info.command} is using the robot.</span>}
        </div>
      </>
    );
  }
  return (
    <Card
      id="findport-card"
      title={<StepTitle n={1}>Find port</StepTitle>}
      extra={st === 'scan' || st === 'unplug' ? <span className="pill running">Running</span> : null}
    >
      <div className="card-body" style={{ padding: '14px 16px' }}>
        {body}
      </div>
      {entry && (
        <Folding id="hardware:fp-out" title="Output">
          <TermView term={entry.term} />
        </Folding>
      )}
    </Card>
  );
}
