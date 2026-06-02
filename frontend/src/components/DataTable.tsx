import { ReactNode } from 'react';
import { useCollection } from '@cloudscape-design/collection-hooks';
import Box from '@cloudscape-design/components/box';
import Pagination from '@cloudscape-design/components/pagination';
import Table, { TableProps } from '@cloudscape-design/components/table';
import TextFilter from '@cloudscape-design/components/text-filter';

export interface DataTableProps<T> {
  items: T[];
  columnDefinitions: TableProps.ColumnDefinition<T>[];
  trackBy: string;
  filteringPlaceholder?: string;
  pageSize?: number;
  header?: ReactNode;
  loading?: boolean;
  loadingText?: string;
  empty?: string;
  noMatch?: string;
  onRowClick?: (item: T) => void;
  variant?: TableProps['variant'];
  stickyHeader?: boolean;
}

export default function DataTable<T extends Record<string, unknown>>({
  items,
  columnDefinitions,
  trackBy,
  filteringPlaceholder = 'Find items',
  pageSize = 10,
  header,
  loading = false,
  loadingText = 'Loading…',
  empty = 'No items found.',
  noMatch = 'No items match the filter.',
  onRowClick,
  variant,
  stickyHeader,
}: DataTableProps<T>) {
  const {
    items: collectionItems,
    filteredItemsCount,
    collectionProps,
    filterProps,
    paginationProps,
  } = useCollection(items, {
    filtering: { empty, noMatch },
    pagination: { pageSize },
    sorting: { defaultState: { sortingColumn: columnDefinitions[0] } },
  });

  return (
    <Table
      {...collectionProps}
      columnDefinitions={columnDefinitions}
      items={collectionItems}
      loading={loading}
      loadingText={loadingText}
      trackBy={trackBy}
      variant={variant}
      stickyHeader={stickyHeader}
      header={header}
      filter={
        <TextFilter
          {...filterProps}
          filteringPlaceholder={filteringPlaceholder}
          countText={`${filteredItemsCount ?? 0} match(es)`}
        />
      }
      pagination={<Pagination {...paginationProps} />}
      onRowClick={
        onRowClick
          ? ({ detail }) => onRowClick(detail.item)
          : undefined
      }
      empty={
        <Box textAlign="center" padding="l">
          {empty}
        </Box>
      }
    />
  );
}
