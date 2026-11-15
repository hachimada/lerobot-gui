import { useCapturedImages } from '../hooks/useCapturedImages';
import { useHardwareForm } from '../hooks/useForm';
import { useStore } from '../lib/store';
import { app } from '../state/app';
import { ArmsCard } from './hardware/ArmsCard';
import { CameraSettingsCard } from './hardware/CameraSettingsCard';
import { CamerasFoundCard } from './hardware/CamerasFoundCard';
import { FindPortCard } from './hardware/FindPortCard';
import { CalibrationFiles, SetupStatus } from './hardware/SetupStatus';

/** The setup every command uses, in the order it is done: ports, arms, cameras, limits. */
export function HardwarePage() {
  const armCheck = useStore(app, (s) => s.armCheck.result);
  // empty: lerobot-find-cameras' default dir (the server resolves it)
  const dir = useStore(app, (s) => String(s.values['find-cameras']?.['output-dir'] ?? ''));
  const recordTime = useStore(app, (s) => String(s.values['find-cameras']?.['record-time-s'] ?? ''));
  const images = useCapturedImages(dir, recordTime);
  const form = useHardwareForm(armCheck);
  const view = form?.view;
  if (!form || !view) {
    return (
      <div className="content">
        <section className="form">
          <div className="dev-empty">Loading…</div>
        </section>
      </div>
    );
  }
  return (
    <div className="content">
      <section className="form">
        <FindPortCard view={view} />
        <ArmsCard groups={form.groups} view={view} />
        <CamerasFoundCard view={view} images={images} dir={dir} />
        <CameraSettingsCard view={view} images={images} />
      </section>
      <section className="side">
        <SetupStatus items={view.status} />
        <CalibrationFiles view={view} />
      </section>
    </div>
  );
}
