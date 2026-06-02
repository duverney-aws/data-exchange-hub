import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import CMORegistration from './CMORegistration';

/* Stub the API module so no real fetch calls are made */
vi.mock('../services/api', () => ({
  registerCMO: vi.fn(),
}));

import { registerCMO } from '../services/api';
const mockRegisterCMO = vi.mocked(registerCMO);

function renderPage() {
  return render(
    <MemoryRouter>
      <CMORegistration />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe('CMORegistration', () => {
  it('renders all required form fields', () => {
    renderPage();
    expect(screen.getByText('Organization Name')).toBeInTheDocument();
    expect(screen.getByText('Contact Email')).toBeInTheDocument();
    expect(screen.getByText('Contact Phone')).toBeInTheDocument();
    expect(screen.getByText('Address')).toBeInTheDocument();
    expect(screen.getByText('This organization is GxP certified')).toBeInTheDocument();
    expect(screen.getByText('Register CMO')).toBeInTheDocument();
  });

  it('shows validation errors when submitting empty form', async () => {
    renderPage();
    fireEvent.click(screen.getByText('Register CMO'));

    await waitFor(() => {
      expect(screen.getByText('Organization name is required.')).toBeInTheDocument();
      expect(screen.getByText('Contact email is required.')).toBeInTheDocument();
      expect(screen.getByText('Contact phone is required.')).toBeInTheDocument();
      expect(screen.getByText('Address is required.')).toBeInTheDocument();
    });

    expect(mockRegisterCMO).not.toHaveBeenCalled();
  });

  it('shows email format error for invalid email', async () => {
    renderPage();

    const inputs = screen.getAllByRole('textbox');
    // Fill all fields but use invalid email
    fireEvent.change(inputs[0], { target: { value: 'Acme Pharma' } });
    fireEvent.change(inputs[1], { target: { value: 'not-an-email' } });
    fireEvent.change(inputs[2], { target: { value: '+1-555-000-0000' } });
    fireEvent.change(inputs[3], { target: { value: '123 Main St' } });

    fireEvent.click(screen.getByText('Register CMO'));

    await waitFor(() => {
      expect(screen.getByText('Enter a valid email address.')).toBeInTheDocument();
    });

    expect(mockRegisterCMO).not.toHaveBeenCalled();
  });

  it('shows success message on successful registration', async () => {
    mockRegisterCMO.mockResolvedValueOnce({
      cmoId: 'cmo-acme',
      organizationName: 'Acme Pharma',
      contactEmail: 'admin@acme.com',
      contactPhone: '+1-555-000-0000',
      address: '123 Main St',
      gxpCertified: true,
      createdAt: '2024-01-01T00:00:00Z',
      status: 'active',
    });

    renderPage();

    const inputs = screen.getAllByRole('textbox');
    fireEvent.change(inputs[0], { target: { value: 'Acme Pharma' } });
    fireEvent.change(inputs[1], { target: { value: 'admin@acme.com' } });
    fireEvent.change(inputs[2], { target: { value: '+1-555-000-0000' } });
    fireEvent.change(inputs[3], { target: { value: '123 Main St' } });

    fireEvent.click(screen.getByText('Register CMO'));

    await waitFor(() => {
      expect(screen.getByText(/CMO registered successfully/)).toBeInTheDocument();
      expect(screen.getByText(/cmo-acme/)).toBeInTheDocument();
    });
  });

  it('shows error message on failed registration', async () => {
    mockRegisterCMO.mockRejectedValueOnce(new Error('Organization already exists'));

    renderPage();

    const inputs = screen.getAllByRole('textbox');
    fireEvent.change(inputs[0], { target: { value: 'Acme Pharma' } });
    fireEvent.change(inputs[1], { target: { value: 'admin@acme.com' } });
    fireEvent.change(inputs[2], { target: { value: '+1-555-000-0000' } });
    fireEvent.change(inputs[3], { target: { value: '123 Main St' } });

    fireEvent.click(screen.getByText('Register CMO'));

    await waitFor(() => {
      expect(screen.getByText(/Registration failed: Organization already exists/)).toBeInTheDocument();
    });
  });
});
