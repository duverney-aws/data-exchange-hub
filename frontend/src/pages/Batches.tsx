import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useCollection } from '@cloudscape-design/collection-hooks';
import Badge from '@cloudscape-design/components/badge';
import Button from '@cloudscape-design/components/button';
import Flashbar, { FlashbarProps } from '@cloudscape-design/components/flashbar';
import Form from '@cloudscape-design/components/form';
import FormField from '@cloudscape-design/components/form-field';
import Header from '@cloudscape-design/components/header';
import Input from '@cloudscape-design/components/input';
import Modal from '@cloudscape-design/components/modal';
import Pagination from '@cloudscape-design/components/pagination';
import Select from '@cloudscape-design/components/select';
import SpaceBetween from '@cloudscape-design/components/space-between';
import StatusIndicator from '@cloudscape-design/components/status-indicator';
import Table from '@cloudscape-design/components/table';
import TextFilter from '@cloudscape-design/components/text-filter';
import { useAuth } from '../context/AuthContext';
import { Batch, listBatches, createBatch, listProducts, Product } from '../services/api';

const STATUS_MAP: Record<string, { type: 'success' | 'in-progress' | 'pending'; label: string }> = {
  in_progress: { type: 'in-progress', label: 'In Progress' },
  submitted:   { type: 'pending',     label: 'Submitted' },
  complete:    { type: 'success',     label: 'Complete' },
};

export default function Batches({ cmoId }: { cmoId?: string } = {}) {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [batches, setBatches] = useState<Batch[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [flash, setFlash] = useState<FlashbarProps.MessageDefinition[]>([]);
  const [showModal, setShowModal] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({ lotNumber: '', productId: '', manufacturingDate: '', notes: '' });

  const productMap = Object.fromEntries(products.map((p) => [p.productId, p.productName]));
  const columns = [
    { id: 'lotNumber',         header: 'Lot Number',         cell: (i: Batch) => i.lotNumber,         sortingField: 'lotNumber' },
    { id: 'productId',        header: 'Product',            cell: (i: Batch) => productMap[i.productId] ?? i.productId, sortingField: 'productId' },
    { id: 'manufacturingDate',header: 'Mfg Date',           cell: (i: Batch) => i.manufacturingDate, sortingField: 'manufacturingDate' },
    {
      id: 'status', header: 'Status',
      cell: (i: Batch) => {
        const s = STATUS_MAP[i.status] ?? { type: 'pending' as const, label: i.status };
        return <StatusIndicator type={s.type}>{s.label}</StatusIndicator>;
      },
    },
    {
      id: 'completeness', header: 'Data Completeness',
      cell: (i: Batch) => {
        const total = 4;
        const received = total - (i.missingElements?.length ?? 0);
        const color = received === total ? 'green' : received === 0 ? 'red' : 'blue';
        return <Badge color={color}>{received}/{total} elements</Badge>;
      },
    },
  ];

  const load = () => {
    setLoading(true);
    listBatches(cmoId ? { cmoId } : undefined)
      .then(setBatches)
      .catch((e: Error) => setFlash([{ type: 'error', dismissible: true, onDismiss: () => setFlash([]), content: e.message }]))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
    // Load products scoped to this CMO (for CMO users, JWT-enforced on backend)
    listProducts().then(setProducts).catch(() => {});
  }, []);

  const { items, filteredItemsCount, collectionProps, filterProps, paginationProps } =
    useCollection(batches, {
      filtering: { empty: 'No batches found.', noMatch: 'No matches.' },
      pagination: { pageSize: 10 },
      sorting: { defaultState: { sortingColumn: columns[0] } },
    });

  const handleCreate = async () => {
    if (!form.lotNumber || !form.productId || !form.manufacturingDate) {
      setFlash([{ type: 'error', dismissible: true, onDismiss: () => setFlash([]), content: 'Lot number, product, and manufacturing date are required.' }]);
      return;
    }
    setSaving(true);
    try {
      const batch = await createBatch(form);
      setShowModal(false);
      setForm({ lotNumber: '', productId: '', manufacturingDate: '', notes: '' });
      navigate(`/batches/${batch.batchId}`);
    } catch (e: unknown) {
      setFlash([{ type: 'error', dismissible: true, onDismiss: () => setFlash([]), content: (e as Error).message }]);
    } finally {
      setSaving(false);
    }
  };

  const productOptions = products
    .filter((p) => p.isActive)
    .map((p) => ({ label: `${p.productName} — ${p.strength} ${p.dosageForm}`, value: p.productId, description: p.productId }));

  return (
    <SpaceBetween size="l">
      <Flashbar items={flash} />
      <Table
        {...collectionProps}
        columnDefinitions={columns}
        items={items}
        loading={loading}
        loadingText="Loading batches…"
        trackBy="batchId"
        variant="full-page"
        stickyHeader
        header={
          <Header
            variant="h1"
            counter={`(${batches.length})`}
            description="Manufacturing batches and data submission status"
            actions={
              user?.isCMOUser
                ? <Button variant="primary" onClick={() => setShowModal(true)}>New Batch</Button>
                : undefined
            }
          >
            Batches
          </Header>
        }
        filter={<TextFilter {...filterProps} filteringPlaceholder="Find batches" countText={`${filteredItemsCount ?? 0} match(es)`} />}
        pagination={<Pagination {...paginationProps} />}
        onRowClick={({ detail }) => navigate(`/batches/${detail.item.batchId}`)}
      />

      {user?.isCMOUser && (
        <Modal
          visible={showModal}
          onDismiss={() => setShowModal(false)}
          header="New Batch"
          footer={
            <SpaceBetween direction="horizontal" size="xs">
              <Button onClick={() => setShowModal(false)}>Cancel</Button>
              <Button variant="primary" loading={saving} onClick={handleCreate}>Create</Button>
            </SpaceBetween>
          }
        >
          <Form>
            <SpaceBetween size="m">
              <FormField label="Lot Number" description="Your internal lot/batch number as it appears on manufacturing documents">
                <Input value={form.lotNumber} onChange={({ detail }) => setForm({ ...form, lotNumber: detail.value })} placeholder="e.g. LOT-LNZ-2026-007" />
              </FormField>
              <FormField label="Product">
                <Select
                  selectedOption={productOptions.find((o) => o.value === form.productId) ?? null}
                  onChange={({ detail }) => setForm({ ...form, productId: detail.selectedOption.value ?? '' })}
                  options={productOptions}
                  placeholder="Select product"
                />
              </FormField>
              <FormField label="Manufacturing Date">
                <Input value={form.manufacturingDate} onChange={({ detail }) => setForm({ ...form, manufacturingDate: detail.value })} placeholder="YYYY-MM-DD" />
              </FormField>
              <FormField label="Notes (optional)">
                <Input value={form.notes} onChange={({ detail }) => setForm({ ...form, notes: detail.value })} />
              </FormField>
            </SpaceBetween>
          </Form>
        </Modal>
      )}
    </SpaceBetween>
  );
}
