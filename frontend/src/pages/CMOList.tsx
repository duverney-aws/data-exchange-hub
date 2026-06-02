import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Box from '@cloudscape-design/components/box';
import Button from '@cloudscape-design/components/button';
import Flashbar, { FlashbarProps } from '@cloudscape-design/components/flashbar';
import FormField from '@cloudscape-design/components/form-field';
import Header from '@cloudscape-design/components/header';
import Input from '@cloudscape-design/components/input';
import Modal from '@cloudscape-design/components/modal';
import SpaceBetween from '@cloudscape-design/components/space-between';
import StatusIndicator from '@cloudscape-design/components/status-indicator';
import Table from '@cloudscape-design/components/table';
import TextFilter from '@cloudscape-design/components/text-filter';
import { listCMOs, inviteCMOUser, updateCMO, deactivateCMO, CMOProfile } from '../services/api';

export default function CMOList() {
  const navigate = useNavigate();
  const [cmos, setCmos] = useState<CMOProfile[]>([]);
  const [loading, setLoading] = useState(true);
  const [filterText, setFilterText] = useState('');
  const [flash, setFlash] = useState<FlashbarProps.MessageDefinition[]>([]);

  // Invite modal state
  const [inviteModalOpen, setInviteModalOpen] = useState(false);
  const [inviteCmo, setInviteCmo] = useState<CMOProfile | null>(null);
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteFirst, setInviteFirst] = useState('');
  const [inviteLast, setInviteLast] = useState('');
  const [inviteLoading, setInviteLoading] = useState(false);

  // Edit modal state
  const [editModalOpen, setEditModalOpen] = useState(false);
  const [editCmo, setEditCmo] = useState<CMOProfile | null>(null);
  const [editForm, setEditForm] = useState({ organizationName: '', contactEmail: '', contactPhone: '', address: '' });
  const [editLoading, setEditLoading] = useState(false);

  useEffect(() => {
    listCMOs()
      .then(setCmos)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const filtered = cmos.filter(c =>
    !filterText ||
    c.organizationName?.toLowerCase().includes(filterText.toLowerCase()) ||
    c.cmoId?.toLowerCase().includes(filterText.toLowerCase()) ||
    c.contactEmail?.toLowerCase().includes(filterText.toLowerCase())
  );

  function openInvite(cmo: CMOProfile) {
    setInviteCmo(cmo);
    setInviteEmail(cmo.contactEmail ?? '');
    setInviteFirst('');
    setInviteLast('');
    setInviteModalOpen(true);
  }

  function openEdit(cmo: CMOProfile) {
    setEditCmo(cmo);
    setEditForm({
      organizationName: cmo.organizationName ?? '',
      contactEmail: cmo.contactEmail ?? '',
      contactPhone: cmo.contactPhone ?? '',
      address: cmo.address ?? '',
    });
    setEditModalOpen(true);
  }

  async function handleEdit() {
    if (!editCmo) return;
    setEditLoading(true);
    try {
      await updateCMO(editCmo.cmoId, editForm);
      setEditModalOpen(false);
      setCmos(prev => prev.map(c => c.cmoId === editCmo.cmoId ? { ...c, ...editForm } : c));
      setFlash([{ type: 'success', dismissible: true, onDismiss: () => setFlash([]), content: 'CMO updated successfully.' }]);
    } catch (err: unknown) {
      setFlash([{ type: 'error', dismissible: true, onDismiss: () => setFlash([]), content: err instanceof Error ? err.message : 'Update failed' }]);
    } finally {
      setEditLoading(false);
    }
  }

  async function handleDeactivate(cmo: CMOProfile) {
    if (!confirm(`Deactivate ${cmo.organizationName}? They will no longer appear as active.`)) return;
    try {
      await deactivateCMO(cmo.cmoId);
      setCmos(prev => prev.map(c => c.cmoId === cmo.cmoId ? { ...c, status: 'inactive' } : c));
      setFlash([{ type: 'success', dismissible: true, onDismiss: () => setFlash([]), content: `${cmo.organizationName} deactivated.` }]);
    } catch (err: unknown) {
      setFlash([{ type: 'error', dismissible: true, onDismiss: () => setFlash([]), content: err instanceof Error ? err.message : 'Deactivate failed' }]);
    }
  }

  async function handleInvite() {
    if (!inviteCmo || !inviteEmail.trim()) return;
    setInviteLoading(true);
    try {
      await inviteCMOUser(inviteCmo.cmoId, inviteEmail.trim(), inviteFirst.trim() || 'CMO', inviteLast.trim() || 'User');
      setInviteModalOpen(false);
      setFlash([{
        type: 'success',
        dismissible: true,
        onDismiss: () => setFlash([]),
        content: `Invitation sent to ${inviteEmail}. They will receive an email with login credentials.`,
      }]);
    } catch (err: unknown) {
      setFlash([{
        type: 'error',
        dismissible: true,
        onDismiss: () => setFlash([]),
        content: err instanceof Error ? err.message : 'Invite failed',
      }]);
    } finally {
      setInviteLoading(false);
    }
  }

  return (
    <SpaceBetween size="l">
      <Header
        variant="h1"
        description="Contract Manufacturing Organizations registered on the platform"
        actions={
          <Button variant="primary" onClick={() => navigate('/cmo-registration')}>
            Register New CMO
          </Button>
        }
      >
        CMO Partners
      </Header>

      <Flashbar items={flash} />

      <Table
        loading={loading}
        loadingText="Loading CMOs…"
        items={filtered}
        empty={
          <Box textAlign="center" color="inherit">
            <b>No CMOs registered</b>
            <Box variant="p" color="inherit">Register your first CMO to get started.</Box>
            <Button onClick={() => navigate('/cmo-registration')}>Register CMO</Button>
          </Box>
        }
        filter={
          <TextFilter
            filteringText={filterText}
            filteringPlaceholder="Search CMOs…"
            onChange={({ detail }) => setFilterText(detail.filteringText)}
          />
        }
        columnDefinitions={[
          {
            id: 'org',
            header: 'Organization',
            cell: c => <Button variant="link" onClick={() => navigate(`/cmos/${c.cmoId}`)}>{c.organizationName}</Button>,
            sortingField: 'organizationName',
          },
          {
            id: 'cmoId',
            header: 'CMO ID',
            cell: c => c.cmoId,
          },
          {
            id: 'email',
            header: 'Contact Email',
            cell: c => c.contactEmail,
          },
          {
            id: 'status',
            header: 'Status',
            cell: c => (
              <StatusIndicator type={c.status === 'active' ? 'success' : 'info'}>
                {c.status ?? 'invited'}
              </StatusIndicator>
            ),
          },
          {
            id: 'actions',
            header: 'Actions',
            cell: c => (
              <SpaceBetween direction="horizontal" size="xs">
                <Button variant="inline-link" onClick={() => openInvite(c)}>
                  Invite User
                </Button>
                <Button variant="inline-link" onClick={() => navigate(`/data-contracts/create?cmoId=${encodeURIComponent(c.cmoId)}`)}>
                  Create Contract
                </Button>
                <Button variant="inline-link" onClick={() => openEdit(c)}>
                  Edit
                </Button>
                {c.status !== 'inactive' && (
                  <Button variant="inline-link" onClick={() => handleDeactivate(c)}>
                    Deactivate
                  </Button>
                )}
              </SpaceBetween>
            ),
          },
        ]}
      />

      <Modal
        visible={inviteModalOpen}
        onDismiss={() => setInviteModalOpen(false)}
        header={`Invite User — ${inviteCmo?.organizationName}`}
        footer={
          <SpaceBetween direction="horizontal" size="xs">
            <Button variant="link" onClick={() => setInviteModalOpen(false)}>Cancel</Button>
            <Button variant="primary" loading={inviteLoading} onClick={handleInvite}>Send Invitation</Button>
          </SpaceBetween>
        }
      >
        <SpaceBetween size="m">
          <Box variant="p" color="text-body-secondary">
            A Cognito account will be created and the user will receive an email with temporary login credentials.
          </Box>
          <FormField label="Email address">
            <Input value={inviteEmail} onChange={({ detail }) => setInviteEmail(detail.value)} placeholder="cmo-rep@company.com" />
          </FormField>
          <FormField label="First name">
            <Input value={inviteFirst} onChange={({ detail }) => setInviteFirst(detail.value)} placeholder="Jane" />
          </FormField>
          <FormField label="Last name">
            <Input value={inviteLast} onChange={({ detail }) => setInviteLast(detail.value)} placeholder="Smith" />
          </FormField>
        </SpaceBetween>
      </Modal>

      <Modal
        visible={editModalOpen}
        onDismiss={() => setEditModalOpen(false)}
        header={`Edit CMO — ${editCmo?.organizationName}`}
        footer={
          <SpaceBetween direction="horizontal" size="xs">
            <Button variant="link" onClick={() => setEditModalOpen(false)}>Cancel</Button>
            <Button variant="primary" loading={editLoading} onClick={handleEdit}>Save Changes</Button>
          </SpaceBetween>
        }
      >
        <SpaceBetween size="m">
          <FormField label="Organization Name">
            <Input value={editForm.organizationName} onChange={({ detail }) => setEditForm(f => ({ ...f, organizationName: detail.value }))} />
          </FormField>
          <FormField label="Contact Email">
            <Input value={editForm.contactEmail} onChange={({ detail }) => setEditForm(f => ({ ...f, contactEmail: detail.value }))} />
          </FormField>
          <FormField label="Contact Phone">
            <Input value={editForm.contactPhone} onChange={({ detail }) => setEditForm(f => ({ ...f, contactPhone: detail.value }))} />
          </FormField>
          <FormField label="Address">
            <Input value={editForm.address} onChange={({ detail }) => setEditForm(f => ({ ...f, address: detail.value }))} />
          </FormField>
        </SpaceBetween>
      </Modal>
    </SpaceBetween>
  );
}
