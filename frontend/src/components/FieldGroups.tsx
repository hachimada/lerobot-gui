import type { GroupSpec } from '../api/types';
import { useStore } from '../lib/store';
import { app, toggleOpen } from '../state/app';
import { Card } from './Card';
import { Field } from './Field';

/** A page's field groups as cards, the advanced fields of each folded away. */
export function FieldGroups({ page, groups }: { page: string; groups: GroupSpec[] }) {
  const stored = useStore(app, (s) => s.values[page]);
  const openAdv = useStore(app, (s) => s.openAdv);
  return (
    <>
      {groups.map((g) => {
        const main = g.fields.filter((f) => !f.advanced);
        const adv = g.fields.filter((f) => f.advanced);
        const key = `${page}:${g.title}`;
        return (
          <Card key={g.title} title={g.title}>
            <div className="card-body">
              <div className="fields">
                {main.map((f) => (
                  <Field key={f.key} page={page} field={f} stored={stored} />
                ))}
              </div>
              {adv.length > 0 && (
                <details
                  className="adv"
                  open={openAdv.includes(key)}
                  onToggle={(e) => toggleOpen(key, (e.currentTarget as HTMLDetailsElement).open)}
                >
                  <summary>Advanced · {adv.length}</summary>
                  <div className="fields">
                    {adv.map((f) => (
                      <Field key={f.key} page={page} field={f} stored={stored} />
                    ))}
                  </div>
                </details>
              )}
            </div>
          </Card>
        );
      })}
    </>
  );
}
