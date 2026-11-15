import type { CalibrationPrompt } from '../api/types';
import { basename } from './format';

/** The question before Enter writes a calibration file that lerobot says the motors don't hold. */
export function confirmWriteText(prompt: CalibrationPrompt | null): string {
  const where = prompt?.port ? ` on ${basename(prompt.port)}` : '';
  const which = prompt?.role ? `that port really is the ${prompt.role}` : 'it really is that arm';
  return (
    `Write ${prompt?.id || 'the calibration file'} into the motors${where}?\n\n` +
    `Only if ${which}. If the ports may be swapped, cancel and press Stop.`
  );
}
