import fs from 'node:fs';

/**
 * After the browser tests: the run fails if their server reached for the network. It refuses that
 * and writes what it refused to this log (tests/netguard.py), even when the code swallowed the refusal.
 */
export default function noNetwork(): void {
  const log = process.env.LEROBOT_GUI_E2E_NETWORK_LOG;
  if (!log) return;
  const reached = fs.existsSync(log) ? fs.readFileSync(log, 'utf8').trim() : '';
  fs.rmSync(log, { force: true });
  if (reached) throw new Error(`The browser tests' server reached for the network:\n${reached}`);
}
