import type { CameraConfig, CapturedImage, FieldSpec, HardwareView } from '../../api/types';
import { Card, StepTitle } from '../../components/Card';
import { Field } from '../../components/Field';
import { Icon } from '../../components/Icon';
import { SelectWithCustom } from '../../components/SelectWithCustom';
import { isSet } from '../../lib/format';
import { CARD_SETTINGS, isUsed, withIds } from '../../lib/hardware';
import { Rich } from '../../lib/rich';
import { setHardware } from '../../state/app';
import { useCameras } from './common';

function Mini({ label, flag, children }: { label: string; flag?: string; children: React.ReactNode }) {
  return (
    <div className="field">
      <div className="field-label">
        <span>{label}</span>
        {flag && <span className="flag">{flag}</span>}
      </div>
      {children}
    </div>
  );
}

/** Which device the camera opens: one in the last Find cameras frames, or typed. */
function DeviceControl({ devices, cam, label, setting, update }: {
  devices: string[];
  cam: CameraConfig;
  label: string;
  setting: string;
  update: (patch: Partial<CameraConfig>) => void;
}) {
  const device = cam.device ?? '';
  return (
    <Mini label="Device" flag={setting}>
      <SelectWithCustom
        value={device}
        options={devices.map((d) => ({ value: d, label: d, disabled: false, title: '' }))}
        empty={devices.includes(device) ? null : 'Select…'}
        onChange={(v) => update({ device: v ?? '' })}
        label={`${label} device`}
        customLabel={`${label} ${setting}`}
        typedOnly={!devices.length}
        mono
        unset={!device}
      />
    </Mini>
  );
}

function CameraRow({ view, devices, cam, framed, update, remove }: {
  view: HardwareView;
  devices: string[];
  cam: CameraConfig;
  /** it has a card in step 3, which has its name, fps, width and height */
  framed: boolean;
  update: (patch: Partial<CameraConfig>) => void;
  remove: () => void;
}) {
  const type = cam.type ?? '';
  const known = view.camera_types.includes(type);
  const deviceSetting = known ? view.camera_device_field[type] : null;
  // lerobot's settings of the type; the device setting is chosen above, the card's in step 3
  const fields: FieldSpec[] = known
    ? (view.camera_fields[type] ?? []).filter((f) => f.key !== deviceSetting && !(framed && CARD_SETTINGS.includes(f.key)))
    : [];
  const label = cam.name || cam.device || 'camera';
  const setSettings = (patch: Record<string, unknown>) => {
    const next = { ...(cam.settings ?? {}) };
    for (const [key, value] of Object.entries(patch)) {
      if (isSet(value)) next[key] = value;
      else delete next[key];
    }
    update({ settings: next });
  };
  return (
    <div className="cam">
      <div className="cam-top">
        <span className={`cam-title mono${cam.name ? '' : ' missing'}`} title={framed ? 'Named on its card in step 3' : undefined}>
          {cam.name || (framed ? 'no name yet (step 3)' : 'no name yet')}
        </span>
        {cam.device && <span className="muted tiny mono">{cam.device}</span>}
        {!framed && (
          <button className="icon-btn cam-remove" title="Remove" type="button" onClick={remove}>
            <Icon name="trash" />
          </button>
        )}
      </div>
      {/* every setting one cell of the same width: the name (here only for a camera added here), type, device, then lerobot's */}
      <div className="fields cam-fields">
        {!framed && (
          <Mini label="Name">
            <input
              className="input mono"
              aria-label="Camera name"
              value={cam.name}
              spellCheck={false}
              onChange={(e) => update({ name: e.target.value.trim() })}
            />
          </Mini>
        )}
        <Mini label="Type" flag="type">
          <select
            className={`input mono${type ? '' : ' unset'}`}
            aria-label={`${label} type`}
            value={type}
            onChange={(e) => update({ type: e.target.value || undefined })}
          >
            {!known && <option value={type}>{type ? `${type} (not in lerobot)` : 'Select…'}</option>}
            {view.camera_types.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        </Mini>
        {deviceSetting && <DeviceControl devices={devices} cam={cam} label={label} setting={deviceSetting} update={update} />}
        {fields.map((f) => (
          <Field key={f.key} page="hardware" field={f} stored={cam.settings ?? {}} onSet={setSettings} />
        ))}
      </div>
      {!known && <div className="muted tiny">Choose the camera type to see its settings.</div>}
    </div>
  );
}

/** Step 4: lerobot's settings of each camera used (the ones checked in step 3, and the ones added here). */
export function CameraSettingsCard({ view, images }: { view: HardwareView; images: CapturedImage[] }) {
  const cams = useCameras();
  const setCameras = (next: CameraConfig[]) => setHardware({ cameras: withIds(next) }, { keepCheck: true });
  // the devices in the last Find cameras frames
  const devices = [...new Set(images.map((img) => img.device))];
  const add = (
    <button
      className="btn ghost small"
      type="button"
      title="For a camera Find cameras doesn't list"
      onClick={() => setCameras([...cams, { name: `cam${cams.length + 1}` }])}
    >
      <Icon name="plus" />
      Add manually
    </button>
  );
  const shown = cams.map((cam, i) => ({ cam, i })).filter(({ cam }) => isUsed(cam));
  return (
    <Card id="camsettings-card" title={<StepTitle n={4}>Camera settings</StepTitle>} extra={add}>
      <div className="cam-list">
        {shown.map(({ cam, i }) => (
          <CameraRow
            key={cam.id ?? `at-${i}`}
            view={view}
            devices={devices}
            cam={cam}
            framed={isSet(cam.device) && devices.includes(String(cam.device))}
            update={(patch) => setCameras(cams.map((c, j) => (j === i ? { ...c, ...patch } : c)))}
            remove={() => setCameras(cams.filter((_, j) => j !== i))}
          />
        ))}
        {!shown.length && (
          <div className="dev-empty" style={{ padding: '4px 0 8px' }}>
            No cameras used yet: check them in step 3.
          </div>
        )}
      </div>
      <div className="hint">
        <Rich text="The type and its settings are lerobot's (`--robot.cameras`); an empty setting uses lerobot's default. A camera found in step 3 has its name, fps, width and height there. The devices offered are the ones in the last Find cameras frames." />
      </div>
    </Card>
  );
}
