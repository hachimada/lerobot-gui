/// <reference types="vitest/config" />
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

// The Python package serves the build from src/lerobot_gui/web (see lerobot_gui/app.py).
// `npm run dev` proxies /api to a running `lerobot-gui`; start it with LEROBOT_GUI_TOKEN set to the
// same value as here so the proxy can authenticate (the dev page has no token of its own).
const backend = process.env.LEROBOT_GUI_URL ?? 'http://127.0.0.1:7878';
const token = process.env.LEROBOT_GUI_TOKEN ?? '';

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: '../src/lerobot_gui/web',
    emptyOutDir: true,
    // the licenses of the npm packages bundled, to .vite/license.md: the wheel ships them (THIRD_PARTY_NOTICES.md)
    license: true,
  },
  server: {
    proxy: {
      '/api': { target: backend, changeOrigin: true, headers: token ? { 'X-Token': token } : {} },
    },
  },
  test: {
    environment: 'jsdom',
    include: ['src/**/*.test.{ts,tsx}'],
    setupFiles: ['./src/test-setup.ts'],
    restoreMocks: true,
  },
});
