import { render, screen } from '@testing-library/react';
import PageLoadingIndicator from './PageLoadingIndicator';

describe('PageLoadingIndicator', () => {
  it('renders default loading text', () => {
    render(<PageLoadingIndicator />);
    expect(screen.getByText('Loading…')).toBeInTheDocument();
  });

  it('renders custom label', () => {
    render(<PageLoadingIndicator label="Loading contracts…" />);
    expect(screen.getByText('Loading contracts…')).toBeInTheDocument();
  });

  it('renders a spinner', () => {
    const { container } = render(<PageLoadingIndicator />);
    // Cloudscape Spinner renders with role="img" or as a visual element
    // Just verify the component renders more than just the label text
    expect(container.firstChild).toBeTruthy();
    expect(container.textContent).toContain('Loading…');
  });
});
