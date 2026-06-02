import { useEffect, useState, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import Alert from '@cloudscape-design/components/alert';
import Box from '@cloudscape-design/components/box';
import Button from '@cloudscape-design/components/button';
import Flashbar, { FlashbarProps } from '@cloudscape-design/components/flashbar';
import Header from '@cloudscape-design/components/header';
import SpaceBetween from '@cloudscape-design/components/space-between';
import StatusIndicator from '@cloudscape-design/components/status-indicator';
import { TableProps } from '@cloudscape-design/components/table';
import DataTable from '../components/DataTable';
import PageLoadingIndicator from '../components/PageLoadingIndicator';
import { DataContract, listContracts, getPipelineStatus, PipelineStatus, listConnections, Connection } from '../services/api';

const REFRESH_INTERVAL_MS = 10_000;

type PipelineRow = DataContract & { pipelineStatus?: PipelineStatus; [key: string]: unknown };

function statusType(status: string): 'success' | 'info' | 'loading' | 'error' | 'stopped' {
  switch (status) {
    case 'active': return 'success';
    case 'deploying': return 'loading';
    case 'failed': return 'error';
    default: return 'stopped';
  }
}

function statusLabel(status: string): string {
  switch (status) {
    case 'active': return 'Active';
    case 'deploying': return 'Deploying';
    case 'failed': return 'Failed';
    case 'suspended': return 'Suspended';
    default: return 'Draft';
  }
}

function patternLabel(pattern?: string): string {
  switch (pattern) {
    case 'native-connector': return 'Native Connector';
    case 'secure-transfer': return 'Secure Transfer (SFTP)';
    case 'ai-unstructured': return 'AI Unstructured';
    default: return '—';
  }
}

function errorGuidance(errorMessage?: string): string {
  if (!errorMessage) return 'An unknown error occurred. Please try activating the pipeline again or contact support.';
  if (errorMessage.toLowerCase().includes('timeout')) return `${errorMessage} — Try activating again. If the issue persists, check your network connectivity and contact support.`;
  if (errorMessage.toLowerCase().includes('credential') || errorMessage.toLowerCase().includes('auth')) return `${errorMessage} — Verify your connection credentials are correct and have the required permissions.`;
  if (errorMessage.toLowerCase().includes('schema')) return `${errorMessage} — Review your data contract schema definition and ensure it is valid.`;
  return `${errorMessage} — Review the error details and try again. If the issue persists, contact support.`;
}

function resolveStatus(row: PipelineRow): string {
  return row.pipelineStatus?.status ?? row.status;
}

export default function Pipelines() {
  const navigate = useNavigate();
  const [rows, setRows] = useState<PipelineRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [flashItems, setFlashItems] = useState<FlashbarProps.MessageDefinition[]>([]);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const [connections, setConnections] = useState<Connection[]>([]);

  const fetchData = useCallback(async () => {
    try {
      const [contracts, conns] = await Promise.all([listContracts(), listConnections()]);
      setConnections(conns);
      const withStatus: PipelineRow[] = await Promise.all(
        contracts.map(async (c) => {
          try {
            const ps = await getPipelineStatus(c.contractId);
            return { ...c, pipelineStatus: ps };
          } catch {
            return { ...c };
          }
        }),
      );
      setRows(withStatus);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Unknown error';
      setFlashItems([{
        type: 'error',
        dismissible: true,
        onDismiss: () => setFlashItems([]),
        content: `Failed to load pipelines: ${message}`,
      }]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Auto-refresh when any pipeline is deploying
  useEffect(() => {
    const hasDeploying = rows.some(
      (r) => r.pipelineStatus?.status === 'deploying',
    );
    if (hasDeploying && !timerRef.current) {
      timerRef.current = setInterval(fetchData, REFRESH_INTERVAL_MS);
    } else if (!hasDeploying && timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    };
  }, [rows, fetchData]);

  const columnDefinitions: TableProps.ColumnDefinition<PipelineRow>[] = [
    {
      id: 'contractId',
      header: 'Contract ID',
      cell: (row) => row.contractId,
      sortingField: 'contractId',
    },
    {
      id: 'cmoId',
      header: 'CMO',
      cell: (row) => row.cmoId,
      sortingField: 'cmoId',
    },
    {
      id: 'dataDomain',
      header: 'Data Domain',
      cell: (row) => row.dataDomain,
    },
    {
      id: 'pattern',
      header: 'Integration Pattern',
      cell: (row) => {
        const conn = connections.find(c => c.connectionId === row.connectionId);
        return patternLabel(conn?.connectionType || row.integrationPattern);
      },
    },
    {
      id: 'status',
      header: 'Pipeline Status',
      cell: (row) => {
        const s = resolveStatus(row);
        return <StatusIndicator type={statusType(s)}>{statusLabel(s)}</StatusIndicator>;
      },
      sortingField: 'status',
    },
    {
      id: 'actions',
      header: 'Actions',
      cell: (row) => {
        const s = resolveStatus(row);
        return (
          <SpaceBetween direction="horizontal" size="xs">
            {s === 'draft' && (
              <Button
                variant="primary"
                onClick={() => navigate(`/integration-patterns?contractId=${row.contractId}`)}
              >
                Activate
              </Button>
            )}
            <Button
              variant="normal"
              onClick={() => setExpandedId(expandedId === row.contractId ? null : row.contractId)}
            >
              {expandedId === row.contractId ? 'Hide Details' : 'View Details'}
            </Button>
          </SpaceBetween>
        );
      },
    },
  ];

  if (loading) {
    return (
      <SpaceBetween size="l">
        <Header variant="h1" description="Activate and monitor data pipelines">Pipelines</Header>
        <PageLoadingIndicator label="Loading pipelines…" />
      </SpaceBetween>
    );
  }

  return (
    <SpaceBetween size="l">
      <Header variant="h1" description="Activate and monitor data pipelines">Pipelines</Header>
      <Flashbar items={flashItems} />
      <DataTable<PipelineRow>
        items={rows}
        columnDefinitions={columnDefinitions}
        trackBy="contractId"
        filteringPlaceholder="Find pipelines"
        pageSize={10}
        variant="full-page"
        header={
          <Header counter={`(${rows.length})`} actions={<Button iconName="refresh" onClick={fetchData}>Refresh</Button>}>
            Pipeline Overview
          </Header>
        }
        empty="No pipelines found. Create a data contract to get started."
      />

      {expandedId && (() => {
        const row = rows.find((r) => r.contractId === expandedId);
        if (!row) return null;
        const s = resolveStatus(row);
        const ps = row.pipelineStatus;
        const ed = ps?.executionDetails;
        return (
          <SpaceBetween size="s">
            {s === 'failed' && (
              <Alert type="error" header="Pipeline Deployment Failed">
                {errorGuidance(ps?.errorMessage)}
              </Alert>
            )}

            {ps?.connectionType === 'secure-transfer' && ed && (
              <Alert type={ed.totalFilesReceived === 0 ? 'warning' : 'info'} header="SFTP Pipeline — File Transfer Status">
                <SpaceBetween size="xs">
                  {ed.totalFilesReceived !== undefined && <Box><b>Files received:</b> {ed.totalFilesReceived}</Box>}
                  {ed.lastFileReceived && <Box><b>Last file:</b> {ed.lastFileReceived}</Box>}
                  {ed.lastFileSize !== undefined && <Box><b>File size:</b> {(ed.lastFileSize / 1024).toFixed(1)} KB</Box>}
                  {ed.lastReceivedAt && <Box><b>Last received:</b> {new Date(ed.lastReceivedAt).toLocaleString()}</Box>}
                  {ed.bronzePath && <Box><b>Bronze path:</b> <code>{ed.bronzePath}</code></Box>}
                  {ed.message && <Box>{ed.message}</Box>}
                </SpaceBetween>
              </Alert>
            )}

            {ps?.connectionType === 'ai-unstructured' && ed && (
              <Alert type={ed.manualReviewPending ? 'warning' : 'info'} header="AI Pipeline — Document Processing Status">
                <SpaceBetween size="xs">
                  {ed.totalDocumentsProcessed !== undefined && <Box><b>Documents processed:</b> {ed.totalDocumentsProcessed}</Box>}
                  {ed.manualReviewPending !== undefined && <Box><b>Pending manual review:</b> {ed.manualReviewPending}{ed.manualReviewPending > 0 ? ' ⚠️ Low confidence — human review required' : ''}</Box>}
                  {ed.lastDocument && <Box><b>Last document:</b> {ed.lastDocument}</Box>}
                  {ed.lastProcessedAt && <Box><b>Last processed:</b> {new Date(ed.lastProcessedAt).toLocaleString()}</Box>}
                  {ed.bronzePath && <Box><b>Bronze path:</b> <code>{ed.bronzePath}</code></Box>}
                </SpaceBetween>
              </Alert>
            )}

            {ps?.connectionType === 'native-connector' && ed && (
              <Alert
                type={ed.lastRunStatus === 'FAILED' ? 'error' : ed.lastRunStatus === 'SUCCEEDED' ? 'success' : 'info'}
                header="Native Connector — Glue ETL Status"
              >
                <SpaceBetween size="xs">
                  {ed.glueConnectionName && <Box><b>Glue connection:</b> {ed.glueConnectionName}</Box>}
                  {ed.glueJobName && <Box><b>ETL job:</b> {ed.glueJobName}</Box>}
                  {ed.lastRunStatus && <Box><b>Last run status:</b> {ed.lastRunStatus}</Box>}
                  {ed.lastRunStartedAt && <Box><b>Last run started:</b> {new Date(ed.lastRunStartedAt).toLocaleString()}</Box>}
                  {ed.lastRunDuration !== undefined && <Box><b>Duration:</b> {ed.lastRunDuration}s</Box>}
                  {ed.rowsExtracted !== undefined && <Box><b>Rows extracted:</b> {ed.rowsExtracted?.toLocaleString()}</Box>}
                  {ed.message && <Box>{ed.message}</Box>}
                </SpaceBetween>
              </Alert>
            )}

            {!ps?.connectionType && !ps?.errorMessage && (
              <Box variant="small" color="text-body-secondary">No pipeline details available — contract may not have an active connection.</Box>
            )}
          </SpaceBetween>
        );
      })()}
    </SpaceBetween>
  );
}
