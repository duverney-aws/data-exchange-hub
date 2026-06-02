import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import Pipelines from './Pipelines';

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return { ...actual, useNavigate: () => mockNavigate };
});

vi.mock('../services/api', () => ({
  listContracts: vi.fn(),
  getPipelineStatus: vi.fn(),
}));

import { listContracts, getPipelineStatus } from '../services/api';
const mockListContracts = vi.mocked(listContracts);
const mockGetPipelineStatus = vi.mocked(getPipelineStatus);

function renderPage() {
  return render(
    <MemoryRouter>
      <Pipelines />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
});

const CONTRACT_DRAFT = {
  contractId: 'CMO-ALPHA-BATCH-001',
  cmoId: 'cmo-alpha',
  dataDomain: 'batch-records',
  schemaId: 's1',
  schemaVersion: '1.0',
  qualityRules: [],
  sla: { timeliness: { maxDelayHours: 24, measurementWindow: 'daily' }, availability: { uptimePercentage: 99.5, measurementWindow: 'monthly' }, quality: { minQualityScore: 95, measurementWindow: 'daily' } },
  deliverySchedule: { frequency: 'daily' as const, timezone: 'UTC' },
  governance: { dataClassification: 'internal' as const, retentionYears: 7, allowedUsers: [], allowedGroups: [], piiFields: [], encryptionRequired: true },
  status: 'draft' as const,
  createdAt: '2024-01-15T00:00:00Z',
  updatedAt: '2024-01-15T00:00:00Z',
};

const CONTRACT_ACTIVE = {
  ...CONTRACT_DRAFT,
  contractId: 'CMO-BETA-QUALITY-002',
  cmoId: 'cmo-beta',
  dataDomain: 'quality-data',
  status: 'active' as const,
};

describe('Pipelines', () => {
  it('shows loading state while fetching', () => {
    mockListContracts.mockReturnValue(new Promise(() => {}));
    renderPage();
    expect(screen.getByText('Loading pipelines…')).toBeInTheDocument();
  });

  it('renders pipeline list with correct statuses', async () => {
    mockListContracts.mockResolvedValueOnce([CONTRACT_DRAFT, CONTRACT_ACTIVE]);
    mockGetPipelineStatus.mockImplementation(async (id) => {
      if (id === CONTRACT_DRAFT.contractId) {
        return { contractId: id, status: 'draft' };
      }
      return { contractId: id, status: 'active', integrationPattern: 'secure-transfer' };
    });

    renderPage();

    await waitFor(() => {
      expect(screen.getByText('CMO-ALPHA-BATCH-001')).toBeInTheDocument();
      expect(screen.getByText('CMO-BETA-QUALITY-002')).toBeInTheDocument();
    });

    expect(screen.getByText('Draft')).toBeInTheDocument();
    expect(screen.getByText('Active')).toBeInTheDocument();
    expect(screen.getByText('Secure Transfer (SFTP)')).toBeInTheDocument();
  });

  it('shows Activate button for draft contracts and navigates on click', async () => {
    mockListContracts.mockResolvedValueOnce([CONTRACT_DRAFT]);
    mockGetPipelineStatus.mockResolvedValueOnce({ contractId: CONTRACT_DRAFT.contractId, status: 'draft' });

    renderPage();

    await waitFor(() => {
      expect(screen.getByText('CMO-ALPHA-BATCH-001')).toBeInTheDocument();
    });

    const activateBtn = screen.getByRole('button', { name: 'Activate' });
    expect(activateBtn).toBeInTheDocument();
    fireEvent.click(activateBtn);
    expect(mockNavigate).toHaveBeenCalledWith('/integration-patterns?contractId=CMO-ALPHA-BATCH-001');
  });

  it('displays error alert with actionable guidance for failed pipelines', async () => {
    mockListContracts.mockResolvedValueOnce([CONTRACT_ACTIVE]);
    mockGetPipelineStatus.mockResolvedValueOnce({
      contractId: CONTRACT_ACTIVE.contractId,
      status: 'failed',
      errorMessage: 'Connection credential invalid',
    });

    renderPage();

    await waitFor(() => {
      expect(screen.getByText('Failed')).toBeInTheDocument();
    });

    // Expand details
    fireEvent.click(screen.getByRole('button', { name: 'View Details' }));

    await waitFor(() => {
      expect(screen.getByText('Pipeline Deployment Failed')).toBeInTheDocument();
      expect(screen.getByText(/Verify your connection credentials/)).toBeInTheDocument();
    });
  });

  it('shows error flashbar when API call fails', async () => {
    mockListContracts.mockRejectedValueOnce(new Error('Network error'));
    renderPage();

    await waitFor(() => {
      expect(screen.getByText(/Failed to load pipelines: Network error/)).toBeInTheDocument();
    });
  });

  it('displays connection details when available', async () => {
    mockListContracts.mockResolvedValueOnce([CONTRACT_ACTIVE]);
    mockGetPipelineStatus.mockResolvedValueOnce({
      contractId: CONTRACT_ACTIVE.contractId,
      status: 'active',
      integrationPattern: 'secure-transfer',
      connectionDetails: { hostname: 'sftp.example.com', username: 'cmo-beta-user' },
    });

    renderPage();

    await waitFor(() => {
      expect(screen.getByText('CMO-BETA-QUALITY-002')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: 'View Details' }));

    await waitFor(() => {
      expect(screen.getByText('Connection Details')).toBeInTheDocument();
      expect(screen.getByText(/sftp\.example\.com/)).toBeInTheDocument();
      expect(screen.getByText(/cmo-beta-user/)).toBeInTheDocument();
    });
  });
});
