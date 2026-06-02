import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import DataTable, { DataTableProps } from './DataTable';

interface TestItem extends Record<string, unknown> {
  id: string;
  name: string;
  status: string;
}

const ITEMS: TestItem[] = [
  { id: '1', name: 'Alpha', status: 'active' },
  { id: '2', name: 'Beta', status: 'draft' },
  { id: '3', name: 'Gamma', status: 'active' },
];

const COLUMNS: DataTableProps<TestItem>['columnDefinitions'] = [
  { id: 'id', header: 'ID', cell: (item) => item.id, sortingField: 'id' },
  { id: 'name', header: 'Name', cell: (item) => item.name, sortingField: 'name' },
  { id: 'status', header: 'Status', cell: (item) => item.status, sortingField: 'status' },
];

function renderTable(overrides: Partial<DataTableProps<TestItem>> = {}) {
  return render(
    <DataTable<TestItem>
      items={ITEMS}
      columnDefinitions={COLUMNS}
      trackBy="id"
      {...overrides}
    />,
  );
}

describe('DataTable', () => {
  it('renders items in the table', () => {
    renderTable();
    expect(screen.getByText('Alpha')).toBeInTheDocument();
    expect(screen.getByText('Beta')).toBeInTheDocument();
    expect(screen.getByText('Gamma')).toBeInTheDocument();
  });

  it('filters items by text', () => {
    renderTable({ filteringPlaceholder: 'Search items' });

    const filterInput = screen.getByPlaceholderText('Search items');
    fireEvent.change(filterInput, { target: { value: 'Alpha' } });

    expect(screen.getByText('Alpha')).toBeInTheDocument();
    expect(screen.queryByText('Beta')).not.toBeInTheDocument();
    expect(screen.queryByText('Gamma')).not.toBeInTheDocument();
  });

  it('renders pagination controls', () => {
    // Create enough items to trigger pagination with pageSize=2
    const manyItems: TestItem[] = Array.from({ length: 5 }, (_, i) => ({
      id: String(i + 1),
      name: `Item ${i + 1}`,
      status: 'active',
    }));

    renderTable({ items: manyItems, pageSize: 2 });

    // Cloudscape pagination renders page number buttons
    expect(screen.getByRole('button', { name: '1' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '2' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '3' })).toBeInTheDocument();
  });

  it('sorts items when clicking column header', () => {
    renderTable();

    // Click the Name column header to sort
    const nameHeader = screen.getByText('Name');
    fireEvent.click(nameHeader);

    // After first click (ascending), Alpha should come first
    const cells = screen.getAllByRole('cell');
    const nameValues = cells
      .map((c) => c.textContent)
      .filter((t) => ['Alpha', 'Beta', 'Gamma'].includes(t ?? ''));
    expect(nameValues).toEqual(['Alpha', 'Beta', 'Gamma']);
  });

  it('displays loading state', () => {
    renderTable({ loading: true, loadingText: 'Fetching data…' });
    expect(screen.getByText('Fetching data…')).toBeInTheDocument();
  });

  it('displays empty state when no items', () => {
    renderTable({ items: [], empty: 'Nothing here.' });
    expect(screen.getByText('Nothing here.')).toBeInTheDocument();
  });

  it('fires onRowClick callback', () => {
    const handleClick = vi.fn();
    renderTable({ onRowClick: handleClick });

    // Click on a row cell
    fireEvent.click(screen.getByText('Alpha'));

    expect(handleClick).toHaveBeenCalledTimes(1);
    expect(handleClick).toHaveBeenCalledWith(
      expect.objectContaining({ id: '1', name: 'Alpha' }),
    );
  });

  it('renders custom header', () => {
    renderTable({ header: <h2>My Table</h2> });
    expect(screen.getByText('My Table')).toBeInTheDocument();
  });
});
