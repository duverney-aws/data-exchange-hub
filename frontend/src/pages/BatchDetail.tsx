import { useEffect, useRef, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import Alert from '@cloudscape-design/components/alert';
import Badge from '@cloudscape-design/components/badge';
import Box from '@cloudscape-design/components/box';
import Button from '@cloudscape-design/components/button';
import ColumnLayout from '@cloudscape-design/components/column-layout';
import Container from '@cloudscape-design/components/container';
import Flashbar, { FlashbarProps } from '@cloudscape-design/components/flashbar';
import Header from '@cloudscape-design/components/header';
import Modal from '@cloudscape-design/components/modal';
import SpaceBetween from '@cloudscape-design/components/space-between';
import Spinner from '@cloudscape-design/components/spinner';
import StatusIndicator from '@cloudscape-design/components/status-indicator';
import Table from '@cloudscape-design/components/table';
import { useAuth } from '../context/AuthContext';
import {
  Batch, DataElementStatus, Connection,
  getBatch, markElementReceived, submitBatch, getBatchConnections, uploadFile, getElementViewData,
} from '../services/api';

const ELEMENT_LABELS: Record<string, string> = {
  bmr:        'Batch Manufacturing Record (BMR)',
  coa:        'Certificate of Analysis (CoA)',
  in_process: 'In-Process Test Results',
  yield:      'Yield / Reconciliation Data',
};

const STATUS_MAP: Record<string, { type: 'success' | 'in-progress' | 'pending'; label: string }> = {
  in_progress: { type: 'in-progress', label: 'In Progress' },
  submitted:   { type: 'pending',     label: 'Submitted' },
  complete:    { type: 'success',     label: 'Complete' },
};

// ── CoA Viewer ────────────────────────────────────────────────────

interface TextractResult {
  sourceFile: string;
  confidence: number;
  forms: Record<string, string>;
  tables: string[][][];
  processedAt: string;
  lotNumber?: string;
  batchId?: string;
}

function CoAViewer({ batchId, elementType, label, onClose }: {
  batchId: string;
  elementType: string;
  label: string;
  onClose: () => void;
}) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<TextractResult | null>(null);

  useEffect(() => {
    getElementViewData(batchId, elementType)
      .then((d) => setData(d as TextractResult))
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, [batchId, elementType]);

  // Find the test results table — the one whose first row has ≥4 columns (header row)
  const testTable = data?.tables?.find((t) => t[0]?.length >= 4) ?? null;
  const testHeaders = testTable?.[0] ?? [];
  const testRows = testTable?.slice(1) ?? [];

  // Key header fields to highlight
  const headerFields = ['Product Name', 'Batch / Lot', 'Mfg Date', 'Expiry Date', 'Quantity', 'Disposition:', 'Analyst', 'QA Approver'];
  const headerInfo = headerFields
    .map((k) => ({ key: k.replace(':', ''), value: data?.forms?.[k] ?? '' }))
    .filter((f) => f.value);

  return (
    <Modal
      visible
      onDismiss={onClose}
      size="large"
      header={<Header variant="h2">{label}</Header>}
      footer={<Button onClick={onClose}>Close</Button>}
    >
      {loading && <Box textAlign="center"><Spinner /> Loading…</Box>}
      {error && <Alert type="error">{error}</Alert>}
      {data && (
        <SpaceBetween size="l">
          {/* Confidence + metadata */}
          <Box>
            <SpaceBetween direction="horizontal" size="s">
              <Badge color={data.confidence >= 85 ? 'green' : 'red'}>
                AI Confidence: {data.confidence.toFixed(1)}%
              </Badge>
              <Box variant="small" color="text-body-secondary">
                Processed: {new Date(data.processedAt).toLocaleString()} · Source: {data.sourceFile}
              </Box>
            </SpaceBetween>
          </Box>

          {/* Header info — product, lot, disposition */}
          {headerInfo.length > 0 && (
            <Container header={<Header variant="h3">Document Header</Header>}>
              <ColumnLayout columns={2} variant="text-grid">
                {headerInfo.map(({ key, value }) => (
                  <div key={key}>
                    <Box variant="awsui-key-label">{key}</Box>
                    <div style={key === 'Disposition' ? { fontWeight: 'bold', color: value.includes('APPROVED') ? 'green' : 'red' } : {}}>
                      {value}
                    </div>
                  </div>
                ))}
              </ColumnLayout>
            </Container>
          )}

          {/* Test results table */}
          {testTable && (
            <Table
              header={<Header variant="h3">Test Results</Header>}
              columnDefinitions={testHeaders.map((h, i) => ({
                id: String(i),
                header: h,
                cell: (row: string[]) => {
                  const val = row[i] ?? '';
                  if (h === 'Status') {
                    return (
                      <StatusIndicator type={val === 'PASS' ? 'success' : val === 'FAIL' ? 'error' : 'pending'}>
                        {val || '—'}
                      </StatusIndicator>
                    );
                  }
                  return val || '—';
                },
              }))}
              items={testRows}
              trackBy={(row) => row[0]}
              variant="embedded"
            />
          )}
        </SpaceBetween>
      )}
    </Modal>
  );
}

// ── BatchDetail ───────────────────────────────────────────────────

export default function BatchDetail() {
  const { batchId } = useParams<{ batchId: string }>();
  const navigate = useNavigate();
  const { user } = useAuth();
  const [batch, setBatch] = useState<Batch | null>(null);
  const [connections, setConnections] = useState<Connection[]>([]);
  const [loading, setLoading] = useState(true);
  const [flash, setFlash] = useState<FlashbarProps.MessageDefinition[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [markingElement, setMarkingElement] = useState<string | null>(null);
  const [uploadingElement, setUploadingElement] = useState<string | null>(null);
  const [viewingElement, setViewingElement] = useState<string | null>(null);
  const fileInputRefs = useRef<Record<string, HTMLInputElement | null>>({});

  const load = () => {
    if (!batchId) return;
    setLoading(true);
    Promise.all([getBatch(batchId), getBatchConnections(batchId)])
      .then(([b, conns]) => { setBatch(b); setConnections(conns); })
      .catch((e: Error) => setFlash([{ type: 'error', dismissible: true, onDismiss: () => setFlash([]), content: e.message }]))
      .finally(() => setLoading(false));
  };

  useEffect(load, [batchId]);

  const aiConnection = connections.find((c) => c.connectionType === 'ai-unstructured');
  const sftpConnection = connections.find((c) => c.connectionType === 'secure-transfer');
  const sftpConfig = sftpConnection?.config as { hostname?: string } | undefined;

  const handleMarkReceived = async (elementType: string) => {
    if (!batchId) return;
    setMarkingElement(elementType);
    try { setBatch(await markElementReceived(batchId, elementType)); }
    catch (e: unknown) { setFlash([{ type: 'error', dismissible: true, onDismiss: () => setFlash([]), content: (e as Error).message }]); }
    finally { setMarkingElement(null); }
  };

  const handleAiUpload = async (elementType: string) => {
    if (!batchId || !aiConnection || !batch) return;
    const input = fileInputRefs.current[elementType];
    const file = input?.files?.[0];
    if (!file) { setFlash([{ type: 'warning', dismissible: true, onDismiss: () => setFlash([]), content: 'Select a file first.' }]); return; }
    setUploadingElement(elementType);
    try {
      await uploadFile(aiConnection.connectionId, file, batchId, batch.lotNumber, elementType);
      setFlash([{ type: 'success', dismissible: true, onDismiss: () => setFlash([]), content: `${file.name} uploaded. AI processing will begin shortly.` }]);
      setTimeout(load, 2000);
    } catch (e: unknown) {
      setFlash([{ type: 'error', dismissible: true, onDismiss: () => setFlash([]), content: (e as Error).message }]);
    } finally {
      setUploadingElement(null);
      if (input) input.value = '';
    }
  };

  const handleSubmit = async () => {
    if (!batchId) return;
    setSubmitting(true);
    try {
      setBatch(await submitBatch(batchId));
      setFlash([{ type: 'success', dismissible: true, onDismiss: () => setFlash([]), content: 'Batch submitted successfully.' }]);
    } catch (e: unknown) {
      setFlash([{ type: 'error', dismissible: true, onDismiss: () => setFlash([]), content: (e as Error).message }]);
    } finally { setSubmitting(false); }
  };

  if (loading) return <Box>Loading…</Box>;
  if (!batch) return <Box>Batch not found.</Box>;

  const statusInfo = STATUS_MAP[batch.status] ?? { type: 'pending' as const, label: batch.status };
  const canSubmit = user?.isCMOUser && batch.status === 'in_progress';

  return (
    <SpaceBetween size="l">
      <Flashbar items={flash} />

      {viewingElement && batchId && (
        <CoAViewer
          batchId={batchId}
          elementType={viewingElement}
          label={ELEMENT_LABELS[viewingElement] ?? viewingElement}
          onClose={() => setViewingElement(null)}
        />
      )}

      <Header
        variant="h1"
        actions={
          <SpaceBetween direction="horizontal" size="xs">
            <Button onClick={() => navigate('/batches')}>Back to Batches</Button>
            {canSubmit && (
              <Button variant="primary" loading={submitting} onClick={handleSubmit} disabled={!batch.isComplete}>
                Submit Batch
              </Button>
            )}
          </SpaceBetween>
        }
      >
        Batch: {batch.lotNumber}
      </Header>

      <Container header={<Header variant="h2">Batch Details</Header>}>
        <ColumnLayout columns={3} variant="text-grid">
          <div><Box variant="awsui-key-label">Lot Number</Box><div>{batch.lotNumber}</div></div>
          <div><Box variant="awsui-key-label">Product ID</Box><div>{batch.productId}</div></div>
          <div><Box variant="awsui-key-label">CMO</Box><div>{batch.cmoId}</div></div>
          <div><Box variant="awsui-key-label">Manufacturing Date</Box><div>{batch.manufacturingDate}</div></div>
          <div>
            <Box variant="awsui-key-label">Status</Box>
            <StatusIndicator type={statusInfo.type}>{statusInfo.label}</StatusIndicator>
          </div>
          {batch.submittedAt && (
            <div><Box variant="awsui-key-label">Submitted At</Box><div>{new Date(batch.submittedAt).toLocaleString()}</div></div>
          )}
          {batch.notes && <div><Box variant="awsui-key-label">Notes</Box><div>{batch.notes}</div></div>}
        </ColumnLayout>
      </Container>

      {user?.isCMOUser && sftpConnection && sftpConfig?.hostname && (
        <Container header={<Header variant="h2">SFTP Upload Instructions</Header>}>
          <SpaceBetween size="s">
            <Alert type="info">
              Upload files to <strong>{sftpConfig.hostname}</strong>. Place each file in its own subdirectory so it is automatically tagged to this lot.
            </Alert>
            <Box variant="code">
              {Object.keys(ELEMENT_LABELS).map(et => (
                <div key={et}>/{batch.batchId}/{et}/{'<filename>'}</div>
              ))}
            </Box>
            <Box variant="small" color="text-body-secondary">
              Files stored in data lake under <strong>lot={batch.lotNumber}</strong>
            </Box>
          </SpaceBetween>
        </Container>
      )}

      <Table
        header={
          <Header
            variant="h2"
            description={batch.isComplete ? 'All required data elements received.' : `${batch.missingElements.length} element(s) still missing.`}
          >
            Required Data Elements
          </Header>
        }
        columnDefinitions={[
          {
            id: 'element',
            header: 'Data Element',
            cell: (el: DataElementStatus) => ELEMENT_LABELS[el.elementType] ?? el.elementType,
          },
          {
            id: 'status',
            header: 'Status',
            cell: (el: DataElementStatus) => (
              <StatusIndicator type={el.received ? 'success' : el.overdue ? 'error' : 'pending'}>
                {el.received ? 'Received' : el.overdue ? 'Overdue' : 'Pending'}
              </StatusIndicator>
            ),
          },
          {
            id: 'receivedAt',
            header: 'Received At',
            cell: (el: DataElementStatus) => el.receivedAt ? new Date(el.receivedAt).toLocaleString() : '—',
          },
          {
            id: 'action',
            header: '',
            cell: (el: DataElementStatus) => {
              const actions: React.ReactNode[] = [];

              // View button — any received element with an s3Path (both roles)
              if (el.received && el.s3Path) {
                actions.push(
                  <Button key="view" variant="inline-link" onClick={() => setViewingElement(el.elementType)}>
                    View
                  </Button>
                );
              }

              // Upload / mark received — CMO only, not yet received, batch in progress
              if (user?.isCMOUser && !el.received && batch.status === 'in_progress') {
                if (aiConnection) {
                  actions.push(
                    <span key="upload">
                      <input
                        type="file"
                        accept=".pdf,.png,.jpg,.jpeg,.tiff"
                        style={{ display: 'none' }}
                        id={`file-${el.elementType}`}
                        ref={r => { fileInputRefs.current[el.elementType] = r; }}
                      />
                      <Button variant="inline-link" onClick={() => document.getElementById(`file-${el.elementType}`)?.click()}>
                        Choose file
                      </Button>
                      <Button variant="inline-link" loading={uploadingElement === el.elementType} onClick={() => handleAiUpload(el.elementType)}>
                        Upload
                      </Button>
                    </span>
                  );
                } else {
                  actions.push(
                    <Button key="mark" variant="inline-link" loading={markingElement === el.elementType} onClick={() => handleMarkReceived(el.elementType)}>
                      Mark Received
                    </Button>
                  );
                }
              }

              return actions.length > 0 ? <SpaceBetween direction="horizontal" size="xs">{actions}</SpaceBetween> : null;
            },
          },
        ]}
        items={batch.dataElements}
        trackBy="elementType"
      />
    </SpaceBetween>
  );
}
