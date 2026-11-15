import type { FormResponse, PageMeta } from '../api/types';
import { Rich } from '../lib/rich';
import { useStore } from '../lib/store';
import { toast } from '../state/app';
import { busyWith, jobs, run } from '../state/jobs';
import { Alerts } from './Alerts';
import { Icon } from './Icon';

async function copyText(text: string): Promise<void> {
  try {
    await navigator.clipboard.writeText(text);
    toast('Copied to clipboard');
  } catch {
    toast('Could not copy: select the command and copy it by hand');
  }
}

/** The command as it will run, highlighted: one `--flag=value` per line. */
export function Preview({ preview }: { preview: string }) {
  const [head, ...args] = preview.split(' \\\n    ');
  return (
    <pre className="preview">
      <span className="p-cmd">{head}</span>
      {args.map((a, i) => {
        const m = /^(--[^=\s]+=)([\s\S]*)$/.exec(a);
        return (
          <span key={i}>
            <span className="p-cont">{' \\\n    '}</span>
            {m ? (
              <>
                <span className="p-flag">{m[1]}</span>
                <span className="p-val">{m[2]}</span>
              </>
            ) : (
              <span className="p-val">{a}</span>
            )}
          </span>
        );
      })}
    </pre>
  );
}

/** Messages, the command preview and Run for a command page. */
export function CommandCard({ meta, form }: { meta: PageMeta; form: FormResponse | null }) {
  const entry = useStore(jobs, (s) => s.byPage[meta.id]);
  const busy = useStore(jobs, () => (meta.hardware ? busyWith(meta.id) : null));
  const running = !!entry?.info.running;
  const errors = form?.errors ?? 0;
  const busyTitle = busy ? `${busy.info.command} is using the robot` : '';
  const runForce = () => void run(meta.id, { force: true });
  return (
    <div className="stack" style={{ gap: 16 }}>
      {form && form.messages.length > 0 && <Alerts items={form.messages} ctx={{ runForce }} />}
      <div className="card">
        <div className="card-head">
          <div className="card-title">Command</div>
          <button
            className="btn ghost small"
            type="button"
            disabled={!form?.command}
            onClick={() => form?.command && void copyText(form.command.preview)}
          >
            <Icon name="copy" />
            Copy
          </button>
        </div>
        {form?.command ? <Preview preview={form.command.preview} /> : <pre className="preview muted">…</pre>}
        <div className="card-body" style={{ padding: '12px 16px', borderTop: '1px solid var(--border)' }}>
          <div className="run-bar">
            <button
              className="btn primary"
              type="button"
              disabled={!form || errors > 0 || running || !!busy}
              title={errors ? 'Fix the errors first' : running ? 'Already running' : busyTitle}
              onClick={() => void run(meta.id)}
            >
              <Icon name="rollout" />
              {running ? 'Running…' : 'Run'}
            </button>
            {busy ? (
              <span className="muted tiny">{busyTitle}.</span>
            ) : errors ? (
              <span className="muted tiny">
                {errors} error{errors > 1 ? 's' : ''} to fix
              </span>
            ) : null}
          </div>
        </div>
        {meta.hints.length > 0 && (
          <div className="hint" style={{ paddingTop: 0 }}>
            <ul>
              {meta.hints.map((t) => (
                <li key={t}>
                  <Rich text={t} />
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}
