// Base URLs injected at build time via Vite env vars.
// Falls back to relative paths for local dev (proxied by vite.config.ts).
const CONTRACT_API = import.meta.env.VITE_CONTRACT_API_URL ?? '';
const NL_QUERY_API = import.meta.env.VITE_NL_QUERY_API_URL ?? '';

async function apiFetch(url: string, init?: RequestInit): Promise<Response> {
  const headers = { ...(init?.headers as Record<string, string> ?? {}), ...await authHeaders() };
  const res = await fetch(url, { ...init, headers });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error(body.error || res.statusText);
  }
  return res;
}

// ── CMO Registration ──────────────────────────────────────────────

export interface CMORegistrationRequest {
  organizationName: string;
  contactEmail: string;
  contactPhone: string;
  address: string;
  gxpCertified: boolean;
}

export interface CMORegistrationResponse {
  cmoId: string;
  organizationName: string;
  contactEmail: string;
  contactPhone: string;
  address: string;
  gxpCertified: boolean;
  createdAt: string;
  status: string;
}

export async function registerCMO(data: CMORegistrationRequest): Promise<CMORegistrationResponse> {
  const res = await apiFetch(`${CONTRACT_API}/api/cmo/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  return res.json();
}

// ── Data Contract Types ───────────────────────────────────────────

export interface QualityRule {
  ruleId: string;
  ruleName: string;
  ruleType: 'completeness' | 'accuracy' | 'uniqueness' | 'consistency';
  expression: string;
  threshold: number;
  severity: 'warning' | 'error';
}

export interface SLA {
  timeliness: { maxDelayHours: number; measurementWindow: string };
  availability: { uptimePercentage: number; measurementWindow: string };
  quality: { minQualityScore: number; measurementWindow: string };
}

export interface DeliverySchedule {
  frequency: 'real-time' | 'hourly' | 'daily' | 'weekly' | 'monthly';
  cronExpression?: string;
  timezone: string;
}

export interface Governance {
  dataClassification: 'public' | 'internal' | 'confidential' | 'restricted';
  retentionYears: number;
  allowedUsers: string[];
  allowedGroups: string[];
  piiFields: string[];
  encryptionRequired: boolean;
}

export interface ElementSla {
  elementType: string;
  maxDaysAfterBatch: number;
}

export interface DataContract {
  contractId: string;
  cmoId: string;
  productId?: string;
  dataDomain: string;
  schemaId: string;
  schemaVersion: string;
  qualityRules: QualityRule[];
  elementSlas?: ElementSla[];
  sla: SLA;
  deliverySchedule: DeliverySchedule;
  governance: Governance;
  status: 'draft' | 'active' | 'suspended';
  createdAt: string;
  updatedAt: string;
  connectionId?: string;
  integrationPattern?: string;
  integrationConfig?: { hostname?: string; username?: string; password?: string };
}

export type CreateContractRequest = Omit<DataContract, 'contractId' | 'status' | 'createdAt' | 'updatedAt'> & { elementSlas?: ElementSla[] };
export type UpdateContractRequest = Partial<CreateContractRequest>;

export interface CMOProfile {
  cmoId: string;
  organizationName: string;
  contactEmail: string;
  contactPhone?: string;
  address?: string;
  status: string;
}

export async function listCMOs(): Promise<CMOProfile[]> {
  const res = await apiFetch(`${CONTRACT_API}/api/cmo`);
  const body = await res.json();
  return Array.isArray(body) ? body : body.cmos ?? [];
}

export async function updateCMO(cmoId: string, data: Partial<Pick<CMOProfile, 'organizationName' | 'contactEmail' | 'contactPhone' | 'address'>>): Promise<void> {
  await apiFetch(`${CONTRACT_API}/api/cmo/${encodeURIComponent(cmoId)}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
}

export async function deactivateCMO(cmoId: string): Promise<void> {
  await apiFetch(`${CONTRACT_API}/api/cmo/${encodeURIComponent(cmoId)}`, { method: 'DELETE' });
}

export async function createContract(data: CreateContractRequest): Promise<DataContract> {
  const res = await apiFetch(`${CONTRACT_API}/api/contract`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  return res.json();
}

export async function getContract(contractId: string): Promise<DataContract> {
  const res = await apiFetch(`${CONTRACT_API}/api/contract/${encodeURIComponent(contractId)}`);
  return res.json();
}

export async function updateContract(contractId: string, data: UpdateContractRequest): Promise<DataContract> {
  const res = await apiFetch(`${CONTRACT_API}/api/contract/${encodeURIComponent(contractId)}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  return res.json();
}

export async function listContracts(cmoId?: string): Promise<DataContract[]> {
  const qs = cmoId ? `?cmoId=${encodeURIComponent(cmoId)}` : '';
  const res = await apiFetch(`${CONTRACT_API}/api/contract${qs}`);
  const body = await res.json();
  return Array.isArray(body) ? body : body.contracts ?? [];
}

// ── Integration Pattern ───────────────────────────────────────────

export type IntegrationPattern = 'native-connector' | 'secure-transfer' | 'ai-unstructured';

export interface PatternConfig {
  connectionType?: string;
  connectionUrl?: string;
  username?: string;
  password?: string;
  database?: string;
  schema?: string;
  tableOrQuery?: string;
  documentType?: string;
  confidenceThreshold?: number;
  processingNotes?: string;
}

export interface ActivatePipelineRequest {
  integrationPattern: IntegrationPattern;
  config: PatternConfig;
}

export interface ActivatePipelineResponse {
  contractId: string;
  status: string;
  sftpCredentials?: { hostname: string; username: string; password: string };
}

export async function activateContractPipeline(
  contractId: string,
  data: ActivatePipelineRequest,
): Promise<ActivatePipelineResponse> {
  const res = await apiFetch(`${CONTRACT_API}/api/contract/${encodeURIComponent(contractId)}/activate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  return res.json();
}

// ── Pipeline Status ───────────────────────────────────────────────

export interface PipelineStatus {
  contractId: string;
  status: 'draft' | 'deploying' | 'active' | 'failed';
  connectionType?: string;
  connectionName?: string;
  lastExecution?: string;
  errorMessage?: string;
  executionDetails?: {
    // SFTP
    lastFileReceived?: string;
    lastFileSize?: number;
    lastReceivedAt?: string;
    totalFilesReceived?: number;
    bronzePath?: string;
    // AI
    totalDocumentsProcessed?: number;
    manualReviewPending?: number;
    lastProcessedAt?: string;
    lastDocument?: string;
    // Native connector
    glueJobName?: string;
    glueConnectionName?: string;
    lastRunStatus?: string;
    lastRunStartedAt?: string;
    lastRunDuration?: number;
    rowsExtracted?: number;
    // Generic
    message?: string;
  };
}

export async function getPipelineStatus(contractId: string): Promise<PipelineStatus> {
  const res = await apiFetch(`${CONTRACT_API}/api/contract/${encodeURIComponent(contractId)}/status`);
  return res.json();
}

// ── Schema (CMO-scoped) ───────────────────────────────────────────

export interface SchemaField {
  name: string;
  type: 'string' | 'integer' | 'double' | 'boolean' | 'timestamp' | 'date' | 'array' | 'object';
  nullable: boolean;
  constraints?: string;
}

export interface Schema {
  schemaId: string;
  cmoId: string;
  name: string;
  fields: SchemaField[];
  version: string;
  status: 'draft' | 'registered';
  registrySchemaName?: string;
  createdAt: string;
  updatedAt: string;
}

export interface InferredSchema {
  fields: SchemaField[];
  sourceFile: string;
  inferredAt: string;
}

export async function listSchemas(cmoId?: string): Promise<Schema[]> {
  const qs = cmoId ? `?cmoId=${encodeURIComponent(cmoId)}` : '';
  const res = await apiFetch(`${CONTRACT_API}/api/schema${qs}`);
  const data = await res.json();
  return data.schemas || [];
}

export async function getSchema(schemaId: string): Promise<Schema> {
  const res = await apiFetch(`${CONTRACT_API}/api/schema/${encodeURIComponent(schemaId)}`);
  return res.json();
}

export async function createSchema(data: { cmoId: string; name: string; fields: SchemaField[] }): Promise<Schema> {
  const res = await apiFetch(`${CONTRACT_API}/api/schema`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  return res.json();
}

export async function inferSchema(file: File): Promise<InferredSchema> {
  const formData = new FormData();
  formData.append('file', file);
  const res = await apiFetch(
    `${CONTRACT_API}/api/schema/infer?filename=${encodeURIComponent(file.name)}&format=${file.name.split('.').pop() ?? 'json'}`,
    { method: 'POST', body: formData },
  );
  return res.json();
}

export async function updateSchema(schemaId: string, data: { name: string; fields: SchemaField[] }): Promise<Schema> {
  const res = await apiFetch(`${CONTRACT_API}/api/schema/${encodeURIComponent(schemaId)}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  return res.json();
}

export async function registerSchemaInRegistry(schemaId: string): Promise<Schema> {
  const res = await apiFetch(`${CONTRACT_API}/api/schema/${encodeURIComponent(schemaId)}/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
  });
  return res.json();
}

// ── Natural Language Query ────────────────────────────────────────

export interface NLQueryRequest {
  query: string;
  user_id: string;
}

export interface NLQueryResponse {
  query: string;
  sql: string | null;
  results: Record<string, unknown>[];
  response: string;
  query_execution_id: string | null;
}

export async function submitNLQuery(data: NLQueryRequest): Promise<NLQueryResponse> {
  const res = await apiFetch(`${NL_QUERY_API}/api/query`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  return res.json();
}

export async function inviteCMOUser(cmoId: string, email: string, firstName: string, lastName: string): Promise<{message: string}> {
  const res = await apiFetch(`${CONTRACT_API}/api/cmo/${encodeURIComponent(cmoId)}/invite`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, firstName, lastName }),
  });
  return res.json();
}

// ── Auth token helper ─────────────────────────────────────────────
// Injected by main.tsx after Amplify is configured
let _getToken: (() => Promise<string | null>) | null = null;
export function setTokenProvider(fn: () => Promise<string | null>) { _getToken = fn; }

async function authHeaders(): Promise<Record<string, string>> {
  if (!_getToken) return {};
  const token = await _getToken().catch(() => null);
  return token ? { Authorization: token } : {};
}

// Override apiFetch to include auth — re-export patched version
export async function authFetch(url: string, init?: RequestInit): Promise<Response> {
  const headers = { ...(init?.headers as Record<string, string> ?? {}), ...await authHeaders() };
  const res = await fetch(url, { ...init, headers });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error(body.error || res.statusText);
  }
  return res;
}

// ── Products ──────────────────────────────────────────────────────

export interface Product {
  productId: string;
  productName: string;
  strength: string;
  dosageForm: string;
  cmoId: string;
  isActive: boolean;
  description?: string;
  createdAt: string;
  updatedAt: string;
  integrationPattern?: string;
  integrationConfig?: { hostname?: string; username?: string; password?: string };
}

export type CreateProductRequest = Omit<Product, 'productId' | 'createdAt' | 'updatedAt'>;

export async function listProducts(cmoId?: string): Promise<Product[]> {
  const url = cmoId
    ? `${CONTRACT_API}/api/product?cmoId=${encodeURIComponent(cmoId)}`
    : `${CONTRACT_API}/api/product`;
  const res = await apiFetch(url);
  const body = await res.json();
  return Array.isArray(body) ? body : body.products ?? [];
}

export async function createProduct(data: CreateProductRequest): Promise<Product> {
  const res = await apiFetch(`${CONTRACT_API}/api/product`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  return res.json();
}

export async function getProduct(productId: string): Promise<Product> {
  const res = await apiFetch(`${CONTRACT_API}/api/product/${encodeURIComponent(productId)}`);
  return res.json();
}

// ── Batches ───────────────────────────────────────────────────────

export interface DataElementStatus {
  elementType: string;
  received: boolean;
  receivedAt: string | null;
  s3Path: string | null;
  overdue: boolean;
}

export interface Batch {
  batchId: string;
  lotNumber: string;
  productId: string;
  cmoId: string;
  contractId: string;
  manufacturingDate: string;
  status: 'in_progress' | 'submitted' | 'complete';
  dataElements: DataElementStatus[];
  isComplete: boolean;
  missingElements: string[];
  submittedAt?: string;
  notes?: string;
  createdAt: string;
  updatedAt: string;
  integrationPattern?: string;
  integrationConfig?: { hostname?: string; username?: string; password?: string };
}

export type CreateBatchRequest = Pick<Batch, 'lotNumber' | 'productId' | 'manufacturingDate'> & { contractId?: string; notes?: string };

export async function listBatches(params?: { cmoId?: string; productId?: string }): Promise<Batch[]> {
  const qs = params?.cmoId ? `?cmoId=${encodeURIComponent(params.cmoId)}`
    : params?.productId ? `?productId=${encodeURIComponent(params.productId)}`
    : '';
  const res = await apiFetch(`${CONTRACT_API}/api/batch${qs}`);
  const body = await res.json();
  return Array.isArray(body) ? body : body.batches ?? [];
}

export async function createBatch(data: CreateBatchRequest): Promise<Batch> {
  const res = await apiFetch(`${CONTRACT_API}/api/batch`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  return res.json();
}

export async function getElementViewData(batchId: string, elementType: string): Promise<unknown> {
  const res = await apiFetch(`${CONTRACT_API}/api/batch/${encodeURIComponent(batchId)}/element/${encodeURIComponent(elementType)}/view`);
  return res.json();
}

export async function getBatchConnections(batchId: string): Promise<Connection[]> {
  const res = await apiFetch(`${CONTRACT_API}/api/batch/${encodeURIComponent(batchId)}/connections`);
  const body = await res.json();
  return body.connections ?? [];
}

export async function getBatch(batchId: string): Promise<Batch> {
  const res = await apiFetch(`${CONTRACT_API}/api/batch/${encodeURIComponent(batchId)}`);
  return res.json();
}

export async function markElementReceived(batchId: string, elementType: string, s3Path?: string): Promise<Batch> {
  const res = await apiFetch(`${CONTRACT_API}/api/batch/${encodeURIComponent(batchId)}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ elementType, s3Path }),
  });
  return res.json();
}

export async function submitBatch(batchId: string): Promise<Batch> {
  const res = await apiFetch(`${CONTRACT_API}/api/batch/${encodeURIComponent(batchId)}/submit`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
  });
  return res.json();
}

// ── Connections ───────────────────────────────────────────────────

export interface Connection {
  connectionId: string;
  cmoId: string;
  connectionType: string;
  name: string;
  status: 'pending' | 'pending_merck_review' | 'active' | 'inactive';
  config?: { hostname?: string; username?: string; password?: string; port?: number | string; supportedFormats?: string[]; glueConnectionName?: string; glueJobs?: Array<{jobName: string; triggerName: string; dataDomain: string; sourceTable: string}>; jdbcUrl?: string; dbType?: string; host?: string; database?: string; secretName?: string; connectionMethod?: string; privateLinkServiceName?: string; tableMappings?: Array<{sourceTable: string; dataDomain: string}>; bucket?: string; uploadPrefix?: string; confidenceThreshold?: number };
  createdAt: string;
  updatedAt: string;
  activatedBy?: string;
  activatedAt?: string;
}

export async function listConnections(cmoId?: string): Promise<Connection[]> {
  const qs = cmoId ? `?cmoId=${encodeURIComponent(cmoId)}` : '';
  const res = await apiFetch(`${CONTRACT_API}/api/connection${qs}`);
  const data = await res.json();
  return data.connections || [];
}

export async function getConnection(connectionId: string): Promise<Connection> {
  const res = await apiFetch(`${CONTRACT_API}/api/connection/${encodeURIComponent(connectionId)}`);
  return res.json();
}

export async function createConnection(data: { cmoId: string; connectionType: string; name: string; [key: string]: unknown }): Promise<Connection> {
  const res = await apiFetch(`${CONTRACT_API}/api/connection`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  return res.json();
}

export async function configureConnection(connectionId: string, jdbcConfig: Record<string, unknown>): Promise<Connection> {
  const res = await apiFetch(`${CONTRACT_API}/api/connection/${encodeURIComponent(connectionId)}/configure`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(jdbcConfig),
  });
  return res.json();
}

export async function activateConnection(connectionId: string): Promise<Connection> {
  const res = await apiFetch(`${CONTRACT_API}/api/connection/${encodeURIComponent(connectionId)}/activate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
  });
  return res.json();
}

export async function uploadFile(
  connectionId: string,
  file: File,
  batchId: string,
  lotNumber: string,
  elementType: string,
): Promise<{ bucket: string; key: string; filename: string; size: number }> {
  const form = new FormData();
  form.append('file', file, file.name);
  const qs = new URLSearchParams({ filename: file.name, batchId, lotNumber, elementType });
  const res = await apiFetch(`${CONTRACT_API}/api/connection/${encodeURIComponent(connectionId)}/upload?${qs}`, {
    method: 'POST',
    body: form,
    // No Content-Type header — browser sets multipart/form-data with boundary automatically
  });
  return res.json();
}

// ── Approval workflow ─────────────────────────────────────────────

export async function runSlaCheck(): Promise<{ checked: number; flagged: number }> {
  const res = await apiFetch(`${CONTRACT_API}/api/sla-check`, { method: 'POST', headers: { 'Content-Type': 'application/json' } });
  return res.json();
}

export async function submitContract(contractId: string): Promise<DataContract> {
  const res = await authFetch(`${CONTRACT_API}/api/contract/${encodeURIComponent(contractId)}/submit`, { method: 'POST', headers: { 'Content-Type': 'application/json' } });
  return res.json();
}

export async function acceptContract(contractId: string): Promise<DataContract> {
  const res = await authFetch(`${CONTRACT_API}/api/contract/${encodeURIComponent(contractId)}/accept`, { method: 'POST', headers: { 'Content-Type': 'application/json' } });
  return res.json();
}

export async function approveContract(contractId: string): Promise<DataContract> {
  const res = await authFetch(`${CONTRACT_API}/api/contract/${encodeURIComponent(contractId)}/approve`, { method: 'POST', headers: { 'Content-Type': 'application/json' } });
  return res.json();
}

export async function rejectContract(contractId: string, reason: string): Promise<DataContract> {
  const res = await authFetch(`${CONTRACT_API}/api/contract/${encodeURIComponent(contractId)}/reject`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ reason }) });
  return res.json();
}
