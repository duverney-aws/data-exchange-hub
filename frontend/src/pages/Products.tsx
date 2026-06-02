import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useCollection } from '@cloudscape-design/collection-hooks';
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
import { Product, listProducts, createProduct, listCMOs, CMOProfile } from '../services/api';

const COLUMNS = [
  { id: 'productName', header: 'Product Name', cell: (i: Product) => i.productName, sortingField: 'productName' },
  { id: 'productId', header: 'Product ID', cell: (i: Product) => i.productId, sortingField: 'productId' },
  { id: 'strength', header: 'Strength', cell: (i: Product) => i.strength, sortingField: 'strength' },
  { id: 'dosageForm', header: 'Dosage Form', cell: (i: Product) => i.dosageForm, sortingField: 'dosageForm' },
  { id: 'cmoId', header: 'CMO', cell: (i: Product) => i.cmoId, sortingField: 'cmoId' },
  {
    id: 'isActive', header: 'Status',
    cell: (i: Product) => (
      <StatusIndicator type={i.isActive ? 'success' : 'stopped'}>
        {i.isActive ? 'Active' : 'Inactive'}
      </StatusIndicator>
    ),
  },
];

export default function Products() {
  const { user } = useAuth();
  const [searchParams] = useSearchParams();
  const preselectedCmoId = searchParams.get('cmoId') ?? '';
  const [products, setProducts] = useState<Product[]>([]);
  const [cmos, setCmos] = useState<CMOProfile[]>([]);
  const [loading, setLoading] = useState(true);
  const [flash, setFlash] = useState<FlashbarProps.MessageDefinition[]>([]);
  const [showModal, setShowModal] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({ productName: '', strength: '', dosageForm: '', cmoId: preselectedCmoId, description: '' });

  const load = () => {
    setLoading(true);
    listProducts()
      .then(setProducts)
      .catch((e: Error) => setFlash([{ type: 'error', dismissible: true, onDismiss: () => setFlash([]), content: e.message }]))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
    listCMOs().then(setCmos).catch(() => {});
    if (preselectedCmoId && user?.isMerckAdmin) setShowModal(true);
  }, []);

  const { items, filteredItemsCount, collectionProps, filterProps, paginationProps } =
    useCollection(products, {
      filtering: { empty: 'No products found.', noMatch: 'No matches.' },
      pagination: { pageSize: 10 },
      sorting: { defaultState: { sortingColumn: COLUMNS[0] } },
    });

  const handleCreate = async () => {
    if (!form.productName || !form.strength || !form.dosageForm || !form.cmoId) {
      setFlash([{ type: 'error', dismissible: true, onDismiss: () => setFlash([]), content: 'All fields are required.' }]);
      return;
    }
    setSaving(true);
    try {
      await createProduct({ ...form, isActive: true });
      setShowModal(false);
      setForm({ productName: '', strength: '', dosageForm: '', cmoId: '', description: '' });
      load();
    } catch (e: unknown) {
      setFlash([{ type: 'error', dismissible: true, onDismiss: () => setFlash([]), content: (e as Error).message }]);
    } finally {
      setSaving(false);
    }
  };

  const cmoOptions = cmos.map((c) => ({ label: c.organizationName || c.cmoId, value: c.cmoId }));

  return (
    <SpaceBetween size="l">
      <Flashbar items={flash} />
      <Table
        {...collectionProps}
        columnDefinitions={COLUMNS}
        items={items}
        loading={loading}
        loadingText="Loading products…"
        trackBy="productId"
        variant="full-page"
        stickyHeader
        header={
          <Header
            variant="h1"
            counter={`(${products.length})`}
            description="Drug products manufactured by CMOs on behalf of Merck"
            actions={
              user?.isMerckAdmin
                ? <Button variant="primary" onClick={() => setShowModal(true)}>Add Product</Button>
                : undefined
            }
          >
            Products
          </Header>
        }
        filter={<TextFilter {...filterProps} filteringPlaceholder="Find products" countText={`${filteredItemsCount ?? 0} match(es)`} />}
        pagination={<Pagination {...paginationProps} />}
      />

      {user?.isMerckAdmin && (
        <Modal
          visible={showModal}
          onDismiss={() => setShowModal(false)}
          header="Add Product"
          footer={
            <SpaceBetween direction="horizontal" size="xs">
              <Button onClick={() => setShowModal(false)}>Cancel</Button>
              <Button variant="primary" loading={saving} onClick={handleCreate}>Create</Button>
            </SpaceBetween>
          }
        >
          <Form>
            <SpaceBetween size="m">
              <FormField label="Product Name">
                <Input value={form.productName} onChange={({ detail }) => setForm({ ...form, productName: detail.value })} placeholder="e.g. Keytruda" />
              </FormField>
              <FormField label="Strength">
                <Input value={form.strength} onChange={({ detail }) => setForm({ ...form, strength: detail.value })} placeholder="e.g. 50mg/mL" />
              </FormField>
              <FormField label="Dosage Form">
                <Input value={form.dosageForm} onChange={({ detail }) => setForm({ ...form, dosageForm: detail.value })} placeholder="e.g. injection" />
              </FormField>
              <FormField label="CMO">
                <Select
                  selectedOption={cmoOptions.find((o) => o.value === form.cmoId) ?? null}
                  onChange={({ detail }) => setForm({ ...form, cmoId: detail.selectedOption.value ?? '' })}
                  options={cmoOptions}
                  placeholder="Select CMO"
                />
              </FormField>
              <FormField label="Description (optional)">
                <Input value={form.description} onChange={({ detail }) => setForm({ ...form, description: detail.value })} />
              </FormField>
            </SpaceBetween>
          </Form>
        </Modal>
      )}
    </SpaceBetween>
  );
}
