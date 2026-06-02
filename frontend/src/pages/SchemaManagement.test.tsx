import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import SchemaManagement from './SchemaManagement';

vi.mock('../services/api', () => ({
  inferSchema: vi.fn(),
  registerSchema: vi.fn(),
}));

import { inferSchema, registerSchema } from '../services/api';
const mockInferSchema = vi.mocked(inferSchema);
const mockRegisterSchema = vi.mocked(registerSchema);

function renderPage() {
  return render(
    <MemoryRouter>
      <SchemaManagement />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe('SchemaManagement', () => {
  it('renders page header and tabs', () => {
    renderPage();
    expect(screen.getByText('Schema Management')).toBeInTheDocument();
    expect(screen.getByText('Infer from Sample')).toBeInTheDocument();
    expect(screen.getByText('Manual Definition')).toBeInTheDocument();
  });

  it('renders file upload and infer button on infer tab', () => {
    renderPage();
    expect(screen.getByTestId('file-upload')).toBeInTheDocument();
    expect(screen.getByText('Infer Schema')).toBeInTheDocument();
  });

  it('disables infer button when no file is selected', () => {
    renderPage();
    const btn = screen.getByText('Infer Schema').closest('button')!;
    expect(btn).toBeDisabled();
  });

  it('calls inferSchema and displays inferred fields on success', async () => {
    mockInferSchema.mockResolvedValueOnce({
      schemaId: 'test-schema',
      fields: [
        { name: 'batch_id', type: 'string', nullable: false, constraints: 'unique' },
        { name: 'quantity', type: 'double', nullable: true, constraints: '' },
      ],
      sourceFile: 'sample.csv',
      inferredAt: '2024-01-01T00:00:00Z',
    });

    renderPage();

    const fileInput = screen.getByTestId('file-upload');
    const file = new File(['col1,col2\na,1'], 'sample.csv', { type: 'text/csv' });
    fireEvent.change(fileInput, { target: { files: [file] } });

    fireEvent.click(screen.getByText('Infer Schema'));

    await waitFor(() => {
      expect(mockInferSchema).toHaveBeenCalledWith(file);
      expect(screen.getByText('batch_id')).toBeInTheDocument();
      expect(screen.getByText('quantity')).toBeInTheDocument();
    });

    // Approve button should appear
    expect(screen.getByText('Approve & Register Schema')).toBeInTheDocument();
  });

  it('shows error alert when inference fails', async () => {
    mockInferSchema.mockRejectedValueOnce(new Error('Unsupported file format'));

    renderPage();

    const fileInput = screen.getByTestId('file-upload');
    const file = new File(['bad'], 'bad.txt', { type: 'text/plain' });
    fireEvent.change(fileInput, { target: { files: [file] } });

    fireEvent.click(screen.getByText('Infer Schema'));

    await waitFor(() => {
      expect(screen.getByText('Schema inference failed')).toBeInTheDocument();
      expect(screen.getByText(/Unsupported file format/)).toBeInTheDocument();
      // Verify the error message suggests manual definition
      expect(screen.getByText(/define the schema by hand/)).toBeInTheDocument();
    });
  });

  it('shows loading indicator during inference', async () => {
    let resolveInfer!: (v: unknown) => void;
    mockInferSchema.mockReturnValueOnce(
      new Promise((resolve) => { resolveInfer = resolve; }) as ReturnType<typeof inferSchema>,
    );

    renderPage();

    const fileInput = screen.getByTestId('file-upload');
    const file = new File(['a,b'], 'data.csv', { type: 'text/csv' });
    fireEvent.change(fileInput, { target: { files: [file] } });
    fireEvent.click(screen.getByText('Infer Schema'));

    await waitFor(() => {
      expect(screen.getByText('Analyzing file…')).toBeInTheDocument();
    });

    resolveInfer({
      schemaId: 's',
      fields: [{ name: 'a', type: 'string', nullable: true }],
      sourceFile: 'data.csv',
      inferredAt: '',
    });

    await waitFor(() => {
      expect(screen.queryByText('Analyzing file…')).not.toBeInTheDocument();
    });
  });

  it('registers schema on approve and shows success flash', async () => {
    mockInferSchema.mockResolvedValueOnce({
      schemaId: 'my-schema',
      fields: [{ name: 'id', type: 'string', nullable: false }],
      sourceFile: 'f.csv',
      inferredAt: '',
    });
    mockRegisterSchema.mockResolvedValueOnce({
      schemaId: 'schema-001',
      schemaName: 'my-schema',
      version: '1.0',
      registeredAt: '2024-01-01T00:00:00Z',
    });

    renderPage();

    // Infer first
    const fileInput = screen.getByTestId('file-upload');
    fireEvent.change(fileInput, { target: { files: [new File(['x'], 'f.csv', { type: 'text/csv' })] } });
    fireEvent.click(screen.getByText('Infer Schema'));

    await waitFor(() => expect(screen.getByText('id')).toBeInTheDocument());

    // Approve
    fireEvent.click(screen.getByText('Approve & Register Schema'));

    await waitFor(() => {
      expect(mockRegisterSchema).toHaveBeenCalledWith({
        schemaName: 'my-schema',
        fields: [{ name: 'id', type: 'string', nullable: false }],
        dataFormat: 'json',
      });
      expect(screen.getByText(/registered as version 1.0/)).toBeInTheDocument();
    });
  });

  it('shows error flash when registration fails', async () => {
    mockInferSchema.mockResolvedValueOnce({
      schemaId: 'my-schema',
      fields: [{ name: 'id', type: 'string', nullable: false }],
      sourceFile: 'f.csv',
      inferredAt: '',
    });
    mockRegisterSchema.mockRejectedValueOnce(new Error('Duplicate schema'));

    renderPage();

    const fileInput = screen.getByTestId('file-upload');
    fireEvent.change(fileInput, { target: { files: [new File(['x'], 'f.csv', { type: 'text/csv' })] } });
    fireEvent.click(screen.getByText('Infer Schema'));
    await waitFor(() => expect(screen.getByText('id')).toBeInTheDocument());

    fireEvent.click(screen.getByText('Approve & Register Schema'));

    await waitFor(() => {
      expect(screen.getByText(/Schema registration failed: Duplicate schema/)).toBeInTheDocument();
    });
  });

  it('allows switching to manual definition tab and adding fields', async () => {
    renderPage();

    // Switch to manual tab
    fireEvent.click(screen.getByText('Manual Definition'));

    await waitFor(() => {
      expect(screen.getByText('Manual Schema Definition')).toBeInTheDocument();
    });

    // Should show the Add field button
    const addBtn = screen.getByText('Add field');
    expect(addBtn).toBeInTheDocument();

    // Add a field and verify the schema fields header counter updates
    fireEvent.click(addBtn);

    await waitFor(() => {
      expect(screen.getByText('(1)')).toBeInTheDocument();
    });
  });
});
