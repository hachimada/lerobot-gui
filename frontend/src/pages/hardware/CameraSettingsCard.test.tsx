import { fireEvent, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it } from 'vitest';
import type { CameraConfig, HardwareView } from '../../api/types';
import { app } from '../../state/app';
import { field, resetStores } from '../../test/utils';
import { CameraSettingsCard } from './CameraSettingsCard';

const VIEW = {
  camera_types: ['opencv', 'zmq'],
  camera_device_field: { opencv: 'index_or_path', zmq: null },
  camera_fields: {
    opencv: [
      field({ key: 'index_or_path', kind: 'text', required: true }),
      field({ key: 'width', kind: 'number', label: 'width' }),
      field({ key: 'rotation', kind: 'choice', label: 'rotation', default: 'NO_ROTATION', options: [{ value: 'ROTATE_90', label: 'ROTATE_90', disabled: false, title: '' }] }),
    ],
    zmq: [field({ key: 'server_address', kind: 'text', label: 'server_address', required: true })],
  },
} as unknown as HardwareView;

const IMAGES = [{ name: 'opencv__dev_video0.png', type: 'opencv', device: '/dev/video0', mtime: 1, width: 1280, height: 720 }];

const cameras = () => app.get().values.hardware?.cameras as CameraConfig[];

beforeEach(() => resetStores());

describe('CameraSettingsCard', () => {
  it('edits lerobot’s settings of the camera’s type; empty removes one', async () => {
    app.set({ values: { hardware: { cameras: [{ name: 'top', type: 'opencv', device: '/dev/video4' }] } } });
    render(<CameraSettingsCard view={VIEW} images={IMAGES} />);
    expect(screen.getByText('index_or_path')).toHaveClass('flag'); // the device setting, chosen above
    expect(screen.queryByLabelText('index_or_path')).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('width'), { target: { value: '1280' } });
    expect(cameras()[0]!.settings).toEqual({ width: '1280' });
    await userEvent.selectOptions(screen.getByLabelText('rotation'), 'ROTATE_90');
    expect(cameras()[0]!.settings).toEqual({ width: '1280', rotation: 'ROTATE_90' });
    fireEvent.change(screen.getByLabelText('width'), { target: { value: '' } });
    expect(cameras()[0]!.settings).toEqual({ rotation: 'ROTATE_90' });
  });

  it('shows the cameras used; one found in step 3 has its name and card settings there', () => {
    app.set({
      values: {
        hardware: {
          cameras: [
            { name: 'top', type: 'opencv', device: '/dev/video0', settings: { width: 640 } },
            { name: 'wrist', type: 'opencv', device: '/dev/video2', use: false },
            { name: '', type: 'opencv', device: '/dev/video0' },
          ],
        },
      },
    });
    render(<CameraSettingsCard view={VIEW} images={IMAGES} />);
    expect(screen.getByText('top')).toHaveClass('cam-title'); // shown, not an input
    expect(screen.queryByLabelText('Camera name')).not.toBeInTheDocument();
    expect(screen.getByText('no name yet (step 3)')).toHaveClass('missing');
    expect(screen.queryByText('wrist')).not.toBeInTheDocument(); // unchecked
    expect(screen.queryByLabelText('width')).not.toBeInTheDocument(); // on its card
    expect(screen.getAllByLabelText('rotation')).toHaveLength(2);
    expect(screen.queryByTitle('Remove')).not.toBeInTheDocument(); // unchecked in step 3 instead
  });

  it('asks for the type first, then shows that type’s settings and device', async () => {
    app.set({ values: { hardware: { cameras: [{ name: 'far' }] } } });
    render(<CameraSettingsCard view={VIEW} images={[]} />);
    expect(screen.getByText('Choose the camera type to see its settings.')).toBeInTheDocument();
    await userEvent.selectOptions(screen.getByLabelText('far type'), 'zmq');
    expect(cameras()[0]!.type).toBe('zmq');
    expect(screen.getByLabelText('server_address')).toBeInTheDocument();
    expect(screen.queryByLabelText('far device')).not.toBeInTheDocument(); // zmq has no device setting
  });

  it('adds a camera with no settings of the GUI’s own', async () => {
    render(<CameraSettingsCard view={VIEW} images={[]} />);
    await userEvent.click(screen.getByRole('button', { name: 'Add manually' }));
    expect(cameras()).toEqual([{ name: 'cam1', id: expect.any(String) }]); // the id only keys its row
  });

  it('keeps each row with its camera when one above is removed', async () => {
    app.set({ values: { hardware: { cameras: ['a', 'b', 'c'].map((n) => ({ name: n, id: n, type: 'opencv' })) } } });
    render(<CameraSettingsCard view={VIEW} images={IMAGES} />);
    // c's device typed instead of chosen from the frames
    await userEvent.selectOptions(screen.getByLabelText('c device'), 'Custom…');
    expect(screen.getByLabelText('c index_or_path')).toBeInTheDocument();
    await userEvent.click(screen.getAllByTitle('Remove')[1]!);
    expect(cameras().map((c) => c.name)).toEqual(['a', 'c']);
    expect(screen.getByLabelText('c index_or_path')).toBeInTheDocument();
    expect(screen.queryByLabelText('a index_or_path')).not.toBeInTheDocument();
  });
});


describe('CameraSettingsCard devices', () => {
  it('offers the devices of the last Find cameras frames', () => {
    app.set({ values: { hardware: { cameras: [{ name: 'top', type: 'opencv', device: '/dev/video0' }] } } });
    render(<CameraSettingsCard view={VIEW} images={[...IMAGES, { ...IMAGES[0]!, name: 'opencv_1.png', device: '1' }]} />);
    const select = screen.getByRole('combobox', { name: 'top device' });
    expect(Array.from((select as HTMLSelectElement).options).map((o) => o.value)).toEqual(['/dev/video0', '1', '__custom__']);
  });
});
