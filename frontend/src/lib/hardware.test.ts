import { describe, expect, it } from 'vitest';
import type { CameraConfig } from '../api/types';
import { checkCamera, forgetCamera, isUsed, nameCamera, setCameraSettings } from './hardware';

const cam = (name: string, device: string): CameraConfig => ({ name, type: 'opencv', device, settings: { width: 640 } });

describe('cameras', () => {
  it('names a new camera with its captured type, without settings', () => {
    expect(nameCamera([], '/dev/video0', 'top', 'opencv')).toEqual([{ name: 'top', type: 'opencv', device: '/dev/video0' }]);
    expect(nameCamera([], '0', 'wrist')).toEqual([{ name: 'wrist', device: '0' }]); // an OpenCV index (macOS, Windows)
  });

  it('moves a name to another camera and swaps their devices', () => {
    const out = nameCamera([cam('top', '/dev/video0'), cam('wrist', '/dev/video2')], '/dev/video2', 'top');
    expect(out).toEqual([cam('top', '/dev/video2'), cam('wrist', '/dev/video0')]);
  });

  it('renames; an empty name keeps the camera; any name', () => {
    expect(nameCamera([cam('top', '/dev/video0')], '/dev/video0', 'front')).toEqual([cam('front', '/dev/video0')]);
    expect(nameCamera([cam('top', '/dev/video0')], '/dev/video0', '')).toEqual([cam('', '/dev/video0')]);
    // any name: the command quotes it
    expect(nameCamera([], '/dev/video0', '1st camera')).toEqual([{ name: '1st camera', device: '/dev/video0' }]);
  });

  it('moves a name with its settings; each device stays checked or not', () => {
    const fresh: CameraConfig = { name: '', type: 'opencv', device: '/dev/video2' }; // just checked
    // the unnamed camera had nothing to keep: the old device is left without a camera
    expect(nameCamera([cam('top', '/dev/video0'), fresh], '/dev/video2', 'top')).toEqual([cam('top', '/dev/video2')]);
    const off = { ...cam('top', '/dev/video0'), use: false };
    expect(nameCamera([off, cam('wrist', '/dev/video2')], '/dev/video2', 'top')).toEqual([
      cam('top', '/dev/video2'),
      { ...cam('wrist', '/dev/video0'), use: false },
    ]);
  });
});

describe('camera checkboxes', () => {
  it('checks a camera (made unnamed with its frame’s type); unchecking only clears its name', () => {
    const on = checkCamera([], '/dev/video0', true, 'opencv');
    expect(on).toEqual([{ name: '', type: 'opencv', device: '/dev/video0' }]);
    expect(isUsed(on[0]!)).toBe(true);
    const off = checkCamera([cam('top', '/dev/video0')], '/dev/video0', false);
    expect(off).toEqual([{ ...cam('', '/dev/video0'), use: false }]);
    expect(isUsed(off[0]!)).toBe(false);
    expect(checkCamera(off, '/dev/video0', true)).toEqual([cam('', '/dev/video0')]);
    expect(checkCamera([{ name: 'top', type: 'opencv', device: '/dev/video0' }], '/dev/video0', false)).toEqual([
      { name: '', type: 'opencv', device: '/dev/video0', use: false },
    ]);
    expect(checkCamera([], '/dev/video0', false)).toEqual([]);
  });

  it('sets and clears settings, and forgets a camera', () => {
    const cams = [cam('top', '/dev/video0'), cam('wrist', '/dev/video2')];
    expect(setCameraSettings(cams, '/dev/video0', { fps: '30', width: '' })[0]!.settings).toEqual({ fps: '30' });
    expect(setCameraSettings(cams, '/dev/video0', { fps: '30' })[1]).toEqual(cam('wrist', '/dev/video2'));
    expect(forgetCamera(cams, '/dev/video0')).toEqual([cam('wrist', '/dev/video2')]);
  });
});
