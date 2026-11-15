import { fireEvent, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it } from 'vitest';
import type { FieldSpec } from '../api/types';
import { useStore } from '../lib/store';
import { app, setHardware } from '../state/app';
import { field, resetStores } from '../test/utils';
import { Field } from './Field';

beforeEach(() => resetStores());
const stored = () => app.get().values.train;

/** As the pages render it: the stored values come from the store. */
function Connected({ f }: { f: FieldSpec }) {
  const values = useStore(app, (s) => s.values.train);
  return <Field page="train" field={f} stored={values} />;
}

describe('Field', () => {
  it('starts empty with lerobot’s default, and empty again removes the value', () => {
    render(<Connected f={field({ key: 'steps', kind: 'number', label: 'Steps', default: '100000' })} />);
    const input = screen.getByLabelText('Steps');
    expect(input).toHaveValue(null);
    expect(input).toHaveAttribute('placeholder', 'default: 100000');
    expect(screen.getByText('--steps')).toBeInTheDocument();
    fireEvent.change(input, { target: { value: '500' } });
    expect(stored()).toEqual({ steps: '500' });
    fireEvent.change(input, { target: { value: '' } });
    expect(stored()).toEqual({});
  });

  it('shows an example when lerobot has no default', () => {
    render(<Connected f={field({ key: 'policy.repo_id', kind: 'text', label: 'Repo', placeholder: '<user>/<model>' })} />);
    expect(screen.getByLabelText('Repo')).toHaveAttribute('placeholder', '<user>/<model>');
  });

  it('a toggle is on (the flag as true) or off (no flag)', async () => {
    render(<Connected f={field({ key: 'resume', kind: 'toggle', label: 'Add to an existing dataset', flag: '--resume' })} />);
    const toggle = screen.getByRole('switch', { name: 'Add to an existing dataset' });
    expect(toggle).toHaveAttribute('aria-checked', 'false');
    expect(screen.getByText('--resume')).toBeInTheDocument();
    await userEvent.click(toggle);
    expect(stored()).toEqual({ resume: true });
    expect(toggle).toHaveAttribute('aria-checked', 'true');
    await userEvent.click(screen.getByText('Add to an existing dataset')); // the label toggles it too
    expect(stored()).toEqual({});
  });

  it('booleans are default, true or false', async () => {
    render(<Connected f={field({ key: 'display_data', kind: 'bool', label: 'Show in Rerun', default: 'false' })} />);
    const select = screen.getByLabelText('Show in Rerun');
    expect(select).toHaveValue('');
    expect(screen.getByRole('option', { name: 'default: false' })).toBeInTheDocument();
    await userEvent.selectOptions(select, 'true');
    expect(stored()).toEqual({ display_data: true });
    await userEvent.selectOptions(select, 'false');
    expect(stored()).toEqual({ display_data: false }); // written: false is not "not entered"
    await userEvent.selectOptions(select, 'default: false');
    expect(stored()).toEqual({});
  });

  it('choices of a flag can go back to lerobot’s default; a custom value can be typed', async () => {
    const f = field({
      key: 'policy.path',
      kind: 'choice',
      label: 'Policy',
      custom: true,
      options: [{ group: 'Hub', items: [{ value: 'a', label: 'A', disabled: false, title: '' }, { value: 'b', label: 'B', disabled: false, title: '' }] }],
    });
    render(<Connected f={f} />);
    await userEvent.selectOptions(screen.getByLabelText('Policy'), 'b');
    expect(stored()).toEqual({ 'policy.path': 'b' });
    await userEvent.selectOptions(screen.getByLabelText('Policy'), 'Custom…');
    expect(stored()).toEqual({});
    await userEvent.type(screen.getByLabelText('Policy (custom)'), 'my/model');
    expect(stored()).toEqual({ 'policy.path': 'my/model' });
  });

  it('GUI choices always have a value', async () => {
    const f = field({
      key: 'gui.cameras',
      kind: 'choice',
      label: 'Cameras',
      value: 'use',
      flag: '--robot.cameras',
      options: [
        { value: 'use', label: 'Hardware', disabled: false, title: '' },
        { value: 'none', label: 'None', disabled: false, title: '' },
      ],
    });
    render(<Connected f={f} />);
    expect(screen.getAllByRole('option').map((o) => o.textContent)).toEqual(['Hardware', 'None']);
    expect(screen.getByLabelText('Cameras')).toHaveValue('use');
  });

  it('segments, with disabled choices', () => {
    const f = field({
      key: 'gui.mode',
      kind: 'seg',
      value: 'new',
      label: 'Start from',
      options: [
        { value: 'new', label: 'New', disabled: false, title: '' },
        { value: 'resume', label: 'Resume', disabled: true, title: 'no runs' },
      ],
    });
    render(<Connected f={f} />);
    expect(screen.getByRole('button', { name: 'New' })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByRole('button', { name: 'Resume' })).toBeDisabled();
  });

  it('offers suggestions and marks required flags', async () => {
    const f = field({ key: 'dataset.repo_id', kind: 'text', label: 'Dataset', required: true, suggest: ['alice/', 'team/'], help: 'Read from `lerobot/`.' })
    render(<Connected f={f} />);
    expect(screen.getByText('lerobot/', { selector: 'code' })).toBeInTheDocument();
    expect(screen.getByText(/required/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'team/' }));
    expect(stored()).toEqual({ 'dataset.repo_id': 'team/' });
  });

  it('stores the values the server gives with a value (a port: the board on it)', async () => {
    const board = '/dev/serial/by-id/F';
    const f = field({
      key: 'followerPort',
      kind: 'choice',
      label: 'Port',
      custom: true,
      options: [{ value: '/dev/ttyACM0', label: '/dev/ttyACM0', disabled: false, title: '' }],
      also: { values: { '/dev/ttyACM0': { followerBoard: board } }, other: { followerBoard: null } },
    });
    function Hardware() {
      const values = useStore(app, (s) => s.values.hardware);
      return <Field page="hardware" field={f} stored={values} onSet={setHardware} />;
    }
    render(<Hardware />);
    await userEvent.selectOptions(screen.getByLabelText('Port'), '/dev/ttyACM0');
    expect(app.get().values.hardware).toEqual({ followerPort: '/dev/ttyACM0', followerBoard: board });
    // a typed port the server doesn't know: no board (the remembered one goes)
    await userEvent.selectOptions(screen.getByLabelText('Port'), 'Custom…');
    fireEvent.change(screen.getByLabelText('Port (custom)'), { target: { value: '/dev/ttyACM9' } });
    expect(app.get().values.hardware).toEqual({ followerPort: '/dev/ttyACM9' });
  });
});
