import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { useEnterKey } from './useEnterKey';

function Page({ active, onEnter }: { active: boolean; onEnter: () => void }) {
  useEnterKey(active, onEnter);
  return (
    <div>
      <input aria-label="Field" />
      <textarea aria-label="Notes" />
      <select aria-label="Choice">
        <option>a</option>
      </select>
      <button type="button">Stop</button>
      <button type="button" disabled>
        Running…
      </button>
      <div role="button" tabIndex={0}>
        Chip
      </div>
      <p>Text</p>
    </div>
  );
}

const enter = (el: Element | Window, init: KeyboardEventInit = {}) => fireEvent.keyDown(el, { key: 'Enter', ...init });

describe('useEnterKey', () => {
  it('runs on the Enter key when nothing that takes Enter has the focus', () => {
    const onEnter = vi.fn();
    render(<Page active onEnter={onEnter} />);
    enter(document.body);
    enter(screen.getByText('Text'));
    // a button that went disabled while focused (Run once it runs) doesn't take it
    enter(screen.getByRole('button', { name: 'Running…' }));
    expect(onEnter).toHaveBeenCalledTimes(3);
  });

  it('leaves Enter to fields, buttons and choices, and to other keys', () => {
    const onEnter = vi.fn();
    render(<Page active onEnter={onEnter} />);
    enter(screen.getByLabelText('Field'));
    enter(screen.getByLabelText('Notes'));
    enter(screen.getByLabelText('Choice'));
    enter(screen.getByRole('button', { name: 'Stop' }));
    enter(screen.getByRole('button', { name: 'Chip' }));
    fireEvent.keyDown(document.body, { key: 'a' });
    expect(onEnter).not.toHaveBeenCalled();
  });

  it('ignores Enter held down, with a modifier, ending an IME composition or already handled', () => {
    const onEnter = vi.fn();
    render(<Page active onEnter={onEnter} />);
    enter(document.body, { repeat: true });
    enter(document.body, { ctrlKey: true });
    enter(document.body, { shiftKey: true });
    enter(document.body, { altKey: true });
    enter(document.body, { metaKey: true });
    enter(document.body, { isComposing: true });
    const handled = new KeyboardEvent('keydown', { key: 'Enter', bubbles: true, cancelable: true });
    handled.preventDefault();
    document.body.dispatchEvent(handled);
    expect(onEnter).not.toHaveBeenCalled();
  });

  it('does nothing while inactive, and stops listening once unmounted', () => {
    const onEnter = vi.fn();
    const { rerender, unmount } = render(<Page active={false} onEnter={onEnter} />);
    enter(document.body);
    expect(onEnter).not.toHaveBeenCalled();
    rerender(<Page active onEnter={onEnter} />);
    enter(document.body);
    expect(onEnter).toHaveBeenCalledTimes(1);
    unmount();
    enter(document.body);
    expect(onEnter).toHaveBeenCalledTimes(1);
  });

  it('calls the latest callback and keeps the key from doing anything else', () => {
    const first = vi.fn();
    const second = vi.fn();
    const { rerender } = render(<Page active onEnter={first} />);
    rerender(<Page active onEnter={second} />);
    expect(enter(document.body)).toBe(false); // default prevented
    expect(first).not.toHaveBeenCalled();
    expect(second).toHaveBeenCalledTimes(1);
  });
});
