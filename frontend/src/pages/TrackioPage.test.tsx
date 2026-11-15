import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it } from 'vitest';
import { field, formResponse, mockApi, PAGES, resetStores } from '../test/utils';
import { TrackioPage } from './TrackioPage';

const meta = PAGES.find((p) => p.id === 'trackio')!;
const form = formResponse({
  page: 'trackio',
  groups: [{ title: 'Dashboard', fields: [field({ key: 'project', kind: 'text', label: 'Project', flag: '--project', suggest: ['pick'] })] }],
  command: { exe: 'trackio', args: ['show'], preview: 'uv run trackio \\\n    show' },
});
/** a rescan that found runs logged to these Trackio Spaces (no account needed) */
const discover = (spaces: string[]) => ({
  ports: [],
  calibrations: { robots: [], teleoperators: [] },
  datasets: 0,
  policies: 1,
  local: { hf_namespaces: [], trackio_projects: ['pick'], trackio_spaces: spaces },
});

describe('TrackioPage', () => {
  beforeEach(() => resetStores({ pages: PAGES, discover: discover(['alice/trackio']) }));

  it('runs the dashboard, with the projects here offered and the Spaces of the runs linked', async () => {
    mockApi({ 'POST /api/form/trackio': form });
    render(<TrackioPage meta={meta} />);
    expect(await screen.findByRole('button', { name: 'pick' })).toBeInTheDocument();
    expect(screen.getByText(/uv run trackio/)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'alice/trackio' })).toHaveAttribute('href', 'https://huggingface.co/spaces/alice/trackio');
    expect(screen.queryByText('Presets')).toBeNull();
  });

  it('shows no Spaces card when no run logged to one', async () => {
    resetStores({ pages: PAGES, discover: discover([]) });
    mockApi({ 'POST /api/form/trackio': form });
    render(<TrackioPage meta={meta} />);
    expect(await screen.findByRole('button', { name: 'pick' })).toBeInTheDocument();
    expect(screen.queryByText('Spaces')).toBeNull();
  });
});
