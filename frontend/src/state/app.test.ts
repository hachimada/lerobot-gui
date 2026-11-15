import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { mockApi, resetStores } from '../test/utils';
import { app, checkArms, loadPersisted, runAction, setHardware, setValues, STORAGE_KEY } from './app';

beforeEach(() => resetStores());

describe('persisted values', () => {
  it('reads its save and survives garbage', () => {
    localStorage.setItem(STORAGE_KEY, '{not json');
    expect(loadPersisted().page).toBe('hardware');
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ page: 'rollout', values: { record: { 'dataset.fps': 15 } }, openAdv: [1, 'a'] }));
    expect(loadPersisted()).toEqual({ page: 'rollout', values: { record: { 'dataset.fps': 15 } }, openAdv: ['a'], presets: {} });
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ page: 'train', values: {}, openAdv: [], presets: { train: 'fast', record: 3 } }));
    expect(loadPersisted().presets).toEqual({ train: 'fast' });
  });

  it('gives the cameras saved before they had ids theirs, and keeps the ones they have', () => {
    const cameras = [{ name: 'top', device: '/dev/video0' }, { name: 'wrist', id: 'w' }];
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ values: { hardware: { followerPort: '/dev/ttyACM0', cameras } } }));
    const hw = loadPersisted().values.hardware!;
    expect(hw.followerPort).toBe('/dev/ttyACM0');
    expect(hw.cameras).toEqual([{ name: 'top', device: '/dev/video0', id: expect.any(String) }, { name: 'wrist', id: 'w' }]);
  });

  it('starts on Hardware, the first step', () => {
    localStorage.clear();
    expect(loadPersisted().page).toBe('hardware');
  });

  it('saves changes', () => {
    setValues('record', { 'dataset.single_task': 'pick' });
    expect(JSON.parse(localStorage.getItem(STORAGE_KEY)!).values.record).toEqual({ 'dataset.single_task': 'pick' });
  });
});

describe('setHardware', () => {
  const check = { loading: false, result: { arms: [], swapped: false }, error: null, at: 1 };

  it('drops the arm check when a port changes, and stores only what it is given', () => {
    app.set({ armCheck: check, blocked: { rollout: { arms: [], swapped: true } } });
    setHardware({ followerPort: '/dev/ttyACM0' });
    // the board comes from the server with the port (the field's `also`, an action's values)
    expect(app.get().values.hardware).toEqual({ followerPort: '/dev/ttyACM0' });
    expect(app.get().armCheck.result).toBeNull();
    expect(app.get().blocked).toEqual({});
  });

  it('keeps the arm check for camera changes', () => {
    app.set({ armCheck: check });
    setHardware({ cameras: [] }, { keepCheck: true });
    expect(app.get().armCheck.result).not.toBeNull();
  });
});

describe('setValues', () => {
  it('leaves the arm check alone: a command page’s values move no arm', () => {
    const check = { loading: false, result: { arms: [], swapped: false }, error: null, at: 1 };
    app.set({ armCheck: check });
    setValues('teleoperate', { fps: 30 });
    expect(app.get().armCheck).toEqual(check);
  });

  it('removes empty values (back to lerobot’s default)', () => {
    setValues('train', { 'policy.repo_id': 'x/', 'policy.push_to_hub': true });
    setValues('train', { 'policy.repo_id': '', 'policy.push_to_hub': null });
    expect(app.get().values.train).toEqual({});
  });
});

describe('runAction', () => {
  it('sets values and goes to a page', () => {
    app.set({ pages: [{ id: 'calibrate', title: 'Calibrate', icon: '', nav: 'Setup', exe: 'lerobot-calibrate', desc: '', hints: [], hardware: true, presets: true }] });
    runAction({ type: 'set', page: 'calibrate', values: { 'gui.target': 'leader' }, label: '', go: 'calibrate' });
    expect(app.get().values.calibrate).toEqual({ 'gui.target': 'leader' });
    expect(app.get().page).toBe('calibrate');
  });

  it('says its toast; keeps the arm check when told to', () => {
    const check = { loading: false, result: { arms: [], swapped: false }, error: null, at: 1 };
    app.set({ armCheck: check });
    runAction({ type: 'hardware', values: { followerId: 'a' }, label: '', toast: 'Done', keep_check: true });
    expect(app.get().armCheck).toEqual(check);
    expect(app.get().toast?.text).toBe('Done');
    runAction({ type: 'hardware', values: { followerId: 'b' }, label: '' });
    expect(app.get().armCheck.result).toBeNull();
  });

  it('runs anyway only after confirming', () => {
    let ran = 0;
    const confirm = window.confirm;
    window.confirm = () => false;
    runAction({ type: 'run_force', label: '', confirm: 'sure?' }, { runForce: () => ran++ });
    window.confirm = () => true;
    runAction({ type: 'run_force', label: '', confirm: 'sure?' }, { runForce: () => ran++ });
    window.confirm = confirm;
    expect(ran).toBe(1);
  });
});

describe('checkArms', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('sends the Hardware values as stored and applies the boards the server remembers', async () => {
    const hardware = { followerPort: '/dev/ttyACM0', followerId: 'f', leaderId: 'l' };
    app.set({ values: { hardware } });
    const result = {
      arms: [{ role: 'follower', port: '/dev/ttyACM0', id: 'f', status: 'ok', detail: '' }],
      swapped: false,
      remember: {
        type: 'hardware',
        values: { followerBoard: '/dev/serial/by-id/F' },
        label: 'Remember the boards',
        toast: 'Remembered the board of the follower',
        keep_check: true,
      },
    };
    const calls = mockApi({ 'POST /api/check-arms': result });
    await checkArms();
    expect(calls[0]!.body).toEqual({ hardware });
    expect(app.get().values.hardware).toEqual({ ...hardware, followerBoard: '/dev/serial/by-id/F' });
    expect(app.get().armCheck.result?.arms[0]!.status).toBe('ok'); // kept: the boards don't move an arm
    expect(app.get().toast?.text).toBe('Remembered the board of the follower');
  });
});
