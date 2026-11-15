import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { app, setValues } from '../state/app';
import { mockApi, resetStores } from '../test/utils';
import { PresetCard } from './PresetCard';

const FAST = { name: 'fast', saved: 1, values: { fps: 60, display_data: true } };

beforeEach(() => resetStores());
afterEach(() => vi.restoreAllMocks());

describe('PresetCard', () => {
  it('loads a preset in place of the page’s values', async () => {
    setValues('teleoperate', { teleop_time_s: 30 });
    mockApi({
      'GET /api/presets/teleoperate': [{ name: 'fast', saved: 1, count: 2 }],
      'GET /api/presets/teleoperate/fast': FAST,
    });
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(true);
    render(<PresetCard page="teleoperate" />);
    const select = await screen.findByRole('combobox', { name: 'Load a preset' });
    await waitFor(() => expect(screen.getByRole('option', { name: 'fast · 2 values' })).toBeInTheDocument());
    await userEvent.selectOptions(select, 'fast');
    expect(confirm).toHaveBeenCalledWith('Replace the values on this page with the preset “fast”?');
    await waitFor(() => expect(app.get().values.teleoperate).toEqual({ fps: 60, display_data: true })); // replaced, not merged
    expect(app.get().presets.teleoperate).toBe('fast');
    expect(await screen.findByText('fast', { selector: 'b' })).toBeInTheDocument();
  });

  it('saves the page’s values under a name, and says when they changed since', async () => {
    setValues('teleoperate', { fps: 60, display_data: true });
    const calls = mockApi({
      'GET /api/presets/teleoperate': [],
      'PUT /api/presets/teleoperate/fast': FAST,
      'GET /api/presets/teleoperate/fast': FAST,
    });
    render(<PresetCard page="teleoperate" />);
    await userEvent.click(await screen.findByRole('button', { name: 'Save as…' }));
    await userEvent.type(screen.getByRole('textbox', { name: 'Preset name' }), 'fast{Enter}');
    await waitFor(() => expect(app.get().presets.teleoperate).toBe('fast'));
    expect(calls.find((c) => c.method === 'PUT')?.body).toEqual({ values: { fps: 60, display_data: true } });
    expect(screen.queryByText('changed')).not.toBeInTheDocument();
    setValues('teleoperate', { fps: 30 });
    expect(await screen.findByText('changed')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Save' })).toBeEnabled();
  });

  it('deletes the current preset after asking', async () => {
    resetStores({ presets: { teleoperate: 'fast' }, values: { teleoperate: FAST.values } });
    const calls = mockApi({
      'GET /api/presets/teleoperate': [{ name: 'fast', saved: 1, count: 2 }],
      'GET /api/presets/teleoperate/fast': FAST,
      'DELETE /api/presets/teleoperate/fast': [],
    });
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    render(<PresetCard page="teleoperate" />);
    await userEvent.click(await screen.findByRole('button', { name: 'Delete the preset fast' }));
    await waitFor(() => expect(app.get().presets.teleoperate).toBeUndefined());
    expect(calls.some((c) => c.method === 'DELETE')).toBe(true);
    expect(app.get().values.teleoperate).toEqual(FAST.values); // the values stay
  });
});
