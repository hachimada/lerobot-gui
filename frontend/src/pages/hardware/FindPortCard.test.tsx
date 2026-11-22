import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it } from 'vitest';
import type { HardwareView, JobInfo } from '../../api/types';
import { attach } from '../../state/jobs';
import { mockApi, resetStores } from '../../test/utils';
import { FindPortCard } from './FindPortCard';

const VIEW = { ttys: [], roles: [] } as unknown as HardwareView;

const info = (patch: Partial<JobInfo> = {}): JobInfo => ({
  id: 'fp1',
  command: 'lerobot-find-port',
  page: 'find-port',
  args: [],
  hardware: false,
  started: Date.now() / 1000,
  ended: null,
  running: true,
  returncode: null,
  stop_requested: false,
  preflight: null,
  preflight_notes: [],
  failure: null,
  prompt: null,
  phase: null,
  find_port: null,
  ...patch,
});

beforeEach(() => resetStores());

describe('FindPortCard', () => {
  it('takes the Enter key for its Enter button once the arm is to be unplugged', async () => {
    const calls = mockApi({ 'POST /api/jobs/fp1/input': { ok: true } });
    const sent = () => calls.filter((c) => c.path === '/api/jobs/fp1/input').map((c) => c.body);
    act(() => attach(info()));
    render(<FindPortCard view={VIEW} />);
    // still reading the ports: the button is off, and so is the key
    expect(screen.getByRole('button', { name: 'Enter' })).toBeDisabled();
    fireEvent.keyDown(document.body, { key: 'Enter' });
    expect(sent()).toEqual([]);
    act(() => attach(info({ phase: 'unplug' })));
    expect(screen.getByRole('button', { name: 'Enter' })).toBeEnabled();
    expect(screen.getByRole('button', { name: 'Enter' })).toHaveAttribute('aria-keyshortcuts', 'Enter');
    fireEvent.keyDown(document.body, { key: 'Enter' });
    await waitFor(() => expect(sent()).toEqual([{ text: '' }]));
  });
});
