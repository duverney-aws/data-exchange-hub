import { Routes, Route, Navigate } from 'react-router-dom';
import { useAuth } from './context/AuthContext';
import Layout from './components/Layout';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import CMORegistration from './pages/CMORegistration';
import CMOList from './pages/CMOList';
import CMODetail from './pages/CMODetail';
import DataContracts from './pages/DataContracts';
import ContractCreate from './pages/ContractCreate';
import ContractDetail from './pages/ContractDetail';
import IntegrationPatternSelection from './pages/IntegrationPatternSelection';
import SchemaManagement from './pages/SchemaManagement';
import Pipelines from './pages/Pipelines';
import NLQuery from './pages/NLQuery';
import Products from './pages/Products';
import Connections from './pages/Connections';
import Batches from './pages/Batches';
import BatchDetail from './pages/BatchDetail';
import Spinner from '@cloudscape-design/components/spinner';
import Box from '@cloudscape-design/components/box';

function LoadingScreen() {
  return (
    <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '100vh' }}>
      <Box><Spinner size="large" /> Loading…</Box>
    </div>
  );
}

export default function App() {
  const { user, loading } = useAuth();

  if (loading) return <LoadingScreen />;
  if (!user) return <Login />;

  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Navigate to="/dashboard" replace />} />
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/data-contracts" element={<DataContracts />} />
        <Route path="/data-contracts/create" element={<ContractCreate />} />
        <Route path="/data-contracts/:contractId" element={<ContractDetail />} />
        <Route path="/integration-patterns" element={<IntegrationPatternSelection />} />
        <Route path="/schema-management" element={<SchemaManagement />} />
        <Route path="/pipelines" element={<Pipelines />} />
        <Route path="/nl-query" element={<NLQuery />} />
        <Route path="/products" element={<Products />} />
        <Route path="/connections" element={<Connections />} />
        <Route path="/batches" element={<Batches />} />
        <Route path="/batches/:batchId" element={<BatchDetail />} />
        {/* Merck admin only */}
        {user.isMerckAdmin && (
          <>
            <Route path="/cmos" element={<CMOList />} />
            <Route path="/cmos/:cmoId" element={<CMODetail />} />
            <Route path="/cmo-registration" element={<CMORegistration />} />
          </>
        )}
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Route>
    </Routes>
  );
}
