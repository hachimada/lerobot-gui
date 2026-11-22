import { useEffect, useLayoutEffect, useMemo, useRef, useState, useSyncExternalStore } from 'react';
import type { JobInfo } from '../api/types';
import { confirmWriteText } from '../lib/calibration';
import { fmtDuration } from '../lib/format';
import { withLinks } from '../lib/rich';
import { useStore } from '../lib/store';
import type { Term } from '../lib/term';
import { useEnterKey } from '../hooks/useEnterKey';
import { useNow } from '../hooks/useInterval';
import { input, jobs, signal } from '../state/jobs';
import { Alerts, type AlertItem } from './Alerts';
import { Icon } from './Icon';

/** The output of a job, kept scrolled to the bottom unless the user scrolled up; its web addresses are links. */
export function TermView({ term }: { term: Term | null }) {
  const pre = useRef<HTMLPreElement>(null);
  const version = useSyncExternalStore(
    (l) => term?.subscribe(l) ?? (() => {}),
    () => term?.version ?? 0,
  );
  const [text, setText] = useState('');
  // repaint at most once a frame: lerobot redraws its tables many times a second
  useEffect(() => {
    const id = requestAnimationFrame(() => setText(term ? term.text : ''));
    return () => cancelAnimationFrame(id);
  }, [term, version]);
  const shown = useMemo(() => (text.trim() ? withLinks(text) : ''), [text]);
  const stick = useRef(true);
  useLayoutEffect(() => {
    const el = pre.current;
    if (el && stick.current) el.scrollTop = el.scrollHeight;
  }, [text]);
  return (
    <pre
      ref={pre}
      className="term-out"
      onScroll={(e) => {
        const el = e.currentTarget;
        stick.current = el.scrollHeight - el.scrollTop - el.clientHeight < 48;
      }}
    >
      {shown}
    </pre>
  );
}

export function StatusPill({ info }: { info: JobInfo | undefined }) {
  const now = useNow(1000, !!info?.running);
  if (!info) return <span className="pill">Idle</span>;
  if (info.running) return <span className="pill running">Running · {fmtDuration(now - info.started)}</span>;
  const took = info.ended ? ` · ${fmtDuration(info.ended - info.started)}` : '';
  if (info.returncode === 0) return <span className="pill ok">Finished{took}</span>;
  if (info.stop_requested && [130, -2, -15, -9, 143].includes(info.returncode ?? 0)) {
    return <span className="pill">Stopped{took}</span>;
  }
  return (
    <span className="pill fail">
      Exit {info.returncode}
      {took}
    </span>
  );
}

/** Output, Stop and the input line for the page's job. */
export function TerminalCard({ page }: { page: string }) {
  const entry = useStore(jobs, (s) => s.byPage[page]);
  const info = entry?.info;
  const running = !!info?.running;
  const prompt = info?.prompt ?? null;
  const [text, setText] = useState('');
  const risky = !!prompt?.mismatch && page !== 'calibrate';

  const send = (value: string) => {
    if (
      risky &&
      value.trim().toLowerCase() !== 'c' &&
      !window.confirm(confirmWriteText(prompt))
    ) {
      return;
    }
    void input(page, value);
  };
  useEnterKey(running, () => send(''));

  const notes: AlertItem[] = [];
  if (prompt?.warning) notes.push({ level: 'err', text: prompt.warning });
  for (const n of info?.preflight_notes ?? []) notes.push(n);

  return (
    <div className="card term" id="term-card">
      <div className="card-head">
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, minWidth: 0 }}>
          <div className="card-title">Output</div>
          <StatusPill info={info} />
        </div>
        <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
          {running && info?.stop_requested && (
            <button className="btn ghost small" type="button" title="Send SIGKILL" onClick={() => void signal(page, 'KILL')}>
              Force kill
            </button>
          )}
          {running && (
            <button className="btn danger small" type="button" title="Send Ctrl+C (SIGINT)" onClick={() => void signal(page, 'INT')}>
              <Icon name="stop" />
              Stop
            </button>
          )}
          <button className="icon-btn" type="button" title="Clear output" onClick={() => entry?.term.reset()}>
            <Icon name="clear" />
          </button>
        </div>
      </div>
      {notes.length > 0 && (
        <div className="term-note">
          <Alerts items={notes} />
        </div>
      )}
      <TermView term={entry?.term ?? null} />
      <div className="term-input">
        <input
          className="input mono"
          aria-label="Input for the process"
          placeholder={running ? 'Type input for the process…' : 'Input is enabled while a command runs'}
          disabled={!running}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              send(text);
              setText('');
            }
          }}
        />
        <button
          className="btn ghost small"
          type="button"
          disabled={!running}
          onClick={() => {
            send(text);
            setText('');
          }}
        >
          Send
        </button>
        <button
          className="btn ghost small"
          type="button"
          disabled={!running}
          title="Send an empty line (Enter key)"
          aria-keyshortcuts="Enter"
          onClick={() => send('')}
        >
          <Icon name="enter" />
          Enter
        </button>
      </div>
    </div>
  );
}
