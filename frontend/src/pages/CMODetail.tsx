import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import Box from '@cloudscape-design/components/box';
import Button from '@cloudscape-design/components/button';
import ColumnLayout from '@cloudscape-design/components/column-layout';
import Container from '@cloudscape-design/components/container';
import Header from '@cloudscape-design/components/header';
import SpaceBetween from '@cloudscape-design/components/space-between';
import StatusIndicator from '@cloudscape-design/components/status-indicator';
import Tabs from '@cloudscape-design/components/tabs';
import Spinner from '@cloudscape-design/components/spinner';
import { listCMOs, type CMOProfile } from '../services/api';
import Connections from './Connections';
import SchemaManagement from './SchemaManagement';
import DataContracts from './DataContracts';
import Batches from './Batches';

export default function CMODetail() {
  const { cmoId } = useParams<{ cmoId: string }>();
  const navigate = useNavigate();
  const [cmo, setCmo] = useState<CMOProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('connections');

  useEffect(() => {
    if (!cmoId) return;
    listCMOs()
      .then(list => setCmo(list.find(c => c.cmoId === cmoId) ?? null))
      .finally(() => setLoading(false));
  }, [cmoId]);

  if (loading) return <Box textAlign="center" padding="xl"><Spinner size="large" /></Box>;
  if (!cmo) return <Box>CMO not found.</Box>;

  return (
    <SpaceBetween size="l">
      <Header
        variant="h1"
        actions={<Button onClick={() => navigate('/cmos')}>← Back to CMO Partners</Button>}
      >
        {cmo.organizationName}
      </Header>

      <Container>
        <ColumnLayout columns={4} variant="text-grid">
          <div><Box variant="awsui-key-label">CMO ID</Box><div>{cmo.cmoId}</div></div>
          <div><Box variant="awsui-key-label">Contact Email</Box><div>{cmo.contactEmail ?? '—'}</div></div>
          <div><Box variant="awsui-key-label">Phone</Box><div>{cmo.contactPhone ?? '—'}</div></div>
          <div><Box variant="awsui-key-label">Status</Box>
            <StatusIndicator type={cmo.status === 'active' ? 'success' : 'stopped'}>
              {cmo.status ?? 'unknown'}
            </StatusIndicator>
          </div>
          {cmo.address && (
            <div style={{ gridColumn: 'span 4' }}>
              <Box variant="awsui-key-label">Address</Box><div>{cmo.address}</div>
            </div>
          )}
        </ColumnLayout>
      </Container>

      <Tabs
        activeTabId={activeTab}
        onChange={({ detail }) => setActiveTab(detail.activeTabId)}
        tabs={[
          {
            id: 'connections',
            label: 'Connections',
            content: <Connections cmoId={cmoId} />,
          },
          {
            id: 'schemas',
            label: 'Schemas',
            content: <SchemaManagement cmoId={cmoId} />,
          },
          {
            id: 'contracts',
            label: 'Data Contracts',
            content: <DataContracts cmoId={cmoId} />,
          },
          {
            id: 'batches',
            label: 'Batches',
            content: <Batches cmoId={cmoId} />,
          },
        ]}
      />
    </SpaceBetween>
  );
}
