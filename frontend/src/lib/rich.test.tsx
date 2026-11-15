import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { Rich, withLinks } from './rich';

describe('Rich', () => {
  it('writes code spans and links to the GUI’s pages, and nothing else as a link', () => {
    render(
      <p>
        <Rich text="Runs `trackio show`: see the [Trackio](#trackio) page. [elsewhere](https://example.com) stays text." />
      </p>,
    );
    expect(screen.getByText('trackio show').tagName).toBe('CODE');
    expect(screen.getAllByRole('link').map((a) => [a.textContent, a.getAttribute('href')])).toEqual([['Trackio', '#trackio']]);
    expect(screen.getByText(/stays text/).textContent).toContain('[elsewhere](https://example.com)');
  });
});

describe('withLinks', () => {
  it('links the web addresses in a command’s output, without the punctuation after them', () => {
    const text = '* Trackio UI launched at: http://127.0.0.1:7860/?project=pick\nsee https://huggingface.co/spaces/alice/t. (ftp://x)';
    const { container } = render(<pre>{withLinks(text)}</pre>);
    const links = screen.getAllByRole('link');
    expect(links.map((a) => a.getAttribute('href'))).toEqual([
      'http://127.0.0.1:7860/?project=pick',
      'https://huggingface.co/spaces/alice/t',
    ]);
    expect(links[0]).toHaveAttribute('target', '_blank');
    expect(links[0]).toHaveAttribute('rel', 'noopener noreferrer');
    expect(container.textContent).toBe(text);
  });

  it('leaves text without addresses as it is', () => {
    expect(withLinks('no address here')).toEqual(['no address here']);
  });
});
