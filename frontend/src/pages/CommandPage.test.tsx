import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it } from 'vitest';
import type { JobInfo } from '../api/types';
import { app } from '../state/app';
import { jobs } from '../state/jobs';
import { field, formResponse, jsonError, mockApi, PAGES, resetStores } from '../test/utils';
import { CommandPage } from './CommandPage';

const meta = PAGES.find((p) => p.id === 'teleoperate')!;

const form = (fps: unknown) =>
  formResponse({
    groups: [{ title: 'Options', fields: [field({ key: 'fps', kind: 'number', label: 'Loop rate (Hz)', flag: '--fps', value: fps })] }],
    hardware_summary: [{ label: 'Follower', value: 'ttyACM0 · f' }],
    command: { exe: 'lerobot-teleoperate', args: [`--fps=${fps}`], preview: `uv run lerobot-teleoperate \\\n    --fps=${fps}` },
  });

const info = (patch: Partial<JobInfo> = {}): JobInfo => ({
  id: 'j1',
  command: 'lerobot-teleoperate',
  page: 'teleoperate',
  args: [],
  hardware: true,
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

beforeEach(() => resetStores({ pages: PAGES }));

describe('CommandPage', () => {
  it('renders the server form and asks again when a value changes', async () => {
    const calls = mockApi({
      'POST /api/form/teleoperate': (body: unknown) => form((body as { values: { teleoperate: { fps?: string } } }).values.teleoperate.fps ?? 60),
    });
    render(<CommandPage meta={meta} />);
    expect(await screen.findByText('--fps=')).toBeInTheDocument();
    expect(screen.getByText('60')).toHaveClass('p-val');
    expect(screen.getByText('ttyACM0 · f')).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('Loop rate (Hz)'), { target: { value: '30' } });
    await waitFor(() => expect(screen.getByText('30', { selector: '.p-val' })).toBeInTheDocument());
    expect(calls.at(-1)!.body).toEqual({ values: { hardware: {}, teleoperate: { fps: '30' } }, preflight: null });
  });

  it('disables Run while there are errors and shows the messages with their actions', async () => {
    mockApi({
      'POST /api/form/teleoperate': formResponse({
        errors: 1,
        messages: [{ level: 'err', text: 'Set the `Follower` port.', actions: [{ type: 'go', page: 'hardware', label: 'Open Hardware' }] }],
      }),
    });
    app.set({ pages: [...PAGES] });
    render(<CommandPage meta={meta} />);
    expect(await screen.findByText('1 error to fix')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Run' })).toBeDisabled();
    await userEvent.click(screen.getByRole('button', { name: 'Open Hardware' }));
    expect(app.get().page).toBe('hardware');
  });

  it('runs on the server, and keeps a refused run as a blocked preflight', async () => {
    const preflight = { arms: [], swapped: true };
    let refuse = true;
    const calls = mockApi({
      'POST /api/form/teleoperate': form(60),
      'POST /api/form/teleoperate/run': () => (refuse ? jsonError(409, { message: 'swapped', preflight }) : info()),
    });
    app.set({ values: { teleoperate: { fps: 60 } } });
    render(<CommandPage meta={meta} />);
    const runButton = await screen.findByRole('button', { name: 'Run' });
    await waitFor(() => expect(runButton).toBeEnabled());
    await userEvent.click(runButton);
    await waitFor(() => expect(app.get().blocked.teleoperate).toEqual(preflight));
    // the next form request carries it, so the server can explain
    await waitFor(() => expect(calls.at(-1)!.body).toMatchObject({ preflight }));
    refuse = false;
    await userEvent.click(screen.getByRole('button', { name: 'Run' }));
    await waitFor(() => expect(jobs.get().byPage.teleoperate?.info.id).toBe('j1'));
    expect(app.get().blocked.teleoperate).toBeUndefined();
    expect(calls.find((c) => c.path === '/api/form/teleoperate/run')!.body).toEqual({ values: { teleoperate: { fps: 60 } }, force: false });
    expect(await screen.findByRole('button', { name: 'Running…' })).toBeDisabled();
  });

  it('shows the job, its calibration prompt warning, and sends input', async () => {
    const calls = mockApi({ 'POST /api/form/teleoperate': form(60), 'POST /api/jobs/j1/input': { ok: true } });
    const warning = 'lerobot says the leader motors on `ttyACM1` hold another calibration.';
    const { attach } = await import('../state/jobs');
    act(() => attach(info({ prompt: { role: 'leader', id: 'l', port: '/dev/ttyACM1', mismatch: true, warning } })));
    render(<CommandPage meta={meta} />);
    expect(await screen.findByText(/hold another calibration/)).toBeInTheDocument();
    expect(screen.getByText(/Running · /)).toBeInTheDocument();
    // a risky Enter needs a confirmation
    const confirm = window.confirm;
    window.confirm = () => false;
    await userEvent.click(screen.getByRole('button', { name: 'Enter' }));
    window.confirm = confirm;
    expect(calls.some((c) => c.path === '/api/jobs/j1/input')).toBe(false);
    await userEvent.type(screen.getByLabelText('Input for the process'), 'c{Enter}');
    await waitFor(() => expect(calls.find((c) => c.path === '/api/jobs/j1/input')!.body).toEqual({ text: 'c' }));
  });

  it('sends an empty line on the Enter key while it runs, unless a field has the focus', async () => {
    const calls = mockApi({ 'POST /api/form/teleoperate': form(60), 'POST /api/jobs/j1/input': { ok: true } });
    const { attach } = await import('../state/jobs');
    act(() => attach(info()));
    render(<CommandPage meta={meta} />);
    const sent = () => calls.filter((c) => c.path === '/api/jobs/j1/input').map((c) => c.body);
    expect(await screen.findByRole('button', { name: 'Enter' })).toHaveAttribute('aria-keyshortcuts', 'Enter');
    fireEvent.keyDown(document.body, { key: 'Enter' });
    await waitFor(() => expect(sent()).toEqual([{ text: '' }]));
    // Enter in a field is that field's
    fireEvent.keyDown(await screen.findByLabelText('Loop rate (Hz)'), { key: 'Enter' });
    expect(sent()).toHaveLength(1);
    // once it ended, the key sends nothing
    act(() => attach(info({ running: false, returncode: 0, ended: Date.now() / 1000 })));
    fireEvent.keyDown(document.body, { key: 'Enter' });
    expect(sent()).toHaveLength(1);
  });

  it('blocks Run while another robot command runs', async () => {
    mockApi({ 'POST /api/form/teleoperate': form(60) });
    const { attach } = await import('../state/jobs');
    act(() => attach(info({ id: 'j2', page: 'rollout', command: 'lerobot-rollout' })));
    render(<CommandPage meta={meta} />);
    expect(await screen.findByText('lerobot-rollout is using the robot.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Run' })).toBeDisabled();
  });
});
