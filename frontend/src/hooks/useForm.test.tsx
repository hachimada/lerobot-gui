import { render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it } from 'vitest';
import type { ArmCheck, HardwareForm } from '../api/types';
import { app } from '../state/app';
import { mockApi, resetStores } from '../test/utils';
import { useHardwareForm } from './useForm';

const CHECK: ArmCheck = { arms: [], swapped: false };

function Hardware({ check }: { check: ArmCheck | null }) {
  const form = useHardwareForm(check);
  return <div>{form ? form.groups.map((g) => g.title).join(', ') : 'loading'}</div>;
}

beforeEach(() => resetStores());

describe('useHardwareForm', () => {
  it('asks the Hardware route with the values as stored and the last arm check', async () => {
    const answer = { groups: [{ title: 'Follower', fields: [] }], view: {} } as unknown as HardwareForm;
    const calls = mockApi({ 'POST /api/hardware': answer });
    app.set({ values: { hardware: { followerPort: '/dev/ttyACM0' } } });
    render(<Hardware check={CHECK} />);
    expect(await screen.findByText('Follower')).toBeInTheDocument();
    expect(calls.at(-1)!.body).toEqual({ hardware: { followerPort: '/dev/ttyACM0' }, arm_check: CHECK });
    // asked again when a value changes
    app.set({ values: { hardware: { followerPort: '/dev/ttyACM1' } } });
    await waitFor(() => expect(calls.at(-1)!.body).toMatchObject({ hardware: { followerPort: '/dev/ttyACM1' } }));
  });
});
