import { render } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { Icon } from './Icon';

describe('Icon', () => {
  it('draws the services with their own logos and colors', () => {
    const { container } = render(
      <>
        <Icon name="huggingface" />
        <Icon name="train" />
      </>,
    );
    const [hf, train] = Array.from(container.querySelectorAll('svg'));
    expect(hf).toHaveClass('ico', 'logo');
    expect(hf).toHaveAttribute('viewBox', '0 0 95 88');
    expect(hf!.querySelector('path')).toHaveAttribute('fill', '#FFD21E');
    expect(train).not.toHaveClass('logo'); // the others are line icons in the text color
  });
});
