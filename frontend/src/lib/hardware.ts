import type { CameraConfig } from '../api/types';
import { isSet } from './format';

// The arms' ports and boards are the server's: it sends the values to store with each choice
// (the field's `also`, the Hardware view's assign / confirm actions, Check arms' `remember`).

// ------------------------------------------------------------------ cameras

/** lerobot's camera settings that each frame's card (step 3) shows, when the type has them; the rest are in step 4. */
export const CARD_SETTINGS = ['fps', 'width', 'height'];

let made = 0;

/**
 * Each camera with an `id`, the key of its rows: the cameras are added, removed and renamed (a name moves to
 * another device with its settings), so neither the position nor the device stays with an entry.
 */
export const withIds = (configs: CameraConfig[]): CameraConfig[] =>
  configs.map((c) => (c.id ? c : { ...c, id: `cam-${Date.now().toString(36)}-${(made++).toString(36)}` }));

/** Whether the commands use a camera: an unchecked one keeps its name and settings but isn't written. */
export const isUsed = (c: CameraConfig): boolean => c.use !== false;

/** `c` with `use` set: checked is the default, so it is left out. */
const withUse = (c: CameraConfig, use: boolean | undefined): CameraConfig => {
  const { use: _, ...rest } = c;
  return use === false ? { ...rest, use: false } : rest;
};

/**
 * Check or uncheck the camera on `device`. Checking one without an entry makes it, unnamed, with
 * `type` (the lerobot camera type its frame was captured with). Unchecking only clears its name.
 */
export function checkCamera(configs: CameraConfig[], device: string, use: boolean, type?: string): CameraConfig[] {
  const here = configs.findIndex((c) => c.device === device);
  if (here < 0) return use ? [...configs, { name: '', ...(type ? { type } : {}), device }] : configs;
  return configs.map((c, i) => (i === here ? withUse(use ? c : { ...c, name: '' }, use) : c));
}

/** Change lerobot settings of the camera on `device` (an empty value removes one). */
export function setCameraSettings(configs: CameraConfig[], device: string, patch: Record<string, unknown>): CameraConfig[] {
  return configs.map((c) => {
    if (c.device !== device) return c;
    const settings = { ...(c.settings ?? {}) };
    for (const [k, v] of Object.entries(patch)) {
      if (isSet(v)) settings[k] = v;
      else delete settings[k];
    }
    return { ...c, settings };
  });
}

/** Forget the camera on `device`: its name and settings. */
export const forgetCamera = (configs: CameraConfig[], device: string): CameraConfig[] =>
  configs.filter((c) => c.device !== device);

/**
 * Give the camera on `device` the name `name`. A name already on another camera moves here with
 * its type and settings, and this camera's own name and settings go to that one's device (an
 * unnamed one without settings is dropped). Each device stays checked or unchecked as it was.
 */
export function nameCamera(configs: CameraConfig[], device: string, name: string, type?: string): CameraConfig[] {
  const cams = configs.map((c) => ({ ...c }));
  const here = cams.findIndex((c) => c.device === device);
  const taken = name ? cams.findIndex((c, i) => i !== here && c.name === name) : -1;
  if (taken >= 0) {
    const there = cams[taken]!;
    cams[taken] = withUse({ ...there, device }, here >= 0 ? cams[here]!.use : undefined);
    if (here >= 0) {
      const mine = cams[here]!;
      const keep = mine.name || Object.keys(mine.settings ?? {}).length;
      if (keep) cams[here] = withUse({ ...mine, device: there.device }, there.use);
      else cams.splice(here, 1);
    }
  } else if (here >= 0) {
    cams[here] = { ...cams[here]!, name };
  } else {
    cams.push({ name, ...(type ? { type } : {}), device });
  }
  return cams;
}
