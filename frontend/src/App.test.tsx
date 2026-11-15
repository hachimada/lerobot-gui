import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it } from 'vitest';
import type { Discover } from './api/types';
import { App } from './App';
import { app } from './state/app';
import { formResponse, mockApi, PAGES, resetStores } from './test/utils';

beforeEach(() => {
  resetStores();
  location.hash = '';
});

const discover: Discover = {
  ports: [],
  calibrations: { robots: [], teleoperators: [] },
  datasets: 0,
  policies: 0,
  local: { hf_namespaces: [], trackio_projects: [], trackio_spaces: [] },
};

describe('App', () => {
  it('boots, lists the pages and navigates', async () => {
    mockApi({
      'GET /api/pages': { pages: PAGES, nav: ['Setup', 'Data', 'Policy'] },
      'GET /api/discover': discover,
      'GET /api/accounts': { hf: {} },
      'GET /api/jobs': [],
      'POST /api/form/rollout': formResponse({ page: 'rollout', command: { exe: 'lerobot-rollout', args: [], preview: 'uv run lerobot-rollout' } }),
      'POST /api/form/teleoperate': formResponse(),
    });
    render(<App />);
    expect(await screen.findByRole('heading', { name: 'Rollout' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Find port/ })).not.toBeInTheDocument(); // no page of its own
    await userEvent.click(screen.getByRole('button', { name: 'Teleoperate' }));
    expect(screen.getByRole('heading', { name: 'Teleoperate' })).toBeInTheDocument();
    expect(location.hash).toBe('#teleoperate');
    await waitFor(() => expect(screen.getByText('uv run lerobot-teleoperate')).toBeInTheDocument());
    expect(app.get().page).toBe('teleoperate');
  });

  it('opens Environment from the sidebar', async () => {
    mockApi({
      'GET /api/pages': { pages: PAGES, nav: ['Setup', 'Data', 'Policy'] },
      'GET /api/discover': discover,
      'GET /api/accounts': { hf: {} },
      'GET /api/jobs': [],
      'GET /api/environment': { locations: [], variables: [], runtime: [{ name: 'lerobot', value: '0.7.0' }] },
      'POST /api/form/rollout': formResponse({ page: 'rollout' }),
    });
    render(<App />);
    await userEvent.click(await screen.findByRole('button', { name: 'Environment' }));
    expect(screen.getByRole('heading', { name: 'Environment' })).toBeInTheDocument();
    expect(await screen.findByText('0.7.0')).toBeInTheDocument();
  });

  it('says so when the server is unreachable', async () => {
    mockApi({});
    render(<App />);
    await waitFor(() => expect(app.get().toast?.text).toMatch(/Could not reach the server/));
  });
});
