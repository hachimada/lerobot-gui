import os from 'node:os';
import path from 'node:path';
import { defineConfig } from '@playwright/test';

// Browser tests against the real server on a fake machine (tests/e2e/serve.py) and the built
// frontend: run `npm run e2e`. PW_CHANNEL=chrome uses the installed Google Chrome instead of
// Playwright's own Chromium (`npx playwright install chromium`).
const port = Number(process.env.E2E_PORT ?? 7899);
const python = process.env.PYTHON ?? '.venv/bin/python';
// where the server writes what it refused to reach on the network; checked at the end (e2e/no-network.ts).
// Set once by the runner: the workers load this file too and keep the runner's value.
process.env.LEROBOT_GUI_E2E_NETWORK_LOG ??= path.join(os.tmpdir(), `lerobot-gui-e2e-network-${process.pid}.log`);

export default defineConfig({
  testDir: './e2e',
  timeout: 30_000,
  fullyParallel: false,
  workers: 1, // one server: jobs and values are shared
  reporter: process.env.CI ? 'github' : 'list',
  globalTeardown: './e2e/no-network.ts',
  use: {
    baseURL: `http://127.0.0.1:${port}`,
    channel: process.env.PW_CHANNEL || undefined,
    trace: 'retain-on-failure',
  },
  webServer: {
    command: `${python} -m tests.e2e.serve --port ${port}`,
    cwd: '..',
    url: `http://127.0.0.1:${port}/`,
    reuseExistingServer: false,
    // the server imports lerobot before it listens (tests/e2e/serve.py): slow on a fresh CI runner
    timeout: 180_000,
  },
});
