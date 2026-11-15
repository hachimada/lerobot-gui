// The shapes the Python API answers with. They are declared in src/lerobot_gui/schemas.py and generated into
// ./schema.ts (`npm run gen:api`); this file names them. Only the frontend's own shapes are written here.
import type { components } from './schema';

type S = components['schemas'];

export type Level = S['Message']['level'];
export type StatusLevel = S['StatusItem']['level'];

/** What a message's button does (go, set, check_arms, scroll, run_force). */
export type Action = S['Message']['actions'][number];
export type Message = S['Message'];
export type StatusItem = S['StatusItem'];

export type Option = S['Option'];
export type OptionGroup = S['OptionGroup'];
export type FieldKind = S['FieldSpec']['kind'];
export type FieldSpec = S['FieldSpec'];
export type GroupSpec = S['GroupSpec'];
export type OptionsQuery = S['OptionsQuery'];
export type FormResponse = S['FormResponse'];
export type OptionInfo = S['OptionInfo'];
export type OptionsListing = S['OptionsListing'];
export type PageMeta = S['PageMeta'];

export type Tty = S['Tty'];
export type Role = S['Role'];
export type ArmGuide = S['ArmGuide'];
export type ArmResult = S['ArmResult'];
export type ArmCheck = S['ArmCheck'];
export type Calibrations = S['Calibrations'];
export type HardwareView = S['HardwareView'];
export type HardwareForm = S['HardwareForm'];
export type Port = S['Port'];
export type Ports = S['Ports'];
export type Discover = S['Discover'];
export type CapturedImage = S['CapturedImage'];

export type CalibrationPrompt = S['CalibrationPrompt'];
export type JobInfo = S['JobInfo'];

export type Preset = S['Preset'];
export type PresetInfo = S['PresetInfo'];

export type AccountStatus = S['AccountStatus'];
export type AccountsResponse = S['Accounts'];
export type EnvironmentInfo = S['EnvironmentInfo'];

export type HfLocal = S['HfLocal'];
export type HubRepo = S['HubRepo'];
export type HfCloud = S['HfCloud'];
export type HubModel = S['HubModel'];
export type HubModels = S['HubModels'];

/**
 * A camera on the Hardware page: the GUI's own entry (name, type, the device lerobot-find-cameras
 * saved its frame from) and `settings`, lerobot's settings of that type as entered.
 */
export interface CameraConfig {
  /** the key in --robot.cameras ('' until named) */
  name: string;
  /** the entry's key in the GUI's lists (not written into the commands) */
  id?: string;
  type?: string;
  device?: string;
  /** false: unchecked, not written; its settings are kept (absent: used) */
  use?: boolean;
  settings?: Record<string, unknown>;
}

/** What /api/hf/local/delete takes: one item of the listing. */
export type HfLocalItem =
  | { kind: 'dataset'; repo_id: string }
  | { kind: 'calibration'; calibration_kind: string; cls: string; id: string }
  | { kind: 'cache'; cache: string; repo_type: string; repo_id: string };
