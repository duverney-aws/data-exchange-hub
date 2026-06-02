import { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import Button from '@cloudscape-design/components/button';
import Checkbox from '@cloudscape-design/components/checkbox';
import Container from '@cloudscape-design/components/container';
import Flashbar, { FlashbarProps } from '@cloudscape-design/components/flashbar';
import Form from '@cloudscape-design/components/form';
import FormField from '@cloudscape-design/components/form-field';
import Header from '@cloudscape-design/components/header';
import Input from '@cloudscape-design/components/input';
import Select, { SelectProps } from '@cloudscape-design/components/select';
import SpaceBetween from '@cloudscape-design/components/space-between';
import Link from '@cloudscape-design/components/link';
import { createContract, listCMOs, listProducts, listConnections, listSchemas, CMOProfile, Product, QualityRule, Connection, Schema } from '../services/api';

const FREQUENCY_OPTIONS: SelectProps.Option[] = [
  { value: 'real-time', label: 'Real-time' },
  { value: 'hourly', label: 'Hourly' },
  { value: 'daily', label: 'Daily' },
  { value: 'weekly', label: 'Weekly' },
  { value: 'monthly', label: 'Monthly' },
];

const CLASSIFICATION_OPTIONS: SelectProps.Option[] = [
  { value: 'public', label: 'Public' },
  { value: 'internal', label: 'Internal' },
  { value: 'confidential', label: 'Confidential' },
  { value: 'restricted', label: 'Restricted' },
];

const SEVERITY_OPTIONS: SelectProps.Option[] = [
  { value: 'warning', label: 'Warning' },
  { value: 'error', label: 'Error' },
];

const ELEMENT_OPTIONS: SelectProps.Option[] = [
  { value: 'bmr',           label: 'Batch Manufacturing Record (BMR)' },
  { value: 'coa',           label: 'Certificate of Analysis (CoA)' },
  { value: 'in_process',    label: 'In-Process Test Results' },
  { value: 'yield',         label: 'Yield / Reconciliation Data' },
  { value: 'deviation',     label: 'Deviation Reports' },
  { value: 'env_monitoring',label: 'Environmental Monitoring' },
];

interface ElementSla { elementType: string; maxDaysAfterBatch: number; }
interface FormErrors { cmoId?: string; productId?: string; dataDomain?: string; schemaId?: string; schemaVersion?: string; }

function emptyRule(): QualityRule {
  return { ruleId: '', ruleName: '', ruleType: 'completeness', expression: '', threshold: 95, severity: 'error' };
}

function defaultElementSlas(): ElementSla[] {
  return [
    { elementType: 'bmr',        maxDaysAfterBatch: 5 },
    { elementType: 'coa',        maxDaysAfterBatch: 5 },
    { elementType: 'in_process', maxDaysAfterBatch: 1 },
    { elementType: 'yield',      maxDaysAfterBatch: 5 },
  ];
}

export default function ContractCreate() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  const [cmos, setCmos] = useState<CMOProfile[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const preselected = searchParams.get('cmoId') ?? '';
  const [selectedCmo, setSelectedCmo] = useState<SelectProps.Option | null>(
    preselected ? { value: preselected, label: preselected } : null
  );
  const [selectedProduct, setSelectedProduct] = useState<SelectProps.Option | null>(null);
  const [connections, setConnections] = useState<Connection[]>([]);
  const [selectedConnection, setSelectedConnection] = useState<SelectProps.Option | null>(null);
  const [schemas, setSchemas] = useState<Schema[]>([]);
  const [selectedSchema, setSelectedSchema] = useState<SelectProps.Option | null>(null);
  const cmoId = selectedCmo?.value ?? '';
  const productId = selectedProduct?.value ?? '';

  useEffect(() => {
    listCMOs().then(list => {
      setCmos(list);
      if (preselected) {
        const match = list.find(c => c.cmoId === preselected);
        if (match) setSelectedCmo({ value: match.cmoId, label: `${match.organizationName} (${match.cmoId})` });
      }
    }).catch(() => {});
  }, []);

  useEffect(() => {
    if (!cmoId) { setProducts([]); setSelectedProduct(null); return; }
    listProducts(cmoId).then(setProducts).catch(() => {});
  }, [cmoId]);

  useEffect(() => {
    if (!cmoId) { setSchemas([]); setSelectedSchema(null); return; }
    listSchemas(cmoId).then(setSchemas).catch(() => {});
  }, [cmoId]);

  useEffect(() => {
    if (!cmoId) { setConnections([]); setSelectedConnection(null); return; }
    listConnections(cmoId).then(list => setConnections(list.filter(c => c.status === 'active'))).catch(() => {});
  }, [cmoId]);

  const [dataDomain, setDataDomain] = useState('batch-records');
  const [schemaId, setSchemaId] = useState('');
  const [schemaVersion, setSchemaVersion] = useState('1.0');
  const [qualityRules, setQualityRules] = useState<QualityRule[]>([emptyRule()]);
  const [elementSlas, setElementSlas] = useState<ElementSla[]>(defaultElementSlas());
  const [maxDelayHours] = useState('24');
  const [uptimePercentage] = useState('99.5');
  const [minQualityScore] = useState('95');
  const [frequency, setFrequency] = useState<SelectProps.Option>(FREQUENCY_OPTIONS[2]);
  const [timezone, setTimezone] = useState('UTC');
  const [dataClassification, setDataClassification] = useState<SelectProps.Option>(CLASSIFICATION_OPTIONS[2]);
  const [retentionYears, setRetentionYears] = useState('7');
  const [encryptionRequired, setEncryptionRequired] = useState(true);
  const [errors, setErrors] = useState<FormErrors>({});
  const [loading, setLoading] = useState(false);
  const [flashItems, setFlashItems] = useState<FlashbarProps.MessageDefinition[]>([]);

  function validate(): FormErrors {
    const result: FormErrors = {};
    if (!cmoId.trim()) result.cmoId = 'CMO is required.';
    if (!productId.trim()) result.productId = 'Product is required.';
    if (!dataDomain.trim()) result.dataDomain = 'Data domain is required.';
    if (!schemaId.trim()) result.schemaId = 'Schema ID is required.';
    if (!schemaVersion.trim()) result.schemaVersion = 'Schema version is required.';
    return result;
  }

  async function handleSubmit() {
    const validationErrors = validate();
    setErrors(validationErrors);
    if (Object.keys(validationErrors).length > 0) return;
    setLoading(true);
    setFlashItems([]);
    try {
      const result = await createContract({
        cmoId: cmoId.trim(),
        productId: productId.trim(),
        connectionId: selectedConnection?.value || '',
        dataDomain: dataDomain.trim(),
        schemaId: selectedSchema?.value || schemaId.trim(),
        schemaVersion: schemaVersion.trim(),
        qualityRules,
        elementSlas,
        sla: {
          timeliness: { maxDelayHours: Number(maxDelayHours), measurementWindow: 'daily' },
          availability: { uptimePercentage: Number(uptimePercentage), measurementWindow: 'monthly' },
          quality: { minQualityScore: Number(minQualityScore), measurementWindow: 'daily' },
        },
        deliverySchedule: { frequency: frequency.value as 'real-time' | 'hourly' | 'daily' | 'weekly' | 'monthly', timezone },
        governance: {
          dataClassification: dataClassification.value as 'public' | 'internal' | 'confidential' | 'restricted',
          retentionYears: Number(retentionYears),
          allowedUsers: [],
          allowedGroups: ['merck-admins', 'quality-team'],
          piiFields: [],
          encryptionRequired,
        },
      });
      setFlashItems([{ type: 'success', dismissible: true, onDismiss: () => setFlashItems([]), content: `Contract created: ${result.contractId}` }]);
      setTimeout(() => navigate('/data-contracts'), 1500);
    } catch (err: unknown) {
      setFlashItems([{ type: 'error', dismissible: true, onDismiss: () => setFlashItems([]), content: `Failed: ${err instanceof Error ? err.message : 'Unknown error'}` }]);
    } finally {
      setLoading(false);
    }
  }

  const productOptions = products.map(p => ({ value: p.productId, label: `${p.productName} ${p.strength} (${p.dosageForm})` }));

  return (
    <SpaceBetween size="l">
      <Header variant="h1" description="Define a data contract governing batch data submissions for a specific product">
        Create Data Contract
      </Header>
      <Flashbar items={flashItems} />
      <form onSubmit={(e) => e.preventDefault()}>
        <Form actions={
          <SpaceBetween direction="horizontal" size="xs">
            <Button variant="link" onClick={() => navigate('/data-contracts')}>Cancel</Button>
            <Button variant="primary" loading={loading} onClick={handleSubmit}>Create Contract</Button>
          </SpaceBetween>
        }>
          <SpaceBetween size="l">

            <Container header={<Header variant="h2">Basic Information</Header>}>
              <SpaceBetween size="l">
                <FormField label="CMO" errorText={errors.cmoId}>
                  <Select
                    selectedOption={selectedCmo}
                    onChange={({ detail }) => setSelectedCmo(detail.selectedOption)}
                    options={cmos.map(c => ({ value: c.cmoId, label: `${c.organizationName} (${c.cmoId})` }))}
                    placeholder="Select a CMO"
                  />
                </FormField>
                <FormField label="Product" errorText={errors.productId} description="The drug product this contract covers. Select a CMO first.">
                  <Select
                    selectedOption={selectedProduct}
                    onChange={({ detail }) => setSelectedProduct(detail.selectedOption)}
                    options={productOptions}
                    placeholder={cmoId ? 'Select a product' : 'Select a CMO first'}
                    disabled={!cmoId}
                    empty="No products registered for this CMO"
                  />
                </FormField>
                {cmoId && products.length === 0 && (
                  <Flashbar items={[{
                    type: 'warning',
                    content: <>No products registered for this CMO. <Link href={`/products?cmoId=${cmoId}`}>Add a product</Link> before creating a contract.</>,
                  }]} />
                )}
                <FormField label="Connection" description="Select an active connection for data delivery. Create connections from the Connections page.">
                  <Select
                    selectedOption={selectedConnection}
                    onChange={({ detail }) => setSelectedConnection(detail.selectedOption)}
                    options={connections.map(c => ({ value: c.connectionId, label: `${c.name} (${c.connectionType})` }))}
                    placeholder={cmoId ? 'Select a connection (optional)' : 'Select a CMO first'}
                    disabled={!cmoId}
                    empty="No active connections for this CMO"
                  />
                </FormField>
                <FormField label="Data Domain" errorText={errors.dataDomain}>
                  <Input value={dataDomain} onChange={({ detail }) => setDataDomain(detail.value)} />
                </FormField>
                <FormField label="Schema" description="Select a schema for this CMO. Create schemas from the Schema Management page.">
                  <Select
                    selectedOption={selectedSchema}
                    onChange={({ detail }) => { setSelectedSchema(detail.selectedOption); setSchemaId(detail.selectedOption.value || ''); setSchemaVersion('1'); }}
                    options={schemas.map(s => ({ value: s.schemaId, label: `${s.name} (v${s.version}) — ${s.status}`, description: `${s.fields?.length || 0} fields` }))}
                    placeholder={cmoId ? 'Select a schema (optional)' : 'Select a CMO first'}
                    disabled={!cmoId}
                    empty="No schemas for this CMO"
                  />
                </FormField>
              </SpaceBetween>
            </Container>

            <Container header={
              <Header
                variant="h2"
                description="How many business days after batch completion each data element must be submitted"
                actions={<Button onClick={() => setElementSlas(p => [...p, { elementType: 'deviation', maxDaysAfterBatch: 2 }])}>Add Element</Button>}
              >
                Data Submission SLAs
              </Header>
            }>
              <SpaceBetween size="m">
                {elementSlas.map((sla, idx) => (
                  <SpaceBetween key={idx} direction="horizontal" size="m">
                    <FormField label={idx === 0 ? 'Data Element' : ''} stretch>
                      <Select
                        selectedOption={ELEMENT_OPTIONS.find(o => o.value === sla.elementType) ?? null}
                        onChange={({ detail }) => setElementSlas(p => p.map((s, i) => i === idx ? { ...s, elementType: detail.selectedOption.value ?? '' } : s))}
                        options={ELEMENT_OPTIONS}
                      />
                    </FormField>
                    <FormField label={idx === 0 ? 'Max Days After Batch' : ''}>
                      <Input
                        value={String(sla.maxDaysAfterBatch)}
                        onChange={({ detail }) => setElementSlas(p => p.map((s, i) => i === idx ? { ...s, maxDaysAfterBatch: Number(detail.value) } : s))}
                        inputMode="numeric"
                        type="number"
                      />
                    </FormField>
                    {elementSlas.length > 1 && (
                      <FormField label={idx === 0 ? '\u00a0' : ''}>
                        <Button onClick={() => setElementSlas(p => p.filter((_, i) => i !== idx))}>Remove</Button>
                      </FormField>
                    )}
                  </SpaceBetween>
                ))}
              </SpaceBetween>
            </Container>

            <Container header={
              <Header variant="h2" actions={<Button onClick={() => setQualityRules(p => [...p, emptyRule()])}>Add Rule</Button>}>
                Quality Rules
              </Header>
            }>
              <SpaceBetween size="l">
                {qualityRules.map((rule, idx) => (
                  <Container key={idx} header={
                    <Header variant="h3" actions={qualityRules.length > 1 ? <Button onClick={() => setQualityRules(p => p.filter((_, i) => i !== idx))}>Remove</Button> : undefined}>
                      Rule {idx + 1}
                    </Header>
                  }>
                    <SpaceBetween size="m">
                      <FormField label="Rule Name">
                        <Input value={rule.ruleName} onChange={({ detail }) => setQualityRules(p => p.map((r, i) => i === idx ? { ...r, ruleName: detail.value } : r))} placeholder='Batch ID completeness' />
                      </FormField>
                      <FormField label="DQDL Expression">
                        <Input value={rule.expression} onChange={({ detail }) => setQualityRules(p => p.map((r, i) => i === idx ? { ...r, expression: detail.value } : r))} placeholder='Completeness "batch_id" > 0.99' />
                      </FormField>
                      <FormField label="Threshold (0-100)">
                        <Input value={String(rule.threshold)} onChange={({ detail }) => setQualityRules(p => p.map((r, i) => i === idx ? { ...r, threshold: Number(detail.value) } : r))} inputMode="decimal" />
                      </FormField>
                      <FormField label="Severity">
                        <Select selectedOption={SEVERITY_OPTIONS.find(o => o.value === rule.severity) ?? SEVERITY_OPTIONS[1]} options={SEVERITY_OPTIONS} onChange={({ detail }) => setQualityRules(p => p.map((r, i) => i === idx ? { ...r, severity: detail.selectedOption.value as QualityRule['severity'] } : r))} />
                      </FormField>
                    </SpaceBetween>
                  </Container>
                ))}
              </SpaceBetween>
            </Container>

            <Container header={<Header variant="h2">Delivery & Governance</Header>}>
              <SpaceBetween size="l">
                <FormField label="Delivery Frequency">
                  <Select selectedOption={frequency} options={FREQUENCY_OPTIONS} onChange={({ detail }) => setFrequency(detail.selectedOption)} />
                </FormField>
                <FormField label="Timezone">
                  <Input value={timezone} onChange={({ detail }) => setTimezone(detail.value)} />
                </FormField>
                <FormField label="Data Classification">
                  <Select selectedOption={dataClassification} options={CLASSIFICATION_OPTIONS} onChange={({ detail }) => setDataClassification(detail.selectedOption)} />
                </FormField>
                <FormField label="Retention Years">
                  <Input value={retentionYears} onChange={({ detail }) => setRetentionYears(detail.value)} inputMode="numeric" />
                </FormField>
                <FormField label="Encryption">
                  <Checkbox checked={encryptionRequired} onChange={({ detail }) => setEncryptionRequired(detail.checked)}>
                    Encryption required
                  </Checkbox>
                </FormField>
              </SpaceBetween>
            </Container>

          </SpaceBetween>
        </Form>
      </form>
    </SpaceBetween>
  );
}
