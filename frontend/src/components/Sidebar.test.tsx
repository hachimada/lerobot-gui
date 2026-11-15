import { act, render, screen, within } from '@testing-library/react';
import { beforeEach, describe, expect, it } from 'vitest';
import type { JobInfo } from '../api/types';
import { app } from '../state/app';
import { attach } from '../state/jobs';
import { PAGES, resetStores } from '../test/utils';
import { Sidebar } from './Sidebar';

const job = (page: string, command: string): JobInfo => ({
  id: page,
  command,
  page,
  args: [],
  hardware: true,
  started: 1,
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
});

beforeEach(() => {
  resetStores({ pages: PAGES });
  app.set({ nav: ['Setup', 'Data', 'Policy', 'Services'] });
});

const dot = (name: string) => within(screen.getByRole('button', { name: new RegExp(name) })).queryByTitle('Running');

describe('Sidebar', () => {
  it('marks the page a command runs from: find-port and find-cameras on Hardware', () => {
    render(<Sidebar />);
    expect(dot('Hardware')).toBeNull();
    act(() => attach(job('find-port', 'lerobot-find-port')));
    expect(dot('Hardware')).not.toBeNull();
    expect(dot('Teleoperate')).toBeNull();
    act(() => attach(job('teleoperate', 'lerobot-teleoperate')));
    expect(dot('Teleoperate')).not.toBeNull();
  });
});
