import type { PageMeta } from '../api/types';
import { Card } from '../components/Card';
import { CommandCard } from '../components/CommandCard';
import { FieldGroups } from '../components/FieldGroups';
import { TerminalCard } from '../components/Terminal';
import { useForm } from '../hooks/useForm';
import { Rich } from '../lib/rich';
import { useStore } from '../lib/store';
import { app } from '../state/app';

/** Trackio: its dashboard (`trackio show`) for the runs logged here, and the Spaces they logged to. */
export function TrackioPage({ meta }: { meta: PageMeta }) {
  const form = useForm(meta.id);
  const spaces = useStore(app, (s) => s.discover?.local.trackio_spaces ?? []);
  return (
    <div className="content">
      <section className="form">
        {form ? <FieldGroups page={meta.id} groups={form.groups} /> : <div className="dev-empty">Loading…</div>}
        {spaces.length > 0 && (
          <Card title="Spaces">
            <div className="item-list">
              {spaces.map((id) => (
                <div key={id} className="item-row">
                  <a className="mono" href={`https://huggingface.co/spaces/${id}`} target="_blank" rel="noopener noreferrer">
                    {id}
                  </a>
                </div>
              ))}
            </div>
            <div className="hint">
              <Rich text="The Trackio Spaces of the training runs here (`--trackio.space_id`), on the Hugging Face Hub." />
            </div>
          </Card>
        )}
      </section>
      <section className="side">
        <CommandCard meta={meta} form={form} />
        <TerminalCard page={meta.id} />
      </section>
    </div>
  );
}
