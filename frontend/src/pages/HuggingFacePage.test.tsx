import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { HfLocal } from '../api/types';
import { mockApi, resetStores } from '../test/utils';
import { HuggingFacePage } from './HuggingFacePage';

const LOCAL: HfLocal = {
  home: 'lerobot',
  datasets: [
    { repo_id: 'alice/pick', path: 'lerobot/alice/pick', episodes: 50, frames: 9000, fps: 30, robot_type: 'so101_follower', cameras: ['top'], tasks: [], size: 1_200_000_000, mtime: 1 },
  ],
  calibrations: [{ kind: 'robots', class: 'so_follower', id: 'arm1', path: 'lerobot/calibration/robots/so_follower/arm1.json' }],
  caches: [
    { name: 'HF_LEROBOT_HUB_CACHE', path: 'lerobot/hub', size: 0, error: null, repos: [] },
    {
      name: 'HF_HUB_CACHE',
      path: '~/.cache/huggingface/hub',
      size: 900_000_000,
      error: null,
      repos: [{ repo_id: 'lerobot/smolvla_base', repo_type: 'model', size: 900_000_000, files: 3, revisions: 1, last_accessed: 1, last_modified: 1 }],
    },
  ],
};
const CLOUD = {
  logged_in: true,
  owners: [
    {
      owner: 'alice',
      kind: 'user',
      error: null,
      datasets: [{ id: 'alice/pick', private: true, downloads: 2, likes: 0, updated: '2026-01-05T09:00:00', url: 'https://huggingface.co/datasets/alice/pick' }],
      models: [],
    },
    { owner: 'lab', kind: 'org', error: '403 Forbidden', datasets: [], models: [] },
  ],
};

beforeEach(() => resetStores({ accounts: { hf: { logged_in: true, user: 'alice' } } }));
afterEach(() => vi.restoreAllMocks());

describe('HuggingFacePage', () => {
  it('lists the local data and the account’s repos on the Hub', async () => {
    mockApi({ 'GET /api/hf/local': LOCAL, 'GET /api/hf/cloud': CLOUD, 'GET /api/discover': {} });
    render(<HuggingFacePage />);
    expect(await screen.findByText('alice/pick', { selector: '.item-title span' })).toBeInTheDocument();
    expect(screen.getByText(/50 episodes · 9000 frames · 30 fps · cameras: top · 1.2 GB/)).toBeInTheDocument();
    expect(screen.getByText('lerobot/smolvla_base')).toBeInTheDocument();
    expect(screen.getByText('Nothing downloaded here.')).toBeInTheDocument();
    const link = await screen.findByRole('link', { name: 'alice/pick' });
    expect(link).toHaveAttribute('href', 'https://huggingface.co/datasets/alice/pick');
    expect(screen.getByText(/private · 2 downloads · updated 2026-01-05/)).toBeInTheDocument();
    expect(screen.getByText('403 Forbidden')).toBeInTheDocument();
  });

  it('deletes after asking, and shows what is left', async () => {
    const calls = mockApi({
      'GET /api/hf/local': LOCAL,
      'GET /api/hf/cloud': CLOUD,
      'GET /api/discover': { ports: [], cameras: [], calibrations: { robots: [], teleoperators: [] }, datasets: 0, policies: 0 },
      'POST /api/hf/local/delete': { ...LOCAL, datasets: [], message: 'Deleted the dataset `alice/pick`.' },
    });
    const confirm = vi.spyOn(window, 'confirm').mockReturnValueOnce(false).mockReturnValueOnce(true);
    render(<HuggingFacePage />);
    const button = await screen.findByRole('button', { name: 'Delete the dataset alice/pick' });
    await userEvent.click(button);
    expect(calls.some((c) => c.path === '/api/hf/local/delete')).toBe(false); // cancelled
    await userEvent.click(button);
    expect(confirm).toHaveBeenLastCalledWith("Delete the dataset alice/pick (1.2 GB) from this computer? This can't be undone.");
    expect(calls.find((c) => c.path === '/api/hf/local/delete')?.body).toEqual({ kind: 'dataset', repo_id: 'alice/pick' });
    expect(await screen.findByText('No datasets in HF_LEROBOT_HOME.')).toBeInTheDocument();
  });

  it('asks to log in before listing the Hub', async () => {
    resetStores({ accounts: { hf: { logged_in: false } } });
    const calls = mockApi({ 'GET /api/hf/local': LOCAL });
    render(<HuggingFacePage />);
    const hub = (await screen.findByText('On the Hub')).closest('.card') as HTMLElement;
    expect(within(hub).getByText('Log in to list your datasets and models on the Hub.')).toBeInTheDocument();
    expect(calls.some((c) => c.path === '/api/hf/cloud')).toBe(false);
  });
});
