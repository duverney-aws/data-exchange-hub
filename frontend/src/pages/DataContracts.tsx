import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useCollection } from '@cloudscape-design/collection-hooks';
import Button from '@cloudscape-design/components/button';
import Flashbar, { FlashbarProps } from '@cloudscape-design/components/flashbar';
import Header from '@cloudscape-design/components/header';
import Pagination from '@cloudscape-design/components/pagination';
import SpaceBetween from '@cloudscape-design/components/space-between';
import Table from '@cloudscape-design/components/table';
import TextFilter from '@cloudscape-design/components/text-filter';
import { DataContract, listContracts } from '../services/api';

const COLUMN_DEFINITIONS = [
  {
    id: 'contractId',
    header: 'Contract ID',
    cell: (item: DataContract) => item.contractId,
    sortingField: 'contractId',
  },
  {
    id: 'cmoId',
    header: 'CMO ID',
    cell: (item: DataContract) => item.cmoId,
    sortingField: 'cmoId',
  },
  {
    id: 'dataDomain',
    header: 'Data Domain',
    cell: (item: DataContract) => item.dataDomain,
    sortingField: 'dataDomain',
  },
  {
    id: 'status',
    header: 'Status',
    cell: (item: DataContract) => item.status,
    sortingField: 'status',
  },
  {
    id: 'createdAt',
    header: 'Created At',
    cell: (item: DataContract) => item.createdAt,
    sortingField: 'createdAt',
  },
];

export default function DataContracts({ cmoId }: { cmoId?: string } = {}) {
  const navigate = useNavigate();
  const [contracts, setContracts] = useState<DataContract[]>([]);
  const [loading, setLoading] = useState(true);
  const [flashItems, setFlashItems] = useState<FlashbarProps.MessageDefinition[]>([]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    listContracts(cmoId)
      .then((data) => { if (!cancelled) setContracts(data); })
      .catch((err) => {
        if (!cancelled) {
          setFlashItems([{
            type: 'error',
            dismissible: true,
            onDismiss: () => setFlashItems([]),
            content: `Failed to load contracts: ${err instanceof Error ? err.message : 'Unknown error'}`,
          }]);
        }
      })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, []);

  const { items, filteredItemsCount, collectionProps, filterProps, paginationProps } =
    useCollection(contracts, {
      filtering: {
        empty: 'No contracts found.',
        noMatch: 'No contracts match the filter.',
      },
      pagination: { pageSize: 10 },
      sorting: { defaultState: { sortingColumn: COLUMN_DEFINITIONS[0] } },
    });

  return (
    <SpaceBetween size="l">
      <Flashbar items={flashItems} />
      <Table
        {...collectionProps}
        columnDefinitions={COLUMN_DEFINITIONS}
        items={items}
        loading={loading}
        loadingText="Loading contracts…"
        trackBy="contractId"
        variant="full-page"
        stickyHeader
        header={
          <Header
            variant="h1"
            description="Create and manage data contracts with schemas and quality rules"
            counter={`(${contracts.length})`}
            actions={
              <Button variant="primary" onClick={() => navigate('/data-contracts/create')}>
                Create Contract
              </Button>
            }
          >
            Data Contracts
          </Header>
        }
        filter={
          <TextFilter {...filterProps} filteringPlaceholder="Find contracts" countText={`${filteredItemsCount ?? 0} match(es)`} />
        }
        pagination={<Pagination {...paginationProps} />}
        onRowClick={({ detail }) => navigate(`/data-contracts/${detail.item.contractId}`)}
      />
    </SpaceBetween>
  );
}
