import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import DataContracts from './DataContracts';

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return { ...actual, useNavigate: () => mockNavigate };
});

vi.mock('../services/api', () => ({
  listContracts: vi.fn(),
}));

import { listContracts } from '../services/api';
const mockListContracts = vi.mocked(listContracts);

function renderPage() {
  return render(
    <MemoryRouter>
      <DataContracts />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
});

const SAMPLE_CONTRACTS = [
  {
    contractId: 'CMO-ALPHA-BATCH-001',
    cmoId: 'cmo-alpha',
    dataDomain: 'batch-records',
    schemaId: 'schema-1',
    schemaVersion: '1.0',
    qualityRules: [],
    sla: { timeliness: { maxDelayHours: 24, measurementWindow: 'daily' }, availability: { uptimePercentage: 99.5, measurementWindow: 'monthly' }, quality: { minQualityScore: 95, measurementWindow: 'daily' } },
    deliverySchedule: { frequency: 'daily' as const, timezone: 'UTC' },
    governance: { dataClassification: 'internal' as const, retentionYears: 7, allowedUsers: [], allowedGroups: [], piiFields: [], encryptionRequired: true },
    status: 'draft' as const,
    createdAt: '2024-01-15T00:00:00Z',
    updatedAt: '2024-01-15T00:00:00Z',
  },
  {
    contractId: 'CMO-BETA-QUALITY-002',
    cmoId: 'cmo-beta',
    dataDomain: 'quality-data',
    schemaId: 'schema-2',
    schemaVersion: '2.0',
    qualityRules: [],
    sla: { timeliness: { maxDelayHours: 12, measurementWindow: 'daily' }, availability: { uptimePercentage: 99, measurementWindow: 'monthly' }, quality: { minQualityScore: 90, measurementWindow: 'daily' } },
    deliverySchedule: { frequency: 'hourly' as const, timezone: 'UTC' },
    governance: { dataClassification: 'confidential' as const, retentionYears: 10, allowedUsers: [], allowedGroups: [], piiFields: [], encryptionRequired: true },
    status: 'active' as const,
    createdAt: '2024-02-01T00:00:00Z',
    updatedAt: '2024-02-01T00:00:00Z',
  },
];

describe('DataContracts', () => {
  it('renders table with contract data', async () => {
    mockListContracts.mockResolvedValueOnce(SAMPLE_CONTRACTS);
    renderPage();

    await waitFor(() => {
      expect(screen.getByText('CMO-ALPHA-BATCH-001')).toBeInTheDocument();
      expect(screen.getByText('CMO-BETA-QUALITY-002')).toBeInTheDocument();
    });

    expect(screen.getByText('cmo-alpha')).toBeInTheDocument();
    expect(screen.getByText('batch-records')).toBeInTheDocument();
    expect(screen.getByText('draft')).toBeInTheDocument();
    expect(screen.getByText('active')).toBeInTheDocument();
  });

  it('shows loading state', () => {
    mockListContracts.mockReturnValue(new Promise(() => {})); // never resolves
    renderPage();
    expect(screen.getByText('Loading contracts…')).toBeInTheDocument();
  });

  it('shows error state when API fails', async () => {
    mockListContracts.mockRejectedValueOnce(new Error('Network error'));
    renderPage();

    await waitFor(() => {
      expect(screen.getByText(/Failed to load contracts: Network error/)).toBeInTheDocument();
    });
  });

  it('filters contracts by text', async () => {
    mockListContracts.mockResolvedValueOnce(SAMPLE_CONTRACTS);
    renderPage();

    await waitFor(() => {
      expect(screen.getByText('CMO-ALPHA-BATCH-001')).toBeInTheDocument();
    });

    const filterInput = screen.getByPlaceholderText('Find contracts');
    fireEvent.change(filterInput, { target: { value: 'BETA' } });

    await waitFor(() => {
      expect(screen.queryByText('CMO-ALPHA-BATCH-001')).not.toBeInTheDocument();
      expect(screen.getByText('CMO-BETA-QUALITY-002')).toBeInTheDocument();
    });
  });

  it('navigates to create page when Create Contract is clicked', async () => {
    mockListContracts.mockResolvedValueOnce([]);
    renderPage();

    await waitFor(() => {
      expect(screen.queryByText('Loading contracts…')).not.toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('Create Contract'));
    expect(mockNavigate).toHaveBeenCalledWith('/data-contracts/create');
  });
});
