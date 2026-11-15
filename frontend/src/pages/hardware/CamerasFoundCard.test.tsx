import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { CameraConfig, HardwareView } from '../../api/types';
import { app } from '../../state/app';
import { jobs } from '../../state/jobs';
import { field, formResponse, jsonError, mockApi, resetStores } from '../../test/utils';
import { CamerasFoundCard } from './CamerasFoundCard';

const VIEW = {
  camera_types: ['opencv', 'realsense'],
  camera_names: [],
  camera_fields: {
    opencv: [
      field({ key: 'index_or_path', kind: 'text' }),
      field({ key: 'fps', kind: 'number' }),
      field({ key: 'width', kind: 'number' }),
      field({ key: 'height', kind: 'number' }),
      field({ key: 'rotation', kind: 'choice' }),
    ],
  },
} as unknown as HardwareView;
const frame = (name: string, device: string, older: boolean) => ({ name, type: 'opencv', device, mtime: 1, width: 64, height: 48, older });
/** the cameras stored, without their ids (they only key the rows) */
const cameras = () => (app.get().values.hardware?.cameras as CameraConfig[]).map(({ id: _id, ...c }) => c);
const card = (device: string) => screen.getByRole('checkbox', { name: `Use ${device}` }).closest('.camrow') as HTMLElement;

beforeEach(() => resetStores());
afterEach(() => vi.restoreAllMocks());

describe('CamerasFoundCard', () => {
  it('deletes a frame from the ⋮ menu of its card, after asking', async () => {
    const calls = mockApi({
      'POST /api/form/find-cameras': formResponse({ page: 'find-cameras' }),
      'DELETE /api/captured-images/opencv__dev_video6.png': { ok: true },
    });
    const images = [frame('opencv__dev_video0.png', '/dev/video0', false), frame('opencv__dev_video6.png', '/dev/video6', true)];
    render(<CamerasFoundCard view={VIEW} images={images} dir="" />);
    expect(screen.getAllByText('older run')).toHaveLength(1);
    expect(screen.queryByRole('menuitem', { name: 'Delete' })).not.toBeInTheDocument(); // only in the menu
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(true);
    const before = jobs.get().captured;
    await userEvent.click(screen.getByRole('button', { name: 'More for /dev/video6' }));
    await userEvent.click(screen.getByRole('menuitem', { name: 'Delete' }));
    expect(confirm).toHaveBeenCalledWith('Delete the frame of /dev/video6 (opencv__dev_video6.png)?');
    await waitFor(() => expect(jobs.get().captured).toBe(before + 1)); // the frames are asked for again
    expect(calls.some((c) => c.method === 'DELETE' && c.path === '/api/captured-images/opencv__dev_video6.png')).toBe(true);
    expect(screen.queryByRole('menu')).not.toBeInTheDocument(); // closed after the choice
  });

  it('closes the menu with Escape, and a frame of the last run can be deleted too', async () => {
    mockApi({ 'POST /api/form/find-cameras': formResponse({ page: 'find-cameras' }) });
    render(<CamerasFoundCard view={VIEW} images={[frame('opencv__dev_video0.png', '/dev/video0', false)]} dir="" />);
    await userEvent.click(screen.getByRole('button', { name: 'More for /dev/video0' }));
    expect(screen.getByRole('menuitem', { name: 'Delete' })).toBeEnabled();
    await userEvent.keyboard('{Escape}');
    expect(screen.queryByRole('menu')).not.toBeInTheDocument();
  });

  it('a camera is used once checked; its card sets its name, fps, width and height', async () => {
    mockApi({ 'POST /api/form/find-cameras': formResponse({ page: 'find-cameras' }) });
    const images = [frame('opencv__dev_video0.png', '/dev/video0', false), frame('opencv__dev_video2.png', '/dev/video2', false)];
    render(<CamerasFoundCard view={VIEW} images={images} dir="" />);
    expect(screen.getByRole('checkbox', { name: 'Use /dev/video0' })).not.toBeChecked();
    expect(screen.getByLabelText('Name of /dev/video0')).toBeDisabled();
    await userEvent.click(screen.getByRole('checkbox', { name: 'Use /dev/video0' }));
    expect(cameras()).toEqual([{ name: '', type: 'opencv', device: '/dev/video0' }]); // the frame's type, no name yet
    const name = screen.getByLabelText('Name of /dev/video0');
    expect(name).toBeEnabled();
    expect(name).toHaveClass('missing');
    await userEvent.type(name, 'top{Enter}');
    expect(cameras()[0]!.name).toBe('top');
    fireEvent.change(screen.getByLabelText('fps of /dev/video0'), { target: { value: '30' } });
    await userEvent.click(within(card('/dev/video0')).getByRole('button', { name: '64×48' })); // the frame's size
    expect(cameras()[0]!.settings).toEqual({ fps: '30', width: '64', height: '48' });
    expect(screen.queryByLabelText('rotation of /dev/video0')).not.toBeInTheDocument(); // in step 4
    expect(screen.getByLabelText('fps of /dev/video2')).toBeDisabled();
    // unchecked: not used, the name cleared, the settings kept
    await userEvent.click(screen.getByRole('checkbox', { name: 'Use /dev/video0' }));
    expect(cameras()).toEqual([{ name: '', type: 'opencv', device: '/dev/video0', use: false, settings: { fps: '30', width: '64', height: '48' } }]);
    expect(screen.getByLabelText('Name of /dev/video0')).toHaveValue('');
    expect(screen.getByLabelText('fps of /dev/video0')).toHaveValue(30);
    expect(screen.getByLabelText('fps of /dev/video0')).toBeDisabled();
  });

  it('a name used before moves here with its settings', async () => {
    mockApi({ 'POST /api/form/find-cameras': formResponse({ page: 'find-cameras' }) });
    app.set({
      values: {
        hardware: {
          cameras: [
            { name: 'top', type: 'opencv', device: '/dev/video0', settings: { fps: 30 } },
            { name: '', type: 'opencv', device: '/dev/video2' },
          ],
        },
      },
    });
    const images = [frame('opencv__dev_video0.png', '/dev/video0', false), frame('opencv__dev_video2.png', '/dev/video2', false)];
    render(<CamerasFoundCard view={{ ...VIEW, camera_names: ['top', 'wrist'] }} images={images} dir="" />);
    expect(within(card('/dev/video0')).queryByRole('button', { name: 'top' })).not.toBeInTheDocument(); // its own name
    await userEvent.click(within(card('/dev/video2')).getByRole('button', { name: 'top' }));
    expect(cameras()).toEqual([{ name: 'top', type: 'opencv', device: '/dev/video2', settings: { fps: 30 } }]);
    expect(screen.getByRole('checkbox', { name: 'Use /dev/video0' })).not.toBeChecked();
  });

  it('deleting a named camera removes its name and settings too', async () => {
    const calls = mockApi({
      'POST /api/form/find-cameras': formResponse({ page: 'find-cameras' }),
      'DELETE /api/captured-images/opencv__dev_video6.png': { ok: true },
    });
    app.set({ values: { hardware: { cameras: [{ name: 'wrist', type: 'opencv', device: '/dev/video6', settings: { width: 640 } }] } } });
    render(<CamerasFoundCard view={VIEW} images={[frame('opencv__dev_video6.png', '/dev/video6', true)]} dir="" />);
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(true);
    await userEvent.click(screen.getByRole('button', { name: 'More for /dev/video6' }));
    await userEvent.click(screen.getByRole('menuitem', { name: 'Delete' }));
    expect(confirm).toHaveBeenCalledWith(
      'Delete the frame of /dev/video6 (opencv__dev_video6.png)? Its name (wrist) and settings are removed too.',
    );
    await waitFor(() => expect(app.get().values.hardware?.cameras).toEqual([]));
    expect(calls.some((c) => c.method === 'DELETE')).toBe(true);
  });

  it('keeps the camera when the frame could not be deleted', async () => {
    mockApi({
      'POST /api/form/find-cameras': formResponse({ page: 'find-cameras' }),
      'DELETE /api/captured-images/opencv__dev_video6.png': jsonError(409, 'Find cameras is running: wait for it to finish.'),
    });
    app.set({ values: { hardware: { cameras: [{ name: 'wrist', type: 'opencv', device: '/dev/video6' }] } } });
    render(<CamerasFoundCard view={VIEW} images={[frame('opencv__dev_video6.png', '/dev/video6', false)]} dir="" />);
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    await userEvent.click(screen.getByRole('button', { name: 'More for /dev/video6' }));
    await userEvent.click(screen.getByRole('menuitem', { name: 'Delete' }));
    await waitFor(() => expect(app.get().toast?.text).toContain('Find cameras is running'));
    expect((app.get().values.hardware?.cameras as { name: string }[]).map((c) => c.name)).toEqual(['wrist']);
  });
});
