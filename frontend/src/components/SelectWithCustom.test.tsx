import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useState } from 'react';
import { describe, expect, it } from 'vitest';
import { SelectWithCustom } from './SelectWithCustom';

const OPTIONS = ['a', 'b'].map((v) => ({ value: v, label: v.toUpperCase(), disabled: false, title: '' }));

function Harness({ start = '', typedOnly = false, allowCustom = true }: { start?: string; typedOnly?: boolean; allowCustom?: boolean }) {
  const [value, setValue] = useState<string | null>(start);
  return (
    <>
      <SelectWithCustom
        value={value ?? ''}
        options={OPTIONS}
        empty="default"
        onChange={setValue}
        label="Thing"
        customLabel="Thing (custom)"
        typedOnly={typedOnly}
        allowCustom={allowCustom}
      />
      <output>{JSON.stringify(value)}</output>
    </>
  );
}

const value = () => JSON.parse(screen.getByRole('status').textContent!);

describe('SelectWithCustom', () => {
  it('chooses from the list, or types a value it doesn’t have', async () => {
    render(<Harness />);
    await userEvent.selectOptions(screen.getByLabelText('Thing'), 'B');
    expect(value()).toBe('b');
    expect(screen.queryByLabelText('Thing (custom)')).not.toBeInTheDocument();
    await userEvent.selectOptions(screen.getByLabelText('Thing'), 'Custom…');
    expect(value()).toBeNull(); // the chosen value goes
    await userEvent.type(screen.getByLabelText('Thing (custom)'), 'zz');
    expect(value()).toBe('zz');
    await userEvent.selectOptions(screen.getByLabelText('Thing'), 'default');
    expect(value()).toBeNull();
  });

  it('shows a value the list doesn’t have in the input', () => {
    render(<Harness start="typed" />);
    expect(screen.getByLabelText('Thing')).toHaveValue('__custom__');
    expect(screen.getByLabelText('Thing (custom)')).toHaveValue('typed');
  });

  it('is typed only with nothing to choose, and offers no Custom… when not allowed', () => {
    const { unmount } = render(<Harness typedOnly />);
    expect(screen.getByLabelText('Thing (custom)')).toBeInTheDocument();
    unmount();
    render(<Harness allowCustom={false} />);
    expect(screen.queryByRole('option', { name: 'Custom…' })).not.toBeInTheDocument();
  });
});
