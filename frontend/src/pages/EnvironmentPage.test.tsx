import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it } from 'vitest';
import { mockApi, resetStores } from '../test/utils';
import { EnvironmentPage } from './EnvironmentPage';

beforeEach(() => resetStores());

const INFO = {
  locations: [
    { name: 'HF_LEROBOT_HOME', value: '~/ws/lerobot', read_from: 'lerobot.utils.constants', from_env: true },
    { name: 'HF_HOME', value: '~/.cache/huggingface', read_from: 'huggingface_hub.constants', from_env: false },
  ],
  variables: [
    { name: 'DISPLAY', set: true, secret: false, value: ':0' },
    { name: 'HF_TOKEN', set: false, secret: true, value: null, note: 'The login saved in `~/.cache/huggingface/token` is used.' },
    { name: 'LEROBOT_GUI_TOKEN', set: true, secret: true, value: null },
    { name: 'WAYLAND_DISPLAY', set: false, secret: false, value: null },
  ],
  runtime: [{ name: 'lerobot', value: '0.7.0' }],
};

describe('EnvironmentPage', () => {
  it('shows the data dirs, the variables (secrets hidden) and what runs', async () => {
    const calls = mockApi({ 'GET /api/environment': INFO });
    render(<EnvironmentPage />);
    expect(await screen.findByText('~/ws/lerobot')).toBeInTheDocument();
    expect(screen.getByText('set in the environment')).toBeInTheDocument();
    expect(screen.getByText('default')).toBeInTheDocument();
    expect(screen.getByText('from huggingface_hub.constants')).toBeInTheDocument();
    expect(screen.getByText(':0')).toBeInTheDocument();
    expect(screen.getByText('set · hidden')).toBeInTheDocument();
    expect(screen.getAllByText('not set')).toHaveLength(2);
    expect(screen.getByText('~/.cache/huggingface/token', { selector: 'code' })).toBeInTheDocument();
    expect(screen.getByText('0.7.0')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Read again' }));
    expect(calls.filter((c) => c.path === '/api/environment')).toHaveLength(2);
  });

  it('says so when a dir cannot be read', async () => {
    mockApi({ 'GET /api/environment': { ...INFO, locations: [{ name: 'lerobot.utils.constants', error: 'ValueError: no' }] } });
    render(<EnvironmentPage />);
    expect(await screen.findByText('lerobot.utils.constants: ValueError: no')).toBeInTheDocument();
  });
});
