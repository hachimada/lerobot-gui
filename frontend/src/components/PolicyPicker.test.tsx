import { act, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it } from 'vitest';
import type { FieldSpec, HubModels } from '../api/types';
import { resetHubModels } from '../hooks/useHubModels';
import { useStore } from '../lib/store';
import { app } from '../state/app';
import { field, mockApi, resetStores } from '../test/utils';
import { Field } from './Field';
import { fmtCount } from './PolicyPicker';

const RUN = 'outputs/train/act_2026-01-06/checkpoints';
const POLICY = field({
  key: 'policy.path',
  kind: 'picker',
  label: 'Policy',
  hub: true,
  options: [
    {
      group: 'act_2026-01-06',
      items: [
        { value: `${RUN}/last/pretrained_model`, label: 'act · last (step 50,000)', disabled: false, title: '' },
        { value: `${RUN}/010000/pretrained_model`, label: 'act · step 10,000', disabled: false, title: '' },
      ],
    },
  ],
});
const HUB: HubModels = {
  groups: [
    {
      title: 'lerobot',
      author: 'lerobot',
      models: [
        { id: 'lerobot/smolvla_base', downloads: 160097, likes: 492, created: '2025-06-01', private: false },
        { id: 'lerobot/pi0_base', downloads: 9000, likes: 10, created: '2025-09-01', private: false },
        { id: 'lerobot/pi0fast-base', downloads: 900, likes: 1, created: null, private: false },
      ],
    },
    { title: 'alice (you)', author: 'alice', models: [{ id: 'alice/my_act', downloads: 3, likes: 0, created: null, private: true }] },
  ],
  error: null,
};

beforeEach(() => {
  resetStores();
  resetHubModels();
});
const chosen = () => app.get().values.rollout?.['policy.path'];

function Connected({ f }: { f: FieldSpec }) {
  const values = useStore(app, (s) => s.values.rollout);
  return <Field page="rollout" field={f} stored={values} />;
}

describe('PolicyPicker', () => {
  it('lists nothing until Hub or Local is chosen', () => {
    render(<Connected f={POLICY} />);
    expect(screen.getByText(/No policy chosen yet/)).toBeInTheDocument();
    expect(screen.queryByRole('listbox')).not.toBeInTheDocument();
  });

  it('searches the local checkpoints', async () => {
    render(<Connected f={POLICY} />);
    await userEvent.click(screen.getByRole('button', { name: 'Local checkpoints · 2' }));
    expect(screen.getAllByRole('option')).toHaveLength(2);
    expect(screen.getByText('act_2026-01-06')).toHaveClass('pick-group');
    await userEvent.type(screen.getByLabelText('Search local checkpoints'), '10,000');
    expect(screen.getAllByRole('option')).toHaveLength(1);
    await userEvent.click(screen.getByRole('option', { name: /step 10,000/ }));
    expect(chosen()).toBe(`${RUN}/010000/pretrained_model`);
    expect(screen.queryByRole('listbox')).not.toBeInTheDocument(); // closes once chosen
    expect(screen.getByText(`${RUN}/010000/pretrained_model`)).toBeInTheDocument();
  });

  it('searches every model on the Hub, the user’s own too', async () => {
    const calls = mockApi({ 'GET /api/hub/models': HUB });
    render(<Connected f={POLICY} />);
    await userEvent.click(screen.getByRole('button', { name: 'Hugging Face Hub' }));
    expect(await screen.findByRole('option', { name: /lerobot\/smolvla_base/ })).toHaveTextContent('160k downloads · 2025-06-01');
    expect(screen.getAllByRole('option')).toHaveLength(4);
    expect(screen.getByRole('option', { name: /alice\/my_act/ })).toHaveTextContent('private');
    await userEvent.type(screen.getByLabelText('Search models on the Hub'), 'pi0');
    expect(screen.getAllByRole('option').map((o) => o.textContent)).toEqual([
      expect.stringContaining('lerobot/pi0_base'),
      expect.stringContaining('lerobot/pi0fast-base'),
    ]);
    await userEvent.click(screen.getByRole('option', { name: /lerobot\/pi0fast-base/ }));
    expect(chosen()).toBe('lerobot/pi0fast-base');
    // asked once: opening the Hub list again reuses it
    await userEvent.click(screen.getByRole('button', { name: 'Hugging Face Hub' }));
    await screen.findByRole('option', { name: /lerobot\/pi0_base/ });
    expect(calls.filter((c) => c.path === '/api/hub/models')).toHaveLength(1);
  });

  it('asks the Hub again after logging in: the account’s own models are listed too', async () => {
    const before = { ...HUB, groups: HUB.groups.slice(0, 1) };
    let listing = before;
    const calls = mockApi({ 'GET /api/hub/models': () => listing });
    render(<Connected f={POLICY} />);
    await userEvent.click(screen.getByRole('button', { name: 'Hugging Face Hub' }));
    expect(await screen.findAllByRole('option')).toHaveLength(3);
    listing = HUB;
    act(() => app.set({ accounts: { hf: { logged_in: true, user: 'alice' } } }));
    expect(await screen.findByRole('option', { name: /alice\/my_act/ })).toBeInTheDocument();
    expect(calls.filter((c) => c.path === '/api/hub/models')).toHaveLength(2);
  });

  it('takes a typed repo id or path, with Enter too', async () => {
    mockApi({ 'GET /api/hub/models': HUB });
    render(<Connected f={POLICY} />);
    await userEvent.click(screen.getByRole('button', { name: 'Hugging Face Hub' }));
    await userEvent.type(screen.getByLabelText('Search models on the Hub'), 'bob/policy{Enter}');
    expect(chosen()).toBe('bob/policy');
    await userEvent.click(screen.getByRole('button', { name: 'Clear' }));
    expect(chosen()).toBeUndefined();
  });

  it('says when the Hub can’t be reached; local still works', async () => {
    mockApi({ 'GET /api/hub/models': { groups: [{ title: 'lerobot', author: 'lerobot', models: [] }], error: 'Could not list lerobot’s models on the Hub: offline' } });
    render(<Connected f={POLICY} />);
    await userEvent.click(screen.getByRole('button', { name: 'Hugging Face Hub' }));
    expect(await screen.findByText(/offline/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Local checkpoints · 2' }));
    await waitFor(() => expect(screen.getAllByRole('option')).toHaveLength(2));
  });

  it('formats counts', () => {
    expect([fmtCount(3), fmtCount(9000), fmtCount(160097), fmtCount(2_400_000)]).toEqual(['3', '9k', '160k', '2.4M']);
  });
});
