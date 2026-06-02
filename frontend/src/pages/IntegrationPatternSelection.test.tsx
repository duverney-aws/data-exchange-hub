import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import IntegrationPatternSelection from './IntegrationPatternSelection';

// Mock the api module
vi.mock('../services/api', () => ({
  activateContractPipeline: vi.fn(),
}));

import { activateContractPipeline } from '../services/api';
const mockActivate = vi.mocked(activateContractPipeline);

function renderPage(search = '') {
  return render(
    <MemoryRouter initialEntries={[`/integration-patterns${search}`]}>
      <IntegrationPatternSelection />
    </MemoryRouter>
  );
}

/**
 * Cloudscape Cards renders radio inputs. They are accessible but visually hidden.
 * We select by index: 0 = Pattern 1, 1 = Pattern 2, 2 = Pattern 3.
 */
async function selectPatternCard(user: ReturnType<typeof userEvent.setup>, index: number) {
  const radios = screen.getAllByRole('radio', { hidden: true });
  await user.click(radios[index]);
}

describe('IntegrationPatternSelection', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders the page header and all three pattern cards', () => {
    renderPage();
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(
      'Integration Pattern Selection'
    );
    expect(screen.getByText(/Pattern 1: Native Database Connectors/)).toBeInTheDocument();
    expect(screen.getByText(/Pattern 2: Secure File Transfer/)).toBeInTheDocument();
    expect(screen.getByText(/Pattern 3: AI-Powered Unstructured Data/)).toBeInTheDocument();
  });

  it('does not show any configuration form before a pattern is selected', () => {
    renderPage();
    expect(screen.queryByText('Native Connector Configuration')).not.toBeInTheDocument();
    expect(screen.queryByText('Secure File Transfer (SFTP)')).not.toBeInTheDocument();
    expect(screen.queryByText('AI Document Processing Configuration')).not.toBeInTheDocument();
  });

  it('shows Pattern 1 config form when native connector card is selected', async () => {
    renderPage();
    const user = userEvent.setup();
    await selectPatternCard(user, 0);

    expect(screen.getByText('Native Connector Configuration')).toBeInTheDocument();
    expect(screen.getByText('Connection URL')).toBeInTheDocument();
    expect(screen.getByText('Username')).toBeInTheDocument();
    expect(screen.getByText('Password')).toBeInTheDocument();
    expect(screen.getByText('Database')).toBeInTheDocument();
  });

  it('shows Pattern 2 SFTP info when secure transfer card is selected', async () => {
    renderPage();
    const user = userEvent.setup();
    await selectPatternCard(user, 1);

    expect(screen.getByText(/SFTP credentials will be provisioned automatically/)).toBeInTheDocument();
  });

  it('shows Pattern 3 document upload form when AI card is selected', async () => {
    renderPage();
    const user = userEvent.setup();
    await selectPatternCard(user, 2);

    expect(screen.getByText('AI Document Processing Configuration')).toBeInTheDocument();
    expect(screen.getByText('Document type')).toBeInTheDocument();
    expect(screen.getByText(/Confidence threshold/)).toBeInTheDocument();
    expect(screen.getByText('Upload documents')).toBeInTheDocument();
  });

  it('validates required fields for Pattern 1 before activation', async () => {
    renderPage('?contractId=CMO-ALPHA-BATCH-001');
    const user = userEvent.setup();

    await selectPatternCard(user, 0);

    // Click activate without filling fields
    await user.click(screen.getByRole('button', { name: /Activate Pipeline/ }));

    expect(screen.getByText('Connection URL is required.')).toBeInTheDocument();
    expect(screen.getByText('Username is required.')).toBeInTheDocument();
    expect(screen.getByText('Password is required.')).toBeInTheDocument();
    expect(screen.getByText('Database is required.')).toBeInTheDocument();
    expect(mockActivate).not.toHaveBeenCalled();
  });

  it('calls activateContractPipeline on successful Pattern 2 activation', async () => {
    mockActivate.mockResolvedValue({
      contractId: 'CMO-ALPHA-BATCH-001',
      status: 'deploying',
      sftpCredentials: {
        hostname: 'sftp.example.com',
        username: 'cmo-alpha',
        password: 'generated-pass',
      },
    });

    renderPage('?contractId=CMO-ALPHA-BATCH-001');
    const user = userEvent.setup();

    await selectPatternCard(user, 1);
    await user.click(screen.getByRole('button', { name: /Activate Pipeline/ }));

    expect(mockActivate).toHaveBeenCalledWith('CMO-ALPHA-BATCH-001', expect.objectContaining({
      integrationPattern: 'secure-transfer',
    }));

    // SFTP credentials should now be displayed
    expect(await screen.findByText('SFTP Connection Details')).toBeInTheDocument();
    expect(screen.getByDisplayValue('sftp.example.com')).toBeInTheDocument();
    expect(screen.getByDisplayValue('cmo-alpha')).toBeInTheDocument();
  });

  it('displays error flash message when activation fails', async () => {
    mockActivate.mockRejectedValue(new Error('Service unavailable'));

    renderPage('?contractId=CMO-ALPHA-BATCH-001');
    const user = userEvent.setup();

    await selectPatternCard(user, 2);
    await user.click(screen.getByRole('button', { name: /Activate Pipeline/ }));

    expect(await screen.findByText(/Pipeline activation failed: Service unavailable/)).toBeInTheDocument();
  });

  it('shows contract ID info alert when contractId is in URL', () => {
    renderPage('?contractId=CMO-BETA-QUALITY-002');
    expect(screen.getByText(/CMO-BETA-QUALITY-002/)).toBeInTheDocument();
  });
});
