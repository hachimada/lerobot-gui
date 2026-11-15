import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { Preview } from './CommandCard';

describe('Preview', () => {
  it('shows one flag per line, flag and value apart', () => {
    const { container } = render(<Preview preview={'uv run lerobot-record \\\n    --dataset.single_task="pick it" \\\n    opencv'} />);
    expect(screen.getByText('uv run lerobot-record')).toHaveClass('p-cmd');
    expect(screen.getByText('--dataset.single_task=')).toHaveClass('p-flag');
    expect(screen.getByText('"pick it"')).toHaveClass('p-val');
    expect(screen.getByText('opencv')).toHaveClass('p-val');
    expect(container.textContent).toBe('uv run lerobot-record \\\n    --dataset.single_task="pick it" \\\n    opencv');
  });
});
