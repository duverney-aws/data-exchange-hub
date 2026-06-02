import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useCollection } from '@cloudscape-design/collection-hooks';
import Badge from '@cloudscape-design/components/badge';
import Box from '@cloudscape-design/components/box';
import Button from '@cloudscape-design/components/button';
import ColumnLayout from '@cloudscape-design/components/column-layout';
import Container from '@cloudscape-design/components/container';
import Flashbar, { FlashbarProps } from '@cloudscape-design/components/flashbar';
import Header from '@cloudscape-design/components/header';
import Pagination from '@cloudscape-design/components/pagination';
import Select from '@cloudscape-design/components/select';
import SpaceBetween from '@cloudscape-design/components/space-between';
import StatusIndicator from '@cloudscape-design/components/status-indicator';
import Table from '@cloudscape-design/components/table';
import TextFilter from '@cloudscape-design/components/text-filter';
import { useAuth } from '../context/AuthContext';
import {
  Batch, listBatches, listCMOs, CMOProfile, listProducts, Product,
  listContracts, DataContract, runSlaCheck,
} from '../services/api';

const ELEMENT_LABELS: Record<string, string> = {
  bmr: 'BMR', coa: 'CoA', in_process: 'In-Process', yield: 'Yield',
};

export default function Dashboard() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const isMerck = user?.isMerckAdmin ?? false;

  const [batches, setBatches] = useState<Batch[]>([]);
  const [cmos, setCmos] = useState<CMOProfile[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [contracts, setContracts] = useState<DataContract[]>([]);
  const [loading, setLoading] = useState(true);
  const [checking, setChecking] = useState(false);
  const [flash, setFlash] = useState<FlashbarProps.MessageDefinition[]>([]);
  const [cmoFilter, setCmoFilter] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<string | null>(null);

  const load = () => {
    setLoading(true);
    const params = cmoFilter ? { cmoId: cmoFilter } : undefined;
    listBatches(params)
      .then(setBatches)
      .catch((e: Error) => setFlash([{ type: 'error', dismissible: true, onDismiss: () => setFlash([]), content: e.message }]))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
    if (isMerck) listCMOs().then(setCmos).catch(() => {});
    listProducts().then(setProducts).catch(() => {});
    listContracts().then(setContracts).catch(() => {});
  }, [cmoFilter]);

  const productMap = Object.fromEntries(products.map((p) => [p.productId, p.productName]));
  const cmoMap = Object.fromEntries(cmos.map((c) => [c.cmoId, c.organizationName]));

  // Stats
  const totalBatches = batches.length;
  const overdueCount = batches.filter((b) => b.dataElements?.some((e) => e.overdue)).length;
  const incompleteCount = batches.filter((b) => (b.missingElements?.length ?? 0) > 0).length;
  const activeContracts = contracts.filter((c) => c.status === 'active').length;

  // Filtered view
  const displayBatches = statusFilter === 'overdue'
    ? batches.filter((b) => b.dataElements?.some((e) => e.overdue))
    : statusFilter === 'missing'
      ? batches.filter((b) => (b.missingElements?.length ?? 0) > 0)
      : batches;

  const columns = [
    { id: 'lotNumber', header: 'Lot Number', cell: (i: Batch) => i.lotNumber, sortingField: 'lotNumber' },
    ...(isMerck ? [{ id: 'cmoId', header: 'CMO', cell: (i: Batch) => cmoMap[i.cmoId] ?? i.cmoId, sortingField: 'cmoId' }] : []),
    { id: 'productId', header: 'Product', cell: (i: Batch) => productMap[i.productId] ?? i.productId, sortingField: 'productId' },
    { id: 'manufacturingDate', header: 'Mfg Date', cell: (i: Batch) => i.manufacturingDate, sortingField: 'manufacturingDate' },
    {
      id: 'completeness', header: 'Completeness',
      cell: (i: Batch) => {
        const total = 4;
        const received = total - (i.missingElements?.length ?? 0);
        const color = received === total ? 'green' : received === 0 ? 'red' : 'blue';
        return <Badge color={color}>{received}/{total}</Badge>;
      },
    },
    {
      id: 'overdue', header: 'Overdue',
      cell: (i: Batch) => {
        const overdueEls = (i.dataElements ?? []).filter((e) => e.overdue);
        if (overdueEls.length === 0) return <StatusIndicator type="success">None</StatusIndicator>;
        return (
          <StatusIndicator type="error">
            {overdueEls.map((e) => ELEMENT_LABELS[e.elementType] ?? e.elementType).join(', ')}
          </StatusIndicator>
        );
      },
    },
    {
      id: 'missing', header: 'Missing',
      cell: (i: Batch) => {
        const missing = i.missingElements ?? [];
        if (missing.length === 0) return <Box color="text-status-success">All received</Box>;
        return missing.map((e) => ELEMENT_LABELS[e] ?? e).join(', ');
      },
    },
  ];

  const { items, filteredItemsCount, collectionProps, filterProps, paginationProps } =
    useCollection(displayBatches, {
      filtering: { empty: 'No batches found.', noMatch: 'No matches.' },
      pagination: { pageSize: 10 },
      sorting: { defaultState: { sortingColumn: columns[isMerck ? 4 : 3], isDescending: true } },
    });

  const handleSlaCheck = async () => {
    setChecking(true);
    try {
      const result = await runSlaCheck();
      setFlash([{ type: 'success', dismissible: true, onDismiss: () => setFlash([]), content: `SLA check complete: ${result.checked} batches checked, ${result.flagged} elements flagged overdue.` }]);
      load();
    } catch (e: unknown) {
      setFlash([{ type: 'error', dismissible: true, onDismiss: () => setFlash([]), content: (e as Error).message }]);
    } finally {
      setChecking(false);
    }
  };

  const cmoOptions = [{ label: 'All CMOs', value: '' }, ...cmos.map((c) => ({ label: c.organizationName, value: c.cmoId }))];
  const statusOptions = [
    { label: 'All Batches', value: '' },
    { label: 'Has Overdue Elements', value: 'overdue' },
    { label: 'Has Missing Elements', value: 'missing' },
  ];

  return (
    <SpaceBetween size="l">
      <Flashbar items={flash} />
      <Header variant="h1" description={isMerck ? 'Cross-CMO batch completeness and SLA tracking' : 'Your batch submission status and SLA tracking'}>
        Dashboard
      </Header>

      {/* Summary cards */}
      <ColumnLayout columns={4} variant="text-grid">
        <Container>
          <Box variant="awsui-key-label">Active Contracts</Box>
          <Box variant="awsui-value-large">{activeContracts}</Box>
        </Container>
        <Container>
          <Box variant="awsui-key-label">Total Batches</Box>
          <Box variant="awsui-value-large">{totalBatches}</Box>
        </Container>
        <Container>
          <Box variant="awsui-key-label">Incomplete</Box>
          <Box variant="awsui-value-large" color={incompleteCount > 0 ? 'text-status-warning' : undefined}>{incompleteCount}</Box>
        </Container>
        <Container>
          <Box variant="awsui-key-label">Overdue</Box>
          <Box variant="awsui-value-large" color={overdueCount > 0 ? 'text-status-error' : undefined}>{overdueCount}</Box>
        </Container>
      </ColumnLayout>

      {/* Batch completeness table */}
      <Table
        {...collectionProps}
        columnDefinitions={columns}
        items={items}
        loading={loading}
        loadingText="Loading batches…"
        trackBy="batchId"
        stickyHeader
        header={
          <Header
            variant="h2"
            counter={`(${displayBatches.length})`}
            actions={
              <SpaceBetween direction="horizontal" size="xs">
                {isMerck && (
                  <Select
                    selectedOption={cmoOptions.find((o) => o.value === (cmoFilter ?? '')) ?? cmoOptions[0]}
                    onChange={({ detail }) => setCmoFilter(detail.selectedOption.value || null)}
                    options={cmoOptions}
                  />
                )}
                <Select
                  selectedOption={statusOptions.find((o) => o.value === (statusFilter ?? '')) ?? statusOptions[0]}
                  onChange={({ detail }) => setStatusFilter(detail.selectedOption.value || null)}
                  options={statusOptions}
                />
                {isMerck && <Button iconName="refresh" loading={checking} onClick={handleSlaCheck}>Run SLA Check</Button>}
              </SpaceBetween>
            }
          >
            Batch Completeness
          </Header>
        }
        filter={<TextFilter {...filterProps} filteringPlaceholder="Search batches" countText={`${filteredItemsCount ?? 0} match(es)`} />}
        pagination={<Pagination {...paginationProps} />}
        onRowClick={({ detail }) => navigate(`/batches/${detail.item.batchId}`)}
      />
    </SpaceBetween>
  );
}
