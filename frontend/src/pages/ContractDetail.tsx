import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import Alert from '@cloudscape-design/components/alert';
import Box from '@cloudscape-design/components/box';
import Button from '@cloudscape-design/components/button';
import Checkbox from '@cloudscape-design/components/checkbox';
import Container from '@cloudscape-design/components/container';
import Flashbar from '@cloudscape-design/components/flashbar';
import Form from '@cloudscape-design/components/form';
import FormField from '@cloudscape-design/components/form-field';
import Header from '@cloudscape-design/components/header';
import Input from '@cloudscape-design/components/input';
import Modal from '@cloudscape-design/components/modal';
import Select, { SelectProps } from '@cloudscape-design/components/select';
import SpaceBetween from '@cloudscape-design/components/space-between';
import StatusIndicator from '@cloudscape-design/components/status-indicator';
import Textarea from '@cloudscape-design/components/textarea';
import PageLoadingIndicator from '../components/PageLoadingIndicator';
import { useNotifications } from '../hooks/useNotifications';
import { useApiCall } from '../hooks/useApiCall';
import { useAuth } from '../context/AuthContext';
import {
  getContract, updateContract, submitContract, acceptContract,
  approveContract, rejectContract, DataContract, QualityRule,
} from '../services/api';

const FREQUENCY_OPTIONS: SelectProps.Option[] = [
  { value: 'real-time', label: 'Real-time' }, { value: 'hourly', label: 'Hourly' },
  { value: 'daily', label: 'Daily' }, { value: 'weekly', label: 'Weekly' }, { value: 'monthly', label: 'Monthly' },
];
const CLASSIFICATION_OPTIONS: SelectProps.Option[] = [
  { value: 'public', label: 'Public' }, { value: 'internal', label: 'Internal' },
  { value: 'confidential', label: 'Confidential' }, { value: 'restricted', label: 'Restricted' },
];
const SEVERITY_OPTIONS: SelectProps.Option[] = [
  { value: 'warning', label: 'Warning' }, { value: 'error', label: 'Error' },
];

function emptyRule(): QualityRule {
  return { ruleId: '', ruleName: '', ruleType: 'completeness', expression: '', threshold: 95, severity: 'error' };
}

function statusType(status: string): 'info' | 'success' | 'warning' | 'error' | 'pending' {
  const map: Record<string, 'info' | 'success' | 'warning' | 'error' | 'pending'> = {
    draft: 'info', pending_cmo_review: 'pending', pending_merck_approval: 'pending',
    active: 'success', rejected: 'error', suspended: 'warning',
  };
  return map[status] ?? 'info';
}

function statusLabel(status: string) {
  return status.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

export default function ContractDetail() {
  const { contractId } = useParams<{ contractId: string }>();
  const navigate = useNavigate();
  const { user } = useAuth();
  const notifications = useNotifications();
  const saveCall = useApiCall<DataContract>(notifications);

  const [contract, setContract] = useState<DataContract | null>(null);
  const [pageLoading, setPageLoading] = useState(true);
  const [status, setStatus] = useState('');
  const [actionLoading, setActionLoading] = useState(false);
  const [rejectModalOpen, setRejectModalOpen] = useState(false);
  const [rejectReason, setRejectReason] = useState('');

  // Form fields
  const [cmoId, setCmoId] = useState('');
  const [productId, setProductId] = useState('');
  const [dataDomain, setDataDomain] = useState('');
  const [schemaId, setSchemaId] = useState('');
  const [schemaVersion, setSchemaVersion] = useState('');
  const [qualityRules, setQualityRules] = useState<QualityRule[]>([]);
  const [maxDelayHours, setMaxDelayHours] = useState('24');
  const [timelinessWindow, setTimelinessWindow] = useState('daily');
  const [uptimePercentage, setUptimePercentage] = useState('99.5');
  const [availabilityWindow, setAvailabilityWindow] = useState('monthly');
  const [minQualityScore, setMinQualityScore] = useState('95');
  const [qualityWindow, setQualityWindow] = useState('daily');
  const [frequency, setFrequency] = useState<SelectProps.Option>(FREQUENCY_OPTIONS[2]);
  const [cronExpression, setCronExpression] = useState('');
  const [timezone, setTimezone] = useState('UTC');
  const [dataClassification, setDataClassification] = useState<SelectProps.Option>(CLASSIFICATION_OPTIONS[1]);
  const [retentionYears, setRetentionYears] = useState('7');
  const [allowedUsers, setAllowedUsers] = useState('');
  const [allowedGroups, setAllowedGroups] = useState('');
  const [piiFields, setPiiFields] = useState('');
  const [encryptionRequired, setEncryptionRequired] = useState(true);

  function populateForm(c: DataContract) {
    setCmoId(c.cmoId); setProductId(c.productId ?? ''); setDataDomain(c.dataDomain); setSchemaId(c.schemaId);
    setSchemaVersion(c.schemaVersion); setStatus(c.status);
    setQualityRules(c.qualityRules?.length ? c.qualityRules : [emptyRule()]);
    setMaxDelayHours(String(c.sla?.timeliness?.maxDelayHours ?? 24));
    setTimelinessWindow(c.sla?.timeliness?.measurementWindow ?? 'daily');
    setUptimePercentage(String(c.sla?.availability?.uptimePercentage ?? 99.5));
    setAvailabilityWindow(c.sla?.availability?.measurementWindow ?? 'monthly');
    setMinQualityScore(String(c.sla?.quality?.minQualityScore ?? 95));
    setQualityWindow(c.sla?.quality?.measurementWindow ?? 'daily');
    setFrequency(FREQUENCY_OPTIONS.find(o => o.value === c.deliverySchedule?.frequency) ?? FREQUENCY_OPTIONS[2]);
    setCronExpression(c.deliverySchedule?.cronExpression ?? '');
    setTimezone(c.deliverySchedule?.timezone ?? 'UTC');
    setDataClassification(CLASSIFICATION_OPTIONS.find(o => o.value === c.governance?.dataClassification) ?? CLASSIFICATION_OPTIONS[1]);
    setRetentionYears(String(c.governance?.retentionYears ?? 7));
    setAllowedUsers((c.governance?.allowedUsers ?? []).join(', '));
    setAllowedGroups((c.governance?.allowedGroups ?? []).join(', '));
    setPiiFields((c.governance?.piiFields ?? []).join(', '));
    setEncryptionRequired(c.governance?.encryptionRequired ?? true);
  }

  useEffect(() => {
    if (!contractId) return;
    let cancelled = false;
    setPageLoading(true);
    getContract(contractId)
      .then(c => { if (!cancelled) { setContract(c); populateForm(c); } })
      .catch(err => { if (!cancelled) notifications.notifyError(`Failed to load contract: ${err.message}`); })
      .finally(() => { if (!cancelled) setPageLoading(false); });
    return () => { cancelled = true; };
  }, [contractId]);

  function updateRule(i: number, patch: Partial<QualityRule>) {
    setQualityRules(prev => prev.map((r, idx) => idx === i ? { ...r, ...patch } : r));
  }

  async function handleSave() {
    if (!contractId) return;
    await saveCall.execute(() => updateContract(contractId, {
      cmoId: cmoId.trim(), dataDomain: dataDomain.trim(), schemaId: schemaId.trim(),
      schemaVersion: schemaVersion.trim(), qualityRules,
      sla: {
        timeliness: { maxDelayHours: Number(maxDelayHours), measurementWindow: timelinessWindow },
        availability: { uptimePercentage: Number(uptimePercentage), measurementWindow: availabilityWindow },
        quality: { minQualityScore: Number(minQualityScore), measurementWindow: qualityWindow },
      },
      deliverySchedule: {
        frequency: frequency.value as DataContract['deliverySchedule']['frequency'],
        ...(cronExpression.trim() ? { cronExpression: cronExpression.trim() } : {}),
        timezone: timezone.trim() || 'UTC',
      },
      governance: {
        dataClassification: dataClassification.value as DataContract['governance']['dataClassification'],
        retentionYears: Number(retentionYears),
        allowedUsers: allowedUsers.split(',').map(s => s.trim()).filter(Boolean),
        allowedGroups: allowedGroups.split(',').map(s => s.trim()).filter(Boolean),
        piiFields: piiFields.split(',').map(s => s.trim()).filter(Boolean),
        encryptionRequired,
      },
    }), 'Contract updated successfully.');
  }

  async function handleAction(action: () => Promise<DataContract>, successMsg: string) {
    if (!contractId) return;
    setActionLoading(true);
    try {
      const updated = await action();
      setStatus(updated.status);
      notifications.notifySuccess(successMsg);
    } catch (err: unknown) {
      notifications.notifyError(err instanceof Error ? err.message : 'Action failed');
    } finally {
      setActionLoading(false);
    }
  }

  async function handleReject() {
    if (!contractId) return;
    setRejectModalOpen(false);
    await handleAction(() => rejectContract(contractId, rejectReason), 'Contract rejected.');
    setRejectReason('');
  }

  // Determine which action buttons to show
  const canEdit = user?.isMerckAdmin && status === 'draft';
  const canSubmit = user?.isMerckAdmin && status === 'draft';
  const canAccept = user?.isCMOUser && status === 'pending_cmo_review';
  const canApprove = user?.isMerckAdmin && status === 'pending_merck_approval';
  const canReject = (user?.isMerckAdmin || user?.isCMOUser) &&
    ['pending_cmo_review', 'pending_merck_approval'].includes(status);

  if (pageLoading) return <SpaceBetween size="l"><Header variant="h1">Contract Detail</Header><PageLoadingIndicator label="Loading…" /></SpaceBetween>;

  return (
    <SpaceBetween size="l">
      <Header
        variant="h1"
        description={<StatusIndicator type={statusType(status)}>{statusLabel(status)}</StatusIndicator>}
        actions={
          <SpaceBetween direction="horizontal" size="xs">
            {canReject && <Button loading={actionLoading} onClick={() => setRejectModalOpen(true)}>Reject</Button>}
            {canAccept && <Button variant="primary" loading={actionLoading} onClick={() => handleAction(() => acceptContract(contractId!), 'Contract accepted. Awaiting Merck approval.')}>Accept Contract</Button>}
            {canApprove && <Button variant="primary" loading={actionLoading} onClick={() => handleAction(() => approveContract(contractId!), 'Contract approved and activated!')}>Approve & Activate</Button>}
            {canSubmit && <Button variant="primary" loading={actionLoading} onClick={() => handleAction(() => submitContract(contractId!), 'Contract submitted to CMO for review.')}>Submit to CMO</Button>}
          </SpaceBetween>
        }
      >
        Contract: {contractId}
      </Header>

      <Flashbar items={notifications.items} />

      {status === 'pending_cmo_review' && user?.isCMOUser && (
        <Alert type="info" header="Action required">
          Please review this contract and accept or reject it.
        </Alert>
      )}
      {status === 'pending_merck_approval' && user?.isMerckAdmin && (
        <Alert type="info" header="Action required">
          The CMO has accepted this contract. Please review and approve to activate the pipeline.
        </Alert>
      )}
      {status === 'active' && contract?.connectionId && (
        <Alert type="info">
          This contract uses connection <strong>{contract.connectionId}</strong>. <a href="/connections">View connection details</a>
        </Alert>
      )}
      {status === 'active' && !contract?.connectionId && !contract?.integrationPattern && (
        <Alert type="info">
          No connection linked to this contract. <a href="/connections">Manage connections</a>
        </Alert>
      )}

      <form onSubmit={e => e.preventDefault()}>
        <Form actions={
          canEdit ? (
            <SpaceBetween direction="horizontal" size="xs">
              <Button variant="link" onClick={() => navigate('/data-contracts')}>Back</Button>
              <Button variant="primary" loading={saveCall.loading} onClick={handleSave}>Save Changes</Button>
            </SpaceBetween>
          ) : (
            <Button variant="link" onClick={() => navigate('/data-contracts')}>Back</Button>
          )
        }>
          <SpaceBetween size="l">
            <Container header={<Header variant="h2">Basic Information</Header>}>
              <SpaceBetween size="l">
<FormField label="CMO ID"><Box variant="p">{cmoId}</Box></FormField>
                <FormField label="Product ID"><Box variant="p">{productId || '—'}</Box></FormField>
                <FormField label="Data Domain">{canEdit ? <Input value={dataDomain} onChange={({ detail }) => setDataDomain(detail.value)} /> : <Box variant="p">{dataDomain}</Box>}</FormField>
                <FormField label="Schema ID">{canEdit ? <Input value={schemaId} onChange={({ detail }) => setSchemaId(detail.value)} /> : <Box variant="p">{schemaId}</Box>}</FormField>
                <FormField label="Schema Version">{canEdit ? <Input value={schemaVersion} onChange={({ detail }) => setSchemaVersion(detail.value)} /> : <Box variant="p">{schemaVersion}</Box>}</FormField>
              </SpaceBetween>
            </Container>

            <Container header={<Header variant="h2" actions={canEdit ? <Button onClick={() => setQualityRules(p => [...p, emptyRule()])}>Add Rule</Button> : undefined}>Quality Rules</Header>}>
              <SpaceBetween size="l">
                {qualityRules.map((rule, idx) => (
                  <Container key={idx} header={<Header variant="h3" actions={canEdit && qualityRules.length > 1 ? <Button onClick={() => setQualityRules(p => p.filter((_, i) => i !== idx))}>Remove</Button> : undefined}>Rule {idx + 1}</Header>}>
                    <SpaceBetween size="m">
                      <FormField label="Rule Name">{canEdit ? <Input value={rule.ruleName} onChange={({ detail }) => updateRule(idx, { ruleName: detail.value })} /> : <Box variant="p">{rule.ruleName}</Box>}</FormField>
                      <FormField label="DQDL Expression">{canEdit ? <Input value={rule.expression} onChange={({ detail }) => updateRule(idx, { expression: detail.value })} /> : <Box variant="p">{rule.expression}</Box>}</FormField>
                      <FormField label="Threshold">{canEdit ? <Input value={String(rule.threshold)} onChange={({ detail }) => updateRule(idx, { threshold: Number(detail.value) })} inputMode="decimal" /> : <Box variant="p">{rule.threshold}</Box>}</FormField>
                      {canEdit && <FormField label="Severity"><Select selectedOption={SEVERITY_OPTIONS.find(o => o.value === rule.severity) ?? SEVERITY_OPTIONS[1]} options={SEVERITY_OPTIONS} onChange={({ detail }) => updateRule(idx, { severity: detail.selectedOption.value as QualityRule['severity'] })} /></FormField>}
                    </SpaceBetween>
                  </Container>
                ))}
              </SpaceBetween>
            </Container>

            {/* Element SLAs */}
            {(() => {
              const slas = contract?.elementSlas;
              if (!slas?.length) return null;
              const labels: Record<string, string> = {
                bmr: 'BMR', coa: 'CoA', in_process: 'In-Process', yield: 'Yield',
                deviation: 'Deviation', env_monitoring: 'Env. Monitoring',
              };
              return (
                <Container header={<Header variant="h2">Data Submission SLAs</Header>}>
                  <SpaceBetween size="s">
                    {slas.map((s, i) => (
                      <Box key={i}><strong>{labels[s.elementType] ?? s.elementType}:</strong> within {s.maxDaysAfterBatch} business day(s) of batch completion</Box>
                    ))}
                  </SpaceBetween>
                </Container>
              );
            })()}

            <Container header={<Header variant="h2">Service Level Agreements</Header>}>
              <SpaceBetween size="l">
                <FormField label="Max Delay Hours">{canEdit ? <Input value={maxDelayHours} onChange={({ detail }) => setMaxDelayHours(detail.value)} inputMode="decimal" /> : <Box variant="p">{maxDelayHours} hours</Box>}</FormField>
                <FormField label="Uptime %">{canEdit ? <Input value={uptimePercentage} onChange={({ detail }) => setUptimePercentage(detail.value)} inputMode="decimal" /> : <Box variant="p">{uptimePercentage}%</Box>}</FormField>
                <FormField label="Min Quality Score">{canEdit ? <Input value={minQualityScore} onChange={({ detail }) => setMinQualityScore(detail.value)} inputMode="decimal" /> : <Box variant="p">{minQualityScore}</Box>}</FormField>
              </SpaceBetween>
            </Container>

            <Container header={<Header variant="h2">Delivery Schedule</Header>}>
              <SpaceBetween size="l">
                <FormField label="Frequency">{canEdit ? <Select selectedOption={frequency} options={FREQUENCY_OPTIONS} onChange={({ detail }) => setFrequency(detail.selectedOption)} /> : <Box variant="p">{frequency.label}</Box>}</FormField>
                <FormField label="Timezone">{canEdit ? <Input value={timezone} onChange={({ detail }) => setTimezone(detail.value)} /> : <Box variant="p">{timezone}</Box>}</FormField>
              </SpaceBetween>
            </Container>

            <Container header={<Header variant="h2">Governance</Header>}>
              <SpaceBetween size="l">
                <FormField label="Data Classification">{canEdit ? <Select selectedOption={dataClassification} options={CLASSIFICATION_OPTIONS} onChange={({ detail }) => setDataClassification(detail.selectedOption)} /> : <Box variant="p">{dataClassification.label}</Box>}</FormField>
                <FormField label="Retention Years">{canEdit ? <Input value={retentionYears} onChange={({ detail }) => setRetentionYears(detail.value)} inputMode="numeric" /> : <Box variant="p">{retentionYears} years</Box>}</FormField>
                <FormField label="Encryption"><Checkbox checked={encryptionRequired} onChange={canEdit ? ({ detail }) => setEncryptionRequired(detail.checked) : undefined}>Required</Checkbox></FormField>
              </SpaceBetween>
            </Container>
          </SpaceBetween>
        </Form>
      </form>

      <Modal
        visible={rejectModalOpen}
        onDismiss={() => setRejectModalOpen(false)}
        header="Reject Contract"
        footer={
          <SpaceBetween direction="horizontal" size="xs">
            <Button variant="link" onClick={() => setRejectModalOpen(false)}>Cancel</Button>
            <Button variant="primary" onClick={handleReject}>Confirm Rejection</Button>
          </SpaceBetween>
        }
      >
        <FormField label="Reason for rejection">
          <Textarea value={rejectReason} onChange={({ detail }) => setRejectReason(detail.value)} placeholder="Please provide a reason…" />
        </FormField>
      </Modal>
    </SpaceBetween>
  );
}
