import type { PageMeta } from '../api/types';
import { AllOptions } from '../components/AllOptions';
import { CommandCard } from '../components/CommandCard';
import { FieldGroups } from '../components/FieldGroups';
import { HardwareSummary } from '../components/HardwareSummary';
import { PresetCard } from '../components/PresetCard';
import { TerminalCard } from '../components/Terminal';
import { useForm } from '../hooks/useForm';

/** Calibrate, Teleoperate, Record, Train, Rollout: fields on the left, command and output on the right. */
export function CommandPage({ meta }: { meta: PageMeta }) {
  const form = useForm(meta.id);
  return (
    <div className="content">
      <section className="form">
        {meta.presets && <PresetCard page={meta.id} />}
        {form && (
          <>
            <HardwareSummary chips={form.hardware_summary} />
            <FieldGroups page={meta.id} groups={form.groups} />
            {meta.exe && form.options_query && <AllOptions page={meta.id} exe={meta.exe} query={form.options_query} />}
          </>
        )}
        {!form && <div className="dev-empty">Loading…</div>}
      </section>
      <section className="side">
        <CommandCard meta={meta} form={form} />
        <TerminalCard page={meta.id} />
      </section>
    </div>
  );
}
