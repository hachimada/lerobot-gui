import { api } from '../../api/client';
import type { CameraConfig, CapturedImage, HardwareView } from '../../api/types';
import { Alerts } from '../../components/Alerts';
import { Card, StepTitle } from '../../components/Card';
import { Field } from '../../components/Field';
import { Icon } from '../../components/Icon';
import { TermView } from '../../components/Terminal';
import { useForm } from '../../hooks/useForm';
import { forgetCamera, nameCamera, withIds } from '../../lib/hardware';
import { Rich } from '../../lib/rich';
import { useStore } from '../../lib/store';
import { app, setHardware, toast } from '../../state/app';
import { busyWith, jobs, refreshCaptured, run, signal } from '../../state/jobs';
import { CameraFrameRow } from './CameraFrameRow';
import { useCameras } from './common';
import { Folding } from './Folding';

/** Step 3: one frame from each camera (lerobot-find-cameras); check the ones to use and name them. */
export function CamerasFoundCard({ view, images, dir }: { view: HardwareView; images: CapturedImage[]; dir: string }) {
  const fc = useForm('find-cameras');
  const stored = useStore(app, (s) => s.values['find-cameras']);
  const entry = useStore(jobs, (s) => s.byPage['find-cameras']);
  const busy = useStore(jobs, () => busyWith('find-cameras'));
  const cameras = useCameras();
  const running = !!entry?.info.running;

  const setCameras = (cams: CameraConfig[]) => setHardware({ cameras: withIds(cams) }, { keepCheck: true });
  /** Delete a camera from the list: its frame file, and its name and settings. */
  const removeCamera = async (file: string, device: string) => {
    const cfg = cameras.find((c) => c.device === device);
    const kept = cfg && (cfg.name || Object.keys(cfg.settings ?? {}).length);
    const question = kept
      ? `Delete the frame of ${device} (${file})? Its name${cfg.name ? ` (${cfg.name})` : ''} and settings are removed too.`
      : `Delete the frame of ${device} (${file})?`;
    if (!window.confirm(question)) return;
    try {
      await api.deleteCapturedImage(file, dir);
    } catch (e) {
      toast((e as Error).message);
      return;
    }
    if (cfg) setCameras(forgetCamera(cameras, device));
    refreshCaptured();
    toast(`Deleted ${file}`);
  };
  const name = (device: string, value: string) => {
    setCameras(nameCamera(cameras, device, value));
    if (value) toast(`${value} → ${device}`);
  };

  const head = running ? (
    <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
      <span className="pill running">Capturing</span>
      <button className="btn ghost small" type="button" onClick={() => void signal('find-cameras', 'INT')}>
        Cancel
      </button>
    </div>
  ) : (
    <button
      className="btn primary small"
      type="button"
      disabled={!!busy || !!fc?.errors}
      title={busy ? `${busy.info.command} is using the robot` : 'Save one frame from each camera'}
      onClick={() => void run('find-cameras')}
    >
      <Icon name="camera" />
      Find cameras
    </button>
  );
  const failed = entry && !running && entry.info.failure;

  return (
    <Card id="cameras-card" title={<StepTitle n={3}>Find cameras</StepTitle>} extra={head}>
      {running && (
        <div className="card-body" style={{ padding: '10px 16px 0' }}>
          <div className="muted tiny">Capturing a frame from each camera…</div>
        </div>
      )}
      {failed && (
        <div className="card-body" style={{ padding: '10px 16px 0' }}>
          <Alerts items={[{ level: 'err', text: entry.info.failure ?? '' }]} />
        </div>
      )}
      <div className="card-body flush">
        {images.length ? (
          <div className="camrows">
            {images.map((img) => (
              <CameraFrameRow
                key={img.name}
                img={img}
                dir={dir}
                view={view}
                cameras={cameras}
                running={running}
                setCameras={setCameras}
                name={name}
                remove={(file, device) => void removeCamera(file, device)}
              />
            ))}
          </div>
        ) : (
          <div className="dev-empty">No cameras found.</div>
        )}
      </div>
      <div className="hint">
        <Rich
          text="Saves one frame per camera (`lerobot-find-cameras`). Check the cameras to use and name each one; unchecking one clears its name and leaves it out. The names offered are the ones the datasets and training runs on this computer use (`observation.images.<name>`), so a camera matches them. fps, width and height are lerobot's settings of the camera (empty: lerobot's default); the others are in step 4. After replugging cameras, run it again and check the names: their numbers can change."
        />
      </div>
      {fc && (
        <Folding id="hardware:fc-opts" title="Options">
          <div className="card-body">
            {fc.messages.length > 0 && <Alerts items={fc.messages} />}
            <div className="fields">
              {fc.groups.flatMap((g) => g.fields).map((f) => (
                <Field key={f.key} page="find-cameras" field={f} stored={stored} />
              ))}
            </div>
          </div>
        </Folding>
      )}
      {entry && (
        <Folding id="hardware:fc-out" title="Output">
          <TermView term={entry.term} />
        </Folding>
      )}
    </Card>
  );
}
