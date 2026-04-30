import { describe, expect, it } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { KnowMoreButton } from './KnowMoreButton';

describe('KnowMoreButton + KnowMoreModal', () => {
  it('opens the modal with the explainer title when clicked', () => {
    render(<KnowMoreButton id="system-size" />);
    fireEvent.click(screen.getByRole('button', { name: /know more/i }));
    expect(
      screen.getByRole('dialog', { name: /how is the panel count calculated/i }),
    ).toBeInTheDocument();
  });

  it('closes the modal when Escape is pressed', () => {
    render(<KnowMoreButton id="system-size" />);
    fireEvent.click(screen.getByRole('button', { name: /know more/i }));
    expect(screen.getByRole('dialog')).toBeInTheDocument();
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('renders a not-found dialog when the id is missing from the registry', () => {
    render(<KnowMoreButton id="does-not-exist" />);
    fireEvent.click(screen.getByRole('button', { name: /know more/i }));
    expect(screen.getByText(/explainer not found/i)).toBeInTheDocument();
  });
});
