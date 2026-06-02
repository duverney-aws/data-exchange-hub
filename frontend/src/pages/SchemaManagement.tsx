import { useState, useEffect } from 'react';
import Alert from '@cloudscape-design/components/alert';
import Badge from '@cloudscape-design/components/badge';
import Box from '@cloudscape-design/components/box';
import Button from '@cloudscape-design/components/button';
import ExpandableSection from '@cloudscape-design/components/expandable-section';
import Flashbar, { FlashbarProps } from '@cloudscape-design/components/flashbar';
import FormField from '@cloudscape-design/components/form-field';
import Header from '@cloudscape-design/components/header';
import Input from '@cloudscape-design/components/input';
import Modal from '@cloudscape-design/components/modal';
import Select, { SelectProps } from '@cloudscape-design/components/select';
import SpaceBetween from '@cloudscape-design/components/space-between';
import StatusIndicator from '@cloudscape-design/components/status-indicator';
import Table from '@cloudscape-design/components/table';
import Tabs from '@cloudscape-design/components/tabs';
import { useAuth } from '../context/AuthContext';
import {
  listSchemas, createSchema, updateSchema, inferSchema, registerSchemaInRegistry,
  listCMOs, type Schema, type SchemaField, type CMOProfile,
} from '../services/api';

const FIELD_TYPE_OPTIONS: SelectProps.Option[] = [
  { value: 'string', label: 'String' }, { value: 'integer', label: 'Integer' },
  { value: 'double', label: 'Double' }, { value: 'boolean', label: 'Boolean' },
  { value: 'timestamp', label: 'Timestamp' }, { value: 'date', label: 'Date' },
];

function emptyField(): SchemaField { return { name: '', type: 'string', nullable: true }; }

function FieldsDetail({ schema }: { schema: Schema }) {
  const fs = schema.fields ?? [];
  if (fs.length === 0) return <Box color="text-body-secondary">No fields defined.</Box>;
  return (
    <Table
      variant="embedded"
      items={fs}
      columnDefinitions={[
        { id: 'name', header: 'Field Name', cell: f => <Box fontWeight="bold">{f.name}</Box> },
        { id: 'type', header: 'Type', cell: f => <Badge color="blue">{f.type}</Badge> },
        { id: 'required', header: 'Required', cell: f => {
          const req = (f as SchemaField & { required?: boolean }).required;
          const isRequired = req !== undefined ? req : (f.nullable === false);
          return isRequired
            ? <StatusIndicator type="success">Required</StatusIndicator>
            : <StatusIndicator type="stopped">Optional</StatusIndicator>;
        }},
      ]}
    />
  );
}

function EditableFieldsTable({ fields, setFields }: { fields: SchemaField[]; setFields: (fn: (prev: SchemaField[]) => SchemaField[]) => void }) {
  return (
    <Table
      items={fields}
      columnDefinitions={[
        { id: 'name', header: 'Field Name', cell: (item) => item.name,
          editConfig: { ariaLabel: 'name', editIconAriaLabel: 'edit',
            editingCell: (item, { currentValue, setValue }) =>
              <Input autoFocus value={currentValue ?? item.name} onChange={({ detail }) => setValue(detail.value)} /> } },
        { id: 'type', header: 'Type', cell: (item) => item.type,
          editConfig: { ariaLabel: 'type', editIconAriaLabel: 'edit',
            editingCell: (item, { currentValue, setValue }) =>
              <Select selectedOption={FIELD_TYPE_OPTIONS.find(o => o.value === (currentValue ?? item.type)) ?? FIELD_TYPE_OPTIONS[0]}
                options={FIELD_TYPE_OPTIONS} onChange={({ detail }) => setValue(detail.selectedOption.value!)} /> } },
        { id: 'nullable', header: 'Nullable', cell: (item) => item.nullable ? 'Yes' : 'No' },
        { id: 'actions', header: '', cell: (item) =>
          <Button variant="icon" iconName="remove" onClick={() => setFields(prev => prev.filter(f => f !== item))} /> },
      ]}
      submitEdit={(item, column, newValue) => {
        setFields(prev => prev.map(f => f !== item ? f : { ...f, [column.id === 'name' ? 'name' : 'type']: newValue as string }));
      }}
      header={<Header counter={`(${fields.length})`} actions={<Button onClick={() => setFields(prev => [...prev, emptyField()])}>Add Field</Button>}>Fields</Header>}
    />
  );
}

export default function SchemaManagement({ cmoId: propCmoId }: { cmoId?: string } = {}) {
  const { user } = useAuth();
  const [schemas, setSchemas] = useState<Schema[]>([]);
  const [cmos, setCmos] = useState<CMOProfile[]>([]);
  const [loading, setLoading] = useState(true);
  const [flashItems, setFlashItems] = useState<FlashbarProps.MessageDefinition[]>([]);
  const [showCreate, setShowCreate] = useState(false);
  const [registering, setRegistering] = useState<string | null>(null);
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());

  // Create form
  const [activeTab, setActiveTab] = useState('infer');
  const [newCmoId, setNewCmoId] = useState('');
  const [newName, setNewName] = useState('');
  const [fields, setFields] = useState<SchemaField[]>([]);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [inferring, setInferring] = useState(false);
  const [creating, setCreating] = useState(false);

  // Edit modal
  const [editSchema, setEditSchema] = useState<Schema | null>(null);
  const [editName, setEditName] = useState('');
  const [editFields, setEditFields] = useState<SchemaField[]>([]);
  const [saving, setSaving] = useState(false);

  useEffect(() => { load(); }, []);

  async function load() {
    setLoading(true);
    try {
      const [s, c] = await Promise.all([listSchemas(propCmoId), user?.isMerckAdmin ? listCMOs() : Promise.resolve([])]);
      setSchemas(s); setCmos(c);
    } catch (e) { console.error(e); }
    setLoading(false);
  }

  function openEdit(schema: Schema) {
    setEditSchema(schema);
    setEditName(schema.name);
    setEditFields(schema.fields ? schema.fields.map(f => ({ ...f })) : []);
  }

  async function handleSaveEdit() {
    if (!editSchema || !editName || editFields.length === 0) return;
    setSaving(true);
    try {
      const updated = await updateSchema(editSchema.schemaId, { name: editName, fields: editFields });
      // If was registered, backend keeps status; reset to draft so it can be re-registered
      setSchemas(prev => prev.map(s => s.schemaId === updated.schemaId ? updated : s));
      setEditSchema(null);
      setFlashItems([{ type: 'success', dismissible: true, onDismiss: () => setFlashItems([]),
        content: `Schema "${updated.name}" updated.${updated.status === 'registered' ? ' Re-register in Glue to publish the new version.' : ''}` }]);
    } catch (e: unknown) {
      setFlashItems([{ type: 'error', dismissible: true, onDismiss: () => setFlashItems([]),
        content: `Save failed: ${e instanceof Error ? e.message : 'Unknown'}` }]);
    }
    setSaving(false);
  }

  async function handleInfer() {
    if (!selectedFile) return;
    setInferring(true);
    try {
      const result = await inferSchema(selectedFile);
      setFields(result.fields);
      if (!newName) setNewName(selectedFile.name.replace(/\.[^.]+$/, ''));
    } catch (e: unknown) {
      setFlashItems([{ type: 'error', dismissible: true, onDismiss: () => setFlashItems([]), content: `Infer failed: ${e instanceof Error ? e.message : 'Unknown'}` }]);
    }
    setInferring(false);
  }

  async function handleCreate() {
    if (!newCmoId || !newName || fields.length === 0) return;
    setCreating(true);
    try {
      const s = await createSchema({ cmoId: newCmoId, name: newName, fields });
      setSchemas(prev => [s, ...prev]);
      setShowCreate(false); setNewName(''); setFields([]); setSelectedFile(null);
      setFlashItems([{ type: 'success', dismissible: true, onDismiss: () => setFlashItems([]), content: `Schema "${s.name}" created. Register it in Glue when ready.` }]);
    } catch (e: unknown) {
      setFlashItems([{ type: 'error', dismissible: true, onDismiss: () => setFlashItems([]), content: `Failed: ${e instanceof Error ? e.message : 'Unknown'}` }]);
    }
    setCreating(false);
  }

  async function handleRegister(schema: Schema) {
    setRegistering(schema.schemaId);
    try {
      const updated = await registerSchemaInRegistry(schema.schemaId);
      setSchemas(prev => prev.map(s => s.schemaId === updated.schemaId ? updated : s));
      setFlashItems([{ type: 'success', dismissible: true, onDismiss: () => setFlashItems([]), content: `Schema "${updated.name}" registered in Glue as v${updated.version}.` }]);
    } catch (e: unknown) {
      setFlashItems([{ type: 'error', dismissible: true, onDismiss: () => setFlashItems([]), content: `Register failed: ${e instanceof Error ? e.message : 'Unknown'}` }]);
    }
    setRegistering(null);
  }

  function toggleExpand(schemaId: string) {
    setExpandedIds(prev => {
      const next = new Set(prev);
      next.has(schemaId) ? next.delete(schemaId) : next.add(schemaId);
      return next;
    });
  }

  const cmoMap = Object.fromEntries(cmos.map(c => [c.cmoId, c.organizationName]));

  const inferTab = (
    <SpaceBetween size="m">
      <FormField label="Sample data file" description="Upload a CSV or JSON file to infer the schema automatically.">
        <input type="file" accept=".csv,.json" onChange={e => { setSelectedFile(e.target.files?.[0] ?? null); setFields([]); }} />
      </FormField>
      <Button variant="primary" loading={inferring} disabled={!selectedFile} onClick={handleInfer}>Infer Schema</Button>
      {fields.length > 0 && <Alert type="success">Inferred {fields.length} fields. Review below, then click Create.</Alert>}
    </SpaceBetween>
  );

  const manualTab = (
    <SpaceBetween size="m">
      <Button onClick={() => setFields(prev => [...prev, emptyField()])}>Add Field</Button>
    </SpaceBetween>
  );

  return (
    <SpaceBetween size="l">
      <Table
        header={
          <Header variant="h1" counter={`(${schemas.length})`}
            actions={user?.isMerckAdmin ? <Button variant="primary" onClick={() => setShowCreate(true)}>Create Schema</Button> : undefined}>
            {user?.isMerckAdmin ? 'Schema Management' : 'My Schemas'}
          </Header>
        }
        items={schemas} loading={loading} loadingText="Loading schemas..."
        empty={<Box textAlign="center"><b>No schemas</b><Box variant="p">No schemas have been created yet.</Box></Box>}
        columnDefinitions={[
          { id: 'expand', header: '', width: 40, cell: item => (
            <Button variant="icon" iconName={expandedIds.has(item.schemaId) ? 'treeview-collapse' : 'treeview-expand'}
              ariaLabel="Show fields" onClick={() => toggleExpand(item.schemaId)} />
          )},
          { id: 'name', header: 'Name', cell: item => item.name },
          { id: 'schemaId', header: 'Schema ID', cell: item => item.schemaId },
          ...(user?.isMerckAdmin ? [{ id: 'cmo', header: 'CMO', cell: (item: Schema) => cmoMap[item.cmoId] || item.cmoId }] : []),
          { id: 'fields', header: 'Fields', cell: item => (item.fields?.length ?? 0) },
          { id: 'version', header: 'Version', cell: item => item.version ?? '—' },
          { id: 'glue', header: 'Glue Schema', cell: item => (item as Schema & { glueSchemaName?: string }).glueSchemaName ?? '—' },
          { id: 'status', header: 'Status', cell: item => (
            <StatusIndicator type={item.status === 'registered' ? 'success' : 'pending'}>{item.status}</StatusIndicator>
          )},
          { id: 'actions', header: 'Actions', cell: item => (
            user?.isMerckAdmin ? (
              <SpaceBetween direction="horizontal" size="xs">
                <Button onClick={() => openEdit(item)}>Edit</Button>
                {item.status === 'draft' && (
                  <Button loading={registering === item.schemaId} onClick={() => handleRegister(item)}>Register in Glue</Button>
                )}
              </SpaceBetween>
            ) : null
          )},
        ]}
      />

      {/* Inline field detail panels */}
      {schemas.filter(s => expandedIds.has(s.schemaId)).map(s => (
        <ExpandableSection key={s.schemaId} defaultExpanded headerText={`${s.name} — Field Definitions`}
          onChange={({ detail }) => { if (!detail.expanded) toggleExpand(s.schemaId); }}>
          <FieldsDetail schema={s} />
        </ExpandableSection>
      ))}

      <Flashbar items={flashItems} />

      {/* Edit Schema Modal */}
      {editSchema && (
        <Modal visible onDismiss={() => setEditSchema(null)} header={`Edit Schema: ${editSchema.name}`} size="large"
          footer={<Box float="right"><SpaceBetween direction="horizontal" size="xs">
            <Button variant="link" onClick={() => setEditSchema(null)}>Cancel</Button>
            <Button variant="primary" loading={saving} disabled={!editName || editFields.length === 0} onClick={handleSaveEdit}>Save Changes</Button>
          </SpaceBetween></Box>}>
          <SpaceBetween size="m">
            {editSchema.status === 'registered' && (
              <Alert type="info">
                This schema is registered in Glue. Saving changes will update the definition here.
                Use <b>Register in Glue</b> afterward to publish a new version.
              </Alert>
            )}
            <FormField label="Schema Name">
              <Input value={editName} onChange={({ detail }) => setEditName(detail.value)} />
            </FormField>
            <EditableFieldsTable fields={editFields} setFields={setEditFields} />
          </SpaceBetween>
        </Modal>
      )}

      {/* Create Schema Modal */}
      <Modal visible={showCreate} onDismiss={() => setShowCreate(false)} header="Create Schema" size="large"
        footer={<Box float="right"><SpaceBetween direction="horizontal" size="xs">
          <Button variant="link" onClick={() => setShowCreate(false)}>Cancel</Button>
          <Button variant="primary" loading={creating} disabled={!newCmoId || !newName || fields.length === 0} onClick={handleCreate}>Create Schema</Button>
        </SpaceBetween></Box>}>
        <SpaceBetween size="m">
          {user?.isMerckAdmin && (
            <FormField label="CMO">
              <Select selectedOption={newCmoId ? { value: newCmoId, label: cmoMap[newCmoId] || newCmoId } : null}
                onChange={({ detail }) => setNewCmoId(detail.selectedOption.value || '')}
                options={cmos.map(c => ({ value: c.cmoId, label: c.organizationName }))} placeholder="Select CMO" />
            </FormField>
          )}
          <FormField label="Schema Name"><Input value={newName} onChange={({ detail }) => setNewName(detail.value)} placeholder="e.g. batch-records" /></FormField>
          <Tabs activeTabId={activeTab} onChange={({ detail }) => setActiveTab(detail.activeTabId)} tabs={[
            { id: 'infer', label: 'Infer from File', content: inferTab },
            { id: 'manual', label: 'Manual Definition', content: manualTab },
          ]} />
          {fields.length > 0 && <EditableFieldsTable fields={fields} setFields={setFields} />}
        </SpaceBetween>
      </Modal>
    </SpaceBetween>
  );
}
