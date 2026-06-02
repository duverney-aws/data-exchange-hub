import { useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import Alert from '@cloudscape-design/components/alert';
import Box from '@cloudscape-design/components/box';
import Button from '@cloudscape-design/components/button';
import Cards from '@cloudscape-design/components/cards';
import Container from '@cloudscape-design/components/container';
import Flashbar, { FlashbarProps } from '@cloudscape-design/components/flashbar';
import Form from '@cloudscape-design/components/form';
import FormField from '@cloudscape-design/components/form-field';
import Header from '@cloudscape-design/components/header';
import Input from '@cloudscape-design/components/input';
import Select, { SelectProps } from '@cloudscape-design/components/select';
import SpaceBetween from '@cloudscape-design/components/space-between';
import Textarea from '@cloudscape-design/components/textarea';
import {
  activateContractPipeline,
  IntegrationPattern,
  PatternConfig,
} from '../services/api';

// --- Pattern card definitions ---

interface PatternCardItem {
  id: IntegrationPattern;
  title: string;
  description: string;
  tags: string[];
}

const PATTERN_CARDS: PatternCardItem[] = [
  {
    id: 'native-connector',
    title: 'Pattern 1: Native Database Connectors',
    description:
      'Connect directly to modern data platforms. Merck pulls data from your database using native or JDBC connectors.',
    tags: ['Snowflake', 'Oracle', 'SQL Server', 'PostgreSQL', 'SAP', 'Databricks'],
  },
  {
    id: 'secure-transfer',
    title: 'Pattern 2: Secure File Transfer (SFTP)',
    description:
      'Upload files via a managed SFTP endpoint. Works with any system that can export CSV, JSON, or Parquet files.',
    tags: ['CSV', 'JSON', 'Parquet', 'Legacy Systems', 'Universal'],
  },
  {
    id: 'ai-unstructured',
    title: 'Pattern 3: AI-Powered Unstructured Data',
    description:
      'Upload PDFs, images, and scanned documents. AI extracts structured data automatically using Amazon Textract and Rekognition.',
    tags: ['PDF', 'Images', 'Textract', 'Rekognition', 'AI Extraction'],
  },
];

// --- Connection type options for Pattern 1 ---

const CONNECTION_TYPE_OPTIONS: SelectProps.Option[] = [
  { value: 'snowflake', label: 'Snowflake' },
  { value: 'oracle', label: 'Oracle (JDBC)' },
  { value: 'sqlserver', label: 'SQL Server (JDBC)' },
  { value: 'postgresql', label: 'PostgreSQL (JDBC)' },
  { value: 'sap', label: 'SAP HANA (JDBC)' },
  { value: 'databricks', label: 'Databricks' },
];

// --- Document type options for Pattern 3 ---

const DOCUMENT_TYPE_OPTIONS: SelectProps.Option[] = [
  { value: 'pdf', label: 'PDF Documents' },
  { value: 'png', label: 'PNG Images' },
  { value: 'jpg', label: 'JPEG Images' },
  { value: 'tiff', label: 'TIFF Images' },
];


// --- Pattern 1 config form ---

function NativeConnectorForm({
  config,
  onChange,
  errors,
}: {
  config: PatternConfig;
  onChange: (patch: Partial<PatternConfig>) => void;
  errors: Record<string, string>;
}) {
  const selectedType = CONNECTION_TYPE_OPTIONS.find(
    (o) => o.value === config.connectionType
  ) ?? CONNECTION_TYPE_OPTIONS[0];

  return (
    <Container header={<Header variant="h2">Native Connector Configuration</Header>}>
      <SpaceBetween size="l">
        <FormField label="Connection type" errorText={errors.connectionType}>
          <Select
            selectedOption={selectedType}
            options={CONNECTION_TYPE_OPTIONS}
            onChange={({ detail }) =>
              onChange({ connectionType: detail.selectedOption.value })
            }
          />
        </FormField>
        <FormField
          label="Connection URL"
          description="JDBC URL or native connection string"
          errorText={errors.connectionUrl}
        >
          <Input
            value={config.connectionUrl ?? ''}
            onChange={({ detail }) => onChange({ connectionUrl: detail.value })}
            placeholder="jdbc:oracle:thin:@host:1521:orcl"
          />
        </FormField>
        <FormField label="Username" errorText={errors.username}>
          <Input
            value={config.username ?? ''}
            onChange={({ detail }) => onChange({ username: detail.value })}
            placeholder="db_user"
          />
        </FormField>
        <FormField label="Password" errorText={errors.password}>
          <Input
            value={config.password ?? ''}
            onChange={({ detail }) => onChange({ password: detail.value })}
            type="password"
            placeholder="••••••••"
          />
        </FormField>
        <FormField label="Database" errorText={errors.database}>
          <Input
            value={config.database ?? ''}
            onChange={({ detail }) => onChange({ database: detail.value })}
            placeholder="production_db"
          />
        </FormField>
        <FormField label="Schema">
          <Input
            value={config.schema ?? ''}
            onChange={({ detail }) => onChange({ schema: detail.value })}
            placeholder="public"
          />
        </FormField>
        <FormField label="Table or query">
          <Input
            value={config.tableOrQuery ?? ''}
            onChange={({ detail }) => onChange({ tableOrQuery: detail.value })}
            placeholder="batch_records"
          />
        </FormField>
      </SpaceBetween>
    </Container>
  );
}


// --- Pattern 2 SFTP credential display ---

function SecureTransferDisplay({
  sftpCredentials,
}: {
  sftpCredentials: { hostname: string; username: string; password: string } | null;
}) {
  if (!sftpCredentials) {
    return (
      <Container header={<Header variant="h2">Secure File Transfer (SFTP)</Header>}>
        <Alert type="info">
          SFTP credentials will be provisioned automatically when you activate the
          pipeline. Click "Activate Pipeline" below to generate your SFTP endpoint.
        </Alert>
      </Container>
    );
  }

  return (
    <Container header={<Header variant="h2">SFTP Connection Details</Header>}>
      <SpaceBetween size="l">
        <Alert type="success">
          Your SFTP endpoint has been provisioned. Use the credentials below to
          upload files.
        </Alert>
        <FormField label="Hostname">
          <Input value={sftpCredentials.hostname} readOnly />
        </FormField>
        <FormField label="Username">
          <Input value={sftpCredentials.username} readOnly />
        </FormField>
        <FormField label="Password">
          <Input value={sftpCredentials.password} type="password" readOnly />
        </FormField>
        <Box variant="small" color="text-body-secondary">
          Supported file formats: CSV, JSON, Parquet. Files uploaded to the SFTP
          endpoint are automatically detected and processed.
        </Box>
      </SpaceBetween>
    </Container>
  );
}


// --- Pattern 3 document upload form ---

function AIUnstructuredForm({
  config,
  onChange,
  selectedFiles,
  onFilesChange,
}: {
  config: PatternConfig;
  onChange: (patch: Partial<PatternConfig>) => void;
  selectedFiles: File[];
  onFilesChange: (files: File[]) => void;
}) {
  const selectedDocType = DOCUMENT_TYPE_OPTIONS.find(
    (o) => o.value === config.documentType
  ) ?? DOCUMENT_TYPE_OPTIONS[0];

  function handleFileInput(e: React.ChangeEvent<HTMLInputElement>) {
    if (e.target.files) {
      onFilesChange(Array.from(e.target.files));
    }
  }

  return (
    <Container header={<Header variant="h2">AI Document Processing Configuration</Header>}>
      <SpaceBetween size="l">
        <FormField label="Document type">
          <Select
            selectedOption={selectedDocType}
            options={DOCUMENT_TYPE_OPTIONS}
            onChange={({ detail }) =>
              onChange({ documentType: detail.selectedOption.value })
            }
          />
        </FormField>
        <FormField
          label="Confidence threshold (%)"
          description="Records below this confidence are flagged for manual review (default 85%)"
        >
          <Input
            value={String(config.confidenceThreshold ?? 85)}
            onChange={({ detail }) =>
              onChange({ confidenceThreshold: Number(detail.value) })
            }
            inputMode="decimal"
          />
        </FormField>
        <FormField
          label="Upload documents"
          description="Select PDF or image files to process"
        >
          <input
            type="file"
            accept=".pdf,.png,.jpg,.jpeg,.tiff,.tif"
            multiple
            onChange={handleFileInput}
            aria-label="Upload documents for AI processing"
          />
        </FormField>
        {selectedFiles.length > 0 && (
          <Box variant="small">
            {selectedFiles.length} file(s) selected:{' '}
            {selectedFiles.map((f) => f.name).join(', ')}
          </Box>
        )}
        <FormField
          label="Processing notes (optional)"
          description="Additional instructions for document extraction"
        >
          <Textarea
            value={config.processingNotes ?? ''}
            onChange={({ detail }) => onChange({ processingNotes: detail.value })}
            placeholder="e.g., Focus on tables in section 3, ignore headers"
            rows={3}
          />
        </FormField>
      </SpaceBetween>
    </Container>
  );
}


// --- Main page component ---

export default function IntegrationPatternSelection() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const contractId = searchParams.get('contractId') ?? '';

  const [selectedPattern, setSelectedPattern] = useState<IntegrationPattern | null>(null);
  const [config, setConfig] = useState<PatternConfig>({
    connectionType: 'snowflake',
    connectionUrl: '',
    username: '',
    password: '',
    database: '',
    schema: '',
    tableOrQuery: '',
    documentType: 'pdf',
    confidenceThreshold: 85,
    processingNotes: '',
  });
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [sftpCredentials, setSftpCredentials] = useState<{
    hostname: string;
    username: string;
    password: string;
  } | null>(null);
  const [configErrors, setConfigErrors] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);
  const [flashItems, setFlashItems] = useState<FlashbarProps.MessageDefinition[]>([]);

  function updateConfig(patch: Partial<PatternConfig>) {
    setConfig((prev) => ({ ...prev, ...patch }));
    // Clear errors for changed fields
    const clearedErrors = { ...configErrors };
    for (const key of Object.keys(patch)) {
      delete clearedErrors[key];
    }
    setConfigErrors(clearedErrors);
  }

  function validateNativeConnector(): Record<string, string> {
    const errs: Record<string, string> = {};
    if (!config.connectionUrl?.trim()) errs.connectionUrl = 'Connection URL is required.';
    if (!config.username?.trim()) errs.username = 'Username is required.';
    if (!config.password?.trim()) errs.password = 'Password is required.';
    if (!config.database?.trim()) errs.database = 'Database is required.';
    return errs;
  }

  async function handleActivate() {
    if (!selectedPattern) {
      setFlashItems([{
        type: 'error',
        dismissible: true,
        onDismiss: () => setFlashItems([]),
        content: 'Please select an integration pattern before activating.',
      }]);
      return;
    }

    // Validate Pattern 1 fields
    if (selectedPattern === 'native-connector') {
      const errs = validateNativeConnector();
      setConfigErrors(errs);
      if (Object.keys(errs).length > 0) return;
    }

    setLoading(true);
    setFlashItems([]);
    try {
      const result = await activateContractPipeline(contractId, {
        integrationPattern: selectedPattern,
        config,
      });

      if (selectedPattern === 'secure-transfer' && result.sftpCredentials) {
        setSftpCredentials(result.sftpCredentials);
      }

      setFlashItems([{
        type: 'success',
        dismissible: true,
        onDismiss: () => setFlashItems([]),
        content: `Pipeline activated successfully. Status: ${result.status}`,
      }]);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'An unexpected error occurred.';
      setFlashItems([{
        type: 'error',
        dismissible: true,
        onDismiss: () => setFlashItems([]),
        content: `Pipeline activation failed: ${message}`,
      }]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <SpaceBetween size="l">
      <Header
        variant="h1"
        description="Choose how your organization will share data with Merck"
      >
        Integration Pattern Selection
      </Header>
      <Flashbar items={flashItems} />

      {contractId && (
        <Alert type="info">
          Configuring integration for contract: <strong>{contractId}</strong>
        </Alert>
      )}

      {/* Pattern selection cards */}
      <Cards
        cardDefinition={{
          header: (item) => item.title,
          sections: [
            {
              id: 'description',
              content: (item) => item.description,
            },
            {
              id: 'tags',
              header: 'Supported technologies',
              content: (item) => item.tags.join(' · '),
            },
          ],
        }}
        items={PATTERN_CARDS}
        selectionType="single"
        selectedItems={
          selectedPattern
            ? PATTERN_CARDS.filter((c) => c.id === selectedPattern)
            : []
        }
        onSelectionChange={({ detail }) => {
          const selected = detail.selectedItems[0];
          if (selected) {
            setSelectedPattern(selected.id);
            setSftpCredentials(null);
            setConfigErrors({});
          }
        }}
        header={<Header variant="h2">Select an Integration Pattern</Header>}
        empty={<Box textAlign="center">No patterns available.</Box>}
      />

      {/* Pattern-specific configuration */}
      {selectedPattern === 'native-connector' && (
        <NativeConnectorForm
          config={config}
          onChange={updateConfig}
          errors={configErrors}
        />
      )}

      {selectedPattern === 'secure-transfer' && (
        <SecureTransferDisplay sftpCredentials={sftpCredentials} />
      )}

      {selectedPattern === 'ai-unstructured' && (
        <AIUnstructuredForm
          config={config}
          onChange={updateConfig}
          selectedFiles={selectedFiles}
          onFilesChange={setSelectedFiles}
        />
      )}

      {/* Actions */}
      {selectedPattern && (
        <Form
          actions={
            <SpaceBetween direction="horizontal" size="xs">
              <Button variant="link" onClick={() => navigate('/data-contracts')}>
                Cancel
              </Button>
              <Button variant="primary" loading={loading} onClick={handleActivate}>
                Activate Pipeline
              </Button>
            </SpaceBetween>
          }
        >
          <span />
        </Form>
      )}
    </SpaceBetween>
  );
}
