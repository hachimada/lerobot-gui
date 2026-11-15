import { apiUrl } from '../../api/client';
import type { CameraConfig, CapturedImage, HardwareView } from '../../api/types';
import { emptyText } from '../../components/Field';
import { Menu } from '../../components/Menu';
import { ago } from '../../lib/format';
import { CARD_SETTINGS, checkCamera, isUsed, setCameraSettings } from '../../lib/hardware';

/** The lerobot camera type a frame was captured with, when the installed lerobot has it. */
export const knownType = (view: HardwareView, type: string | null | undefined) =>
  type && view.camera_types.includes(type) ? type : undefined;

/**
 * One frame of Find cameras: check the camera to use it, name it (a name the datasets and training runs here use is
 * offered), and set lerobot's fps, width and height of it.
 */
export function CameraFrameRow({ img, dir, view, cameras, running, setCameras, name, remove }: {
  img: CapturedImage;
  dir: string;
  view: HardwareView;
  /** the Hardware page's cameras */
  cameras: CameraConfig[];
  /** Find cameras is running (its frames can't be deleted) */
  running: boolean;
  setCameras: (cams: CameraConfig[]) => void;
  /** give the camera on `device` this name (moving it, with its settings, from another camera) */
  name: (device: string, value: string) => void;
  remove: (file: string, device: string) => void;
}) {
  const suggestions = view.camera_names;
  const path = img.device;
  const src = apiUrl(`/captured-images/${encodeURIComponent(img.name)}`, { dir, v: img.mtime });
  const cfg = cameras.find((c) => c.device === path);
  const on = !!cfg && isUsed(cfg);
  const type = cfg ? (cfg.type ?? '') : (knownType(view, img.type) ?? '');
  // lerobot's settings of the type that this card shows; the others are in step 4
  const quick = (view.camera_fields?.[type] ?? []).filter((f) => CARD_SETTINGS.includes(f.key));
  const sized = !!img.width && !!img.height;
  const sameSize = String(cfg?.settings?.width ?? '') === String(img.width) && String(cfg?.settings?.height ?? '') === String(img.height);
  const set = (patch: Record<string, unknown>) => setCameras(setCameraSettings(cameras, path, patch));
  return (
    <div className={`camrow${on ? ' on' : ''}`}>
      <div className="camrow-menu">
        <Menu
          label={`More for ${path}`}
          items={[
            {
              label: 'Delete',
              icon: 'trash',
              danger: true,
              disabled: running,
              onSelect: () => remove(img.name, path),
            },
          ]}
        />
      </div>
      <div className="cam-pic">
        <a href={src} target="_blank" rel="noopener noreferrer" title="Open full size">
          <img className="cam-thumb" src={src} alt={`Frame from ${path}`} loading="lazy" />
        </a>
        <label className="cam-use" title={on ? 'Used by the commands: uncheck to leave it out (its name is cleared, its settings kept)' : 'Use this camera in the commands'}>
          <input
            type="checkbox"
            aria-label={`Use ${path}`}
            checked={on}
            onChange={(e) => setCameras(checkCamera(cameras, path, e.target.checked, knownType(view, img.type)))}
          />
        </label>
      </div>
      <div className="camrow-info">
        <div>
          <span className="mono" style={{ fontWeight: 600 }}>
            {path}
          </span>
          {img.type && <span className="muted tiny">{`  ${img.type}`}</span>}
        </div>
        <div className="cam-meta muted tiny">
          <span>{`frame ${ago(img.mtime)}`}</span>
          {sized && <span>{`${img.width}×${img.height}`}</span>}
          {img.older && (
            <span className="cam-tag" title="Not updated by the last run">
              older run
            </span>
          )}
        </div>
        <div className="cam-sets">
          <label className="cam-set">
            <span className="muted tiny">Name</span>
            <input
              key={cfg?.name ?? ''}
              className={`input mono cam-name-input${on && !cfg?.name ? ' missing' : ''}`}
              aria-label={`Name of ${path}`}
              defaultValue={cfg?.name ?? ''}
              spellCheck={false}
              disabled={!on}
              placeholder={on ? 'needs a name' : ''}
              title={on ? 'The camera’s name in the commands (Enter to save)' : 'Check the camera to use it'}
              onBlur={(e) => e.target.value.trim() !== (cfg?.name ?? '') && name(path, e.target.value.trim())}
              onKeyDown={(e) => e.key === 'Enter' && e.currentTarget.blur()}
            />
          </label>
        </div>
        {on && suggestions.some((n) => n !== cfg?.name) && (
          <div className="cam-suggest">
            <span className="muted tiny" title="The camera names of the datasets and training runs on this computer">
              used before:
            </span>
            {suggestions
              .filter((n) => n !== cfg?.name)
              .map((n) => (
                <button
                  key={n}
                  className="chip-btn"
                  type="button"
                  title={`${cameras.some((c) => c.name === n) ? `Move the name ${n} and its settings to this camera` : `Name this camera ${n}`} (a name your datasets or training runs use)`}
                  onClick={() => name(path, n)}
                >
                  {n}
                </button>
              ))}
          </div>
        )}
        {quick.length > 0 && (
          <div className="cam-sets">
            {quick.map((f) => (
              <label key={f.key} className="cam-set" title={f.help ?? undefined}>
                <span className="muted tiny">{f.key}</span>
                <input
                  className="input mono cam-num"
                  type={f.kind === 'number' ? 'number' : 'text'}
                  step={f.kind === 'number' ? 'any' : undefined}
                  aria-label={`${f.key} of ${path}`}
                  value={String(cfg?.settings?.[f.key] ?? '')}
                  placeholder={emptyText(f)}
                  disabled={!on}
                  onChange={(e) => set({ [f.key]: e.target.value })}
                />
              </label>
            ))}
            {on && sized && !sameSize && quick.some((f) => f.key === 'width') && quick.some((f) => f.key === 'height') && (
              <span className="cam-suggest">
                <span className="muted tiny">frame size:</span>
                <button
                  className="chip-btn"
                  type="button"
                  title="Set width and height to the size of this frame"
                  onClick={() => set({ width: String(img.width), height: String(img.height) })}
                >
                  {`${img.width}×${img.height}`}
                </button>
              </span>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
