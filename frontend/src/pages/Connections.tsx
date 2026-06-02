import { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import Table from '@cloudscape-design/components/table';
import Header from '@cloudscape-design/components/header';
import Button from '@cloudscape-design/components/button';
import SpaceBetween from '@cloudscape-design/components/space-between';
import Box from '@cloudscape-design/components/box';
import Modal from '@cloudscape-design/components/modal';
import FormField from '@cloudscape-design/components/form-field';
import Input from '@cloudscape-design/components/input';
import Select from '@cloudscape-design/components/select';
import StatusIndicator from '@cloudscape-design/components/status-indicator';
import Container from '@cloudscape-design/components/container';
import ColumnLayout from '@cloudscape-design/components/column-layout';
import Alert from '@cloudscape-design/components/alert';
import CopyToClipboard from '@cloudscape-design/components/copy-to-clipboard';
import { useAuth } from '../context/AuthContext';
import { listConnections, createConnection, activateConnection, configureConnection, listCMOs, type Connection, type CMOProfile } from '../services/api';

const TYPE_OPTIONS = [
  { label: 'Secure File Transfer (SFTP)', value: 'secure-transfer' },
  { label: 'Native Database Connector', value: 'native-connector' },
  { label: 'AI-Powered Unstructured Data', value: 'ai-unstructured' },
];

const TYPE_LABELS: Record<string, string> = {
  'secure-transfer': 'SFTP',
  'native-connector': 'Native Connector',
  'ai-unstructured': 'AI Unstructured',
};

const DB_TYPE_OPTIONS = [
  { label: 'SQL Server', value: 'sqlserver' },
  { label: 'Oracle', value: 'oracle' },
  { label: 'PostgreSQL', value: 'postgresql' },
  { label: 'MySQL', value: 'mysql' },
  { label: 'Snowflake', value: 'snowflake' },
  { label: 'SAP HANA', value: 'sap' },
];

const DEFAULT_PORTS: Record<string, string> = {
  sqlserver: '1433', oracle: '1521', postgresql: '5432',
  mysql: '3306', snowflake: '443', sap: '30015',
};

const CONNECTION_METHOD_OPTIONS = [
  { label: 'Direct (public endpoint or VPN)', value: 'direct' },
  { label: 'Network Load Balancer (NLB)', value: 'nlb' },
  { label: 'AWS PrivateLink', value: 'privatelink' },
];

export default function Connections({ cmoId: propCmoId }: { cmoId?: string } = {}) {
  const { user } = useAuth();
  const [searchParams] = useSearchParams();
  const preselectedCmoId = propCmoId || searchParams.get('cmoId') || '';

  const [connections, setConnections] = useState<Connection[]>([]);
  const [cmos, setCmos] = useState<CMOProfile[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [showDetail, setShowDetail] = useState<Connection | null>(null);
  const [activating, setActivating] = useState<string | null>(null);
  const [configuring, setConfiguring] = useState(false);

  // Create form state
  const [newName, setNewName] = useState('');
  const [newType, setNewType] = useState<string>('secure-transfer');
  const [newCmoId, setNewCmoId] = useState(preselectedCmoId);
  const [creating, setCreating] = useState(false);

  const [showCmoCreate, setShowCmoCreate] = useState(false);

  // JDBC config state (for native-connector configure/create)
  const [jdbcConfig, setJdbcConfig] = useState({ dbType: 'sqlserver', host: '', port: '1433', database: '', username: '', password: '', connectionMethod: 'direct', privateLinkServiceName: '' });
  const [tableMappings, setTableMappings] = useState<Array<{sourceTable: string; dataDomain: string}>>([{ sourceTable: '', dataDomain: '' }]);

  useEffect(() => {
    load();
  }, []);

  async function load() {
    setLoading(true);
    try {
      const [conns, cmoList] = await Promise.all([
        listConnections(preselectedCmoId || undefined),
        user?.isMerckAdmin ? listCMOs() : Promise.resolve([]),
      ]);
      setConnections(conns);
      setCmos(cmoList);
    } catch (e) { console.error(e); }
    setLoading(false);
  }

  async function handleCreate() {
    if (!newName || !newCmoId) return;
    setCreating(true);
    try {
      const conn = await createConnection({ cmoId: newCmoId, connectionType: newType, name: newName });
      setConnections(prev => [conn, ...prev]);
      setShowCreate(false);
      setNewName('');
    } catch (e) { console.error(e); }
    setCreating(false);
  }

  async function handleActivate(conn: Connection) {
    setActivating(conn.connectionId);
    try {
      const updated = await activateConnection(conn.connectionId);
      setConnections(prev => prev.map(c => c.connectionId === updated.connectionId ? updated : c));
      setShowDetail(updated);
    } catch (e) { console.error(e); }
    setActivating(null);
  }

  async function handleConfigure(conn: Connection) {
    setConfiguring(true);
    try {
      const updated = await configureConnection(conn.connectionId, { ...jdbcConfig, tableMappings });
      setConnections(prev => prev.map(c => c.connectionId === updated.connectionId ? updated : c));
      setShowDetail(updated);
    } catch (e) { console.error(e); }
    setConfiguring(false);
  }

  async function handleCmoCreate() {
    if (!jdbcConfig.host || !jdbcConfig.database || !jdbcConfig.username || !jdbcConfig.password) return;
    setCreating(true);
    try {
      const conn = await createConnection({
        cmoId: '',  // backend uses JWT claim
        connectionType: 'native-connector',
        name: newName || `${jdbcConfig.dbType}-connector`,
        ...jdbcConfig,
        tableMappings,
      });
      setConnections(prev => [conn, ...prev]);
      setShowCmoCreate(false);
      setNewName('');
      setJdbcConfig({ dbType: 'sqlserver', host: '', port: '1433', database: '', username: '', password: '', connectionMethod: 'direct', privateLinkServiceName: '' });
      setTableMappings([{ sourceTable: '', dataDomain: '' }]);
    } catch (e) { console.error(e); }
    setCreating(false);
  }



  const cmoMap = Object.fromEntries(cmos.map(c => [c.cmoId, c.organizationName]));

  return (
    <SpaceBetween size="l">
      <Table
        header={
          <Header
            variant="h1"
            actions={
              user?.isMerckAdmin
                ? <Button variant="primary" onClick={() => setShowCreate(true)}>Create Connection</Button>
                : <Button variant="primary" onClick={() => setShowCmoCreate(true)}>Add Database Connection</Button>
            }
            counter={`(${connections.length})`}
          >
            {user?.isMerckAdmin ? 'Connections' : 'My Connections'}
          </Header>
        }
        items={connections}
        loading={loading}
        loadingText="Loading connections..."
        empty={<Box textAlign="center" color="inherit"><b>No connections</b><Box padding={{ bottom: 's' }} variant="p" color="inherit">No connections have been created yet.</Box></Box>}
        columnDefinitions={[
          { id: 'name', header: 'Name', cell: item => <Button variant="link" onClick={() => setShowDetail(item)}>{item.name}</Button> },
          { id: 'type', header: 'Type', cell: item => TYPE_LABELS[item.connectionType] || item.connectionType },
          ...(user?.isMerckAdmin ? [{ id: 'cmo', header: 'CMO', cell: (item: Connection) => cmoMap[item.cmoId] || item.cmoId }] : []),
          { id: 'status', header: 'Status', cell: item => (
            <StatusIndicator type={item.status === 'active' ? 'success' : item.status === 'inactive' ? 'stopped' : item.status === 'pending_merck_review' ? 'in-progress' : 'pending'}>
              {item.status}
            </StatusIndicator>
          )},
          { id: 'actions', header: 'Actions', cell: item => (
            item.status === 'pending_merck_review' && user?.isMerckAdmin ? (
              <Button variant="primary" loading={activating === item.connectionId} onClick={() => { setShowDetail(item); }}>Review & Activate</Button>
            ) : item.status === 'pending' && !user?.isMerckAdmin ? (
              <Button onClick={() => setShowDetail(item)}>Configure</Button>
            ) : item.status === 'active' ? (
              <Button variant="link" onClick={() => setShowDetail(item)}>View Details</Button>
            ) : null
          )},
        ]}
      />

      {/* Create Connection Modal */}
      <Modal
        visible={showCreate}
        onDismiss={() => setShowCreate(false)}
        header="Create Connection"
        footer={
          <Box float="right"><SpaceBetween direction="horizontal" size="xs">
            <Button variant="link" onClick={() => setShowCreate(false)}>Cancel</Button>
            <Button variant="primary" loading={creating} onClick={handleCreate}>Create</Button>
          </SpaceBetween></Box>
        }
      >
        <SpaceBetween size="m">
          {user?.isMerckAdmin && (
            <FormField label="CMO">
              <Select
                selectedOption={newCmoId ? { value: newCmoId, label: cmoMap[newCmoId] || newCmoId } : null}
                onChange={({ detail }) => setNewCmoId(detail.selectedOption.value || '')}
                options={cmos.map(c => ({ value: c.cmoId, label: c.organizationName }))}
                placeholder="Select CMO"
              />
            </FormField>
          )}
          <FormField label="Connection Name">
            <Input value={newName} onChange={({ detail }) => setNewName(detail.value)} placeholder="e.g. batch-records-sftp" />
          </FormField>
          <FormField label="Connection Type">
            <Select
              selectedOption={TYPE_OPTIONS.find(o => o.value === newType) || null}
              onChange={({ detail }) => setNewType(detail.selectedOption.value || 'secure-transfer')}
              options={TYPE_OPTIONS}
            />
          </FormField>
        </SpaceBetween>
      </Modal>

      {/* CMO: Create + Configure Native Connector Modal */}
      <Modal
        visible={showCmoCreate}
        onDismiss={() => setShowCmoCreate(false)}
        header="Add Database Connection"
        size="large"
        footer={
          <Box float="right"><SpaceBetween direction="horizontal" size="xs">
            <Button variant="link" onClick={() => setShowCmoCreate(false)}>Cancel</Button>
            <Button variant="primary" loading={creating} onClick={handleCmoCreate}>Submit to Merck</Button>
          </SpaceBetween></Box>
        }
      >
        <SpaceBetween size="m">
          <Alert type="info">
            Enter your database connection details. Your credentials will be stored securely in AWS Secrets Manager.
            Merck will review and activate the connection — they will not see your password.
          </Alert>
          <FormField label="Connection Name">
            <Input value={newName} onChange={({ detail }) => setNewName(detail.value)} placeholder="e.g. batch-records-sqlserver" />
          </FormField>
          <ColumnLayout columns={2}>
            <FormField label="Database Type">
              <Select
                selectedOption={DB_TYPE_OPTIONS.find(o => o.value === jdbcConfig.dbType) || null}
                onChange={({ detail }) => {
                  const t = detail.selectedOption.value || 'sqlserver';
                  setJdbcConfig(prev => ({ ...prev, dbType: t, port: DEFAULT_PORTS[t] || prev.port }));
                }}
                options={DB_TYPE_OPTIONS}
              />
            </FormField>
            <FormField label="Connection Method">
              <Select
                selectedOption={CONNECTION_METHOD_OPTIONS.find(o => o.value === jdbcConfig.connectionMethod) || null}
                onChange={({ detail }) => setJdbcConfig(p => ({ ...p, connectionMethod: detail.selectedOption.value || 'direct' }))}
                options={CONNECTION_METHOD_OPTIONS}
              />
            </FormField>
            <FormField label="Host / Endpoint" description={jdbcConfig.connectionMethod === 'nlb' ? 'NLB DNS name' : jdbcConfig.connectionMethod === 'privatelink' ? 'VPC Endpoint DNS name' : 'Database hostname or IP'}>
              <Input value={jdbcConfig.host} onChange={({ detail }) => setJdbcConfig(p => ({ ...p, host: detail.value }))} placeholder="db.example.com" />
            </FormField>
            <FormField label="Port">
              <Input value={jdbcConfig.port} onChange={({ detail }) => setJdbcConfig(p => ({ ...p, port: detail.value }))} />
            </FormField>
            <FormField label="Database Name">
              <Input value={jdbcConfig.database} onChange={({ detail }) => setJdbcConfig(p => ({ ...p, database: detail.value }))} placeholder="BatchRecordsDB" />
            </FormField>
            <FormField label="Username">
              <Input value={jdbcConfig.username} onChange={({ detail }) => setJdbcConfig(p => ({ ...p, username: detail.value }))} />
            </FormField>
            <FormField label="Password">
              <Input type="password" value={jdbcConfig.password} onChange={({ detail }) => setJdbcConfig(p => ({ ...p, password: detail.value }))} />
            </FormField>
            {jdbcConfig.connectionMethod === 'privatelink' && (
              <FormField label="PrivateLink Service Name" description="Share this with Merck so they can create the VPC Endpoint on their side">
                <Input value={jdbcConfig.privateLinkServiceName} onChange={({ detail }) => setJdbcConfig(p => ({ ...p, privateLinkServiceName: detail.value }))} placeholder="com.amazonaws.vpce.us-east-1.vpce-svc-xxx" />
              </FormField>
            )}
          </ColumnLayout>
          <FormField label="Table Mappings" description="Map each source table to a data domain in the Bronze layer">
            <SpaceBetween size="xs">
              {tableMappings.map((m, i) => (
                <ColumnLayout key={i} columns={3}>
                  <Input placeholder="Source table (e.g. BATCH_RECORDS)" value={m.sourceTable} onChange={({ detail }) => setTableMappings(prev => prev.map((r, j) => j === i ? { ...r, sourceTable: detail.value } : r))} />
                  <Input placeholder="Data domain (e.g. batch-records)" value={m.dataDomain} onChange={({ detail }) => setTableMappings(prev => prev.map((r, j) => j === i ? { ...r, dataDomain: detail.value } : r))} />
                  <Button iconName="remove" variant="icon" onClick={() => setTableMappings(prev => prev.filter((_, j) => j !== i))} disabled={tableMappings.length === 1} />
                </ColumnLayout>
              ))}
              <Button iconName="add-plus" onClick={() => setTableMappings(prev => [...prev, { sourceTable: '', dataDomain: '' }])}>Add Table</Button>
            </SpaceBetween>
          </FormField>
        </SpaceBetween>
      </Modal>

      {/* Connection Detail Modal */}
      <Modal
        visible={!!showDetail}
        onDismiss={() => setShowDetail(null)}
        header={showDetail?.name || 'Connection Details'}
        size="large"
      >
        {showDetail && (
          <SpaceBetween size="m">
            <Container header={<Header variant="h3">Connection Info</Header>}>
              <ColumnLayout columns={2} variant="text-grid">
                <div><Box variant="awsui-key-label">Connection ID</Box><div>{showDetail.connectionId}</div></div>
                <div><Box variant="awsui-key-label">Type</Box><div>{TYPE_LABELS[showDetail.connectionType] || showDetail.connectionType}</div></div>
                <div><Box variant="awsui-key-label">Status</Box><div>
                  <StatusIndicator type={showDetail.status === 'active' ? 'success' : showDetail.status === 'pending_merck_review' ? 'in-progress' : 'pending'}>{showDetail.status}</StatusIndicator>
                </div></div>
                <div><Box variant="awsui-key-label">Created</Box><div>{new Date(showDetail.createdAt).toLocaleString()}</div></div>
              </ColumnLayout>
            </Container>

            {showDetail.status === 'active' && showDetail.connectionType === 'secure-transfer' && showDetail.config?.hostname && (
              <Container header={<Header variant="h3">SFTP Connection Details</Header>}>
                <Alert type="info">Share these credentials with the CMO. They only need a standard SFTP client — no AWS account required.</Alert>
                <ColumnLayout columns={1} variant="text-grid">
                  <div><Box variant="awsui-key-label">Hostname</Box>
                    <CopyToClipboard copyButtonAriaLabel="Copy" copySuccessText="Copied" copyErrorText="Failed" textToCopy={showDetail.config.hostname} variant="inline" />
                  </div>
                  <div><Box variant="awsui-key-label">Port</Box><div>22</div></div>
                  <div><Box variant="awsui-key-label">Username</Box>
                    <CopyToClipboard copyButtonAriaLabel="Copy" copySuccessText="Copied" copyErrorText="Failed" textToCopy={showDetail.config.username || ''} variant="inline" />
                  </div>
                  <div><Box variant="awsui-key-label">Password</Box>
                    <CopyToClipboard copyButtonAriaLabel="Copy" copySuccessText="Copied" copyErrorText="Failed" textToCopy={showDetail.config.password || ''} variant="inline" />
                  </div>
                </ColumnLayout>
                <Box margin={{ top: 's' }} color="text-body-secondary">Supported formats: CSV, JSON, Parquet</Box>
              </Container>
            )}

            {showDetail.status === 'active' && showDetail.connectionType === 'native-connector' && showDetail.config?.glueConnectionName && (
              <Container header={<Header variant="h3">JDBC Connection Details</Header>}>
                <Alert type="info">AWS Glue connection created. Use the Glue connection name when configuring ETL jobs.</Alert>
                <ColumnLayout columns={2} variant="text-grid">
                  <div><Box variant="awsui-key-label">Glue Connection Name</Box>
                    <CopyToClipboard copyButtonAriaLabel="Copy" copySuccessText="Copied" copyErrorText="Failed" textToCopy={showDetail.config.glueConnectionName} variant="inline" />
                  </div>
                  <div><Box variant="awsui-key-label">Database Type</Box><div>{showDetail.config?.dbType?.toUpperCase()}</div></div>
                  <div><Box variant="awsui-key-label">Connection Method</Box><div>{CONNECTION_METHOD_OPTIONS.find(o => o.value === showDetail.config?.connectionMethod)?.label || 'Direct'}</div></div>
                  <div><Box variant="awsui-key-label">Host</Box><div>{showDetail.config.host}</div></div>
                  <div><Box variant="awsui-key-label">Port</Box><div>{showDetail.config.port}</div></div>
                  <div><Box variant="awsui-key-label">Database</Box><div>{showDetail.config.database}</div></div>
                  <div><Box variant="awsui-key-label">Username</Box><div>{showDetail.config.username}</div></div>
                  <div><Box variant="awsui-key-label">JDBC URL</Box>
                    <CopyToClipboard copyButtonAriaLabel="Copy" copySuccessText="Copied" copyErrorText="Failed" textToCopy={showDetail.config.jdbcUrl || ''} variant="inline" />
                  </div>
                  <div><Box variant="awsui-key-label">Credentials Secret</Box><div>{showDetail.config.secretName}</div></div>
                </ColumnLayout>
                {(showDetail.config?.glueJobs?.length ?? 0) > 0 && (
                  <div>
                    <Box variant="awsui-key-label">ETL Jobs (daily at 02:00 UTC)</Box>
                    <Table
                      columnDefinitions={[
                        { id: 'job', header: 'Glue Job', cell: (j: any) => j.jobName },
                        { id: 'table', header: 'Source Table', cell: (j: any) => j.sourceTable },
                        { id: 'domain', header: 'Data Domain', cell: (j: any) => j.dataDomain },
                      ]}
                      items={showDetail.config?.glueJobs ?? []}
                      variant="embedded"
                    />
                  </div>
                )}
              </Container>
            )}

            {/* CMO: enter their own DB credentials */}
            {showDetail.connectionType === 'native-connector' && showDetail.status === 'pending' && !user?.isMerckAdmin && (
              <Container header={<Header variant="h3">Configure Your Database Connection</Header>}>
                <SpaceBetween size="m">
                  <Alert type="info">Enter your database connection details. Your credentials will be stored securely in AWS Secrets Manager. Merck will then create the integration — they will not see your password.</Alert>
                  <ColumnLayout columns={2}>
                    <FormField label="Database Type">
                      <Select
                        selectedOption={DB_TYPE_OPTIONS.find(o => o.value === jdbcConfig.dbType) || null}
                        onChange={({ detail }) => {
                          const t = detail.selectedOption.value || 'sqlserver';
                          setJdbcConfig(prev => ({ ...prev, dbType: t, port: DEFAULT_PORTS[t] || prev.port }));
                        }}
                        options={DB_TYPE_OPTIONS}
                      />
                    </FormField>
                    <FormField label="Host / Endpoint">
                      <Input value={jdbcConfig.host} onChange={({ detail }) => setJdbcConfig(p => ({ ...p, host: detail.value }))} placeholder="db.example.com" />
                    </FormField>
                    <FormField label="Port">
                      <Input value={jdbcConfig.port} onChange={({ detail }) => setJdbcConfig(p => ({ ...p, port: detail.value }))} />
                    </FormField>
                    <FormField label="Database Name">
                      <Input value={jdbcConfig.database} onChange={({ detail }) => setJdbcConfig(p => ({ ...p, database: detail.value }))} placeholder="BatchRecordsDB" />
                    </FormField>
                    <FormField label="Username">
                      <Input value={jdbcConfig.username} onChange={({ detail }) => setJdbcConfig(p => ({ ...p, username: detail.value }))} />
                    </FormField>
                    <FormField label="Password">
                      <Input type="password" value={jdbcConfig.password} onChange={({ detail }) => setJdbcConfig(p => ({ ...p, password: detail.value }))} />
                    </FormField>
                  </ColumnLayout>
                  <FormField label="Table Mappings" description="Map each source table to a data domain in the Bronze layer">
                    <SpaceBetween size="xs">
                      {tableMappings.map((m, i) => (
                        <ColumnLayout key={i} columns={3}>
                          <Input placeholder="Source table (e.g. BATCH_RECORDS)" value={m.sourceTable} onChange={({ detail }) => setTableMappings(prev => prev.map((r, j) => j === i ? { ...r, sourceTable: detail.value } : r))} />
                          <Input placeholder="Data domain (e.g. batch-records)" value={m.dataDomain} onChange={({ detail }) => setTableMappings(prev => prev.map((r, j) => j === i ? { ...r, dataDomain: detail.value } : r))} />
                          <Button iconName="remove" variant="icon" onClick={() => setTableMappings(prev => prev.filter((_, j) => j !== i))} disabled={tableMappings.length === 1} />
                        </ColumnLayout>
                      ))}
                      <Button iconName="add-plus" onClick={() => setTableMappings(prev => [...prev, { sourceTable: '', dataDomain: '' }])}>Add Table</Button>
                    </SpaceBetween>
                  </FormField>
                  <Button variant="primary" loading={configuring} onClick={() => handleConfigure(showDetail)}>
                    Submit Configuration
                  </Button>
                </SpaceBetween>
              </Container>
            )}

            {/* Merck: see CMO-submitted details (no password) and one-click activate */}
            {showDetail.connectionType === 'native-connector' && showDetail.status === 'pending_merck_review' && user?.isMerckAdmin && (
              <Container header={<Header variant="h3">CMO Database Configuration</Header>}>
                <SpaceBetween size="m">
                  <Alert type="success">The CMO has submitted their database credentials. Review the details below and click Activate to create the AWS Glue connection.</Alert>
                  <ColumnLayout columns={2} variant="text-grid">
                    <div><Box variant="awsui-key-label">Database Type</Box><div>{showDetail.config?.dbType?.toUpperCase()}</div></div>
                    <div><Box variant="awsui-key-label">Connection Method</Box><div>{CONNECTION_METHOD_OPTIONS.find(o => o.value === showDetail.config?.connectionMethod)?.label || showDetail.config?.connectionMethod || 'Direct'}</div></div>
                    <div><Box variant="awsui-key-label">Host</Box><div>{showDetail.config?.host}</div></div>
                    <div><Box variant="awsui-key-label">Port</Box><div>{showDetail.config?.port}</div></div>
                    <div><Box variant="awsui-key-label">Database</Box><div>{showDetail.config?.database}</div></div>
                    <div><Box variant="awsui-key-label">Username</Box><div>{showDetail.config?.username}</div></div>
                    <div><Box variant="awsui-key-label">Password</Box><div>••••••••  <i>(stored in Secrets Manager)</i></div></div>
                    <div><Box variant="awsui-key-label">JDBC URL</Box><div style={{wordBreak:'break-all'}}>{showDetail.config?.jdbcUrl}</div></div>
                    {showDetail.config?.privateLinkServiceName && (
                      <div style={{gridColumn:'span 2'}}><Box variant="awsui-key-label">PrivateLink Service Name</Box>
                        <CopyToClipboard copyButtonAriaLabel="Copy" copySuccessText="Copied" copyErrorText="Failed" textToCopy={showDetail.config.privateLinkServiceName} variant="inline" />
                      </div>
                    )}
                  </ColumnLayout>
                  {(showDetail.config?.tableMappings?.length ?? 0) > 0 && (
                    <div>
                      <Box variant="awsui-key-label">Table Mappings</Box>
                      <Table
                        columnDefinitions={[
                          { id: 'src', header: 'Source Table', cell: (m: any) => m.sourceTable },
                          { id: 'domain', header: 'Data Domain (Bronze)', cell: (m: any) => m.dataDomain },
                        ]}
                        items={showDetail.config?.tableMappings ?? []}
                        variant="embedded"
                      />
                    </div>
                  )}
                  <Button variant="primary" loading={activating === showDetail.connectionId} onClick={() => handleActivate(showDetail)}>
                    Activate — Create Glue Connection + ETL Jobs
                  </Button>
                </SpaceBetween>
              </Container>
            )}

            {showDetail.status === 'active' && showDetail.connectionType === 'ai-unstructured' && (
              <Alert type="info">
                To upload documents for AI processing, go to the <strong>Batch Detail</strong> page and use the Upload button on the relevant data element. Files are automatically tagged with the batch ID for full traceability.
              </Alert>
            )}

            {showDetail.status === 'pending' && showDetail.connectionType === 'secure-transfer' && user?.isMerckAdmin && (
              <Box>
                <Button variant="primary" loading={activating === showDetail.connectionId} onClick={() => handleActivate(showDetail)}>
                  Activate Connection
                </Button>
              </Box>
            )}
          </SpaceBetween>
        )}
      </Modal>
    </SpaceBetween>
  );
}
