import { describe, expect, it } from 'vitest';
import { confirmWriteText } from './calibration';

const prompt = { id: 'alice_leader', port: '/dev/ttyACM1', mismatch: true, warning: null };

describe('confirmWriteText', () => {
  it('names the arm and its port', () => {
    const text = confirmWriteText({ ...prompt, role: 'leader' });
    expect(text).toContain('Write alice_leader into the motors on ttyACM1?');
    expect(text).toContain('Only if that port really is the leader.');
  });

  it('does without them when both arms have the id', () => {
    const text = confirmWriteText({ ...prompt, role: null, port: '' });
    expect(text).toContain('Write alice_leader into the motors?');
    expect(text).toContain('Only if it really is that arm.');
  });
});
