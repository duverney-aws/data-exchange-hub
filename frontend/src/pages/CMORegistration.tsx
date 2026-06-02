import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Button from '@cloudscape-design/components/button';
import Checkbox from '@cloudscape-design/components/checkbox';
import Container from '@cloudscape-design/components/container';
import Flashbar, { FlashbarProps } from '@cloudscape-design/components/flashbar';
import Form from '@cloudscape-design/components/form';
import FormField from '@cloudscape-design/components/form-field';
import Header from '@cloudscape-design/components/header';
import Input from '@cloudscape-design/components/input';
import SpaceBetween from '@cloudscape-design/components/space-between';
import { registerCMO } from '../services/api';

const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

interface FormErrors {
  organizationName?: string;
  contactEmail?: string;
  contactPhone?: string;
  address?: string;
}

export default function CMORegistration() {
  const navigate = useNavigate();
  const [organizationName, setOrganizationName] = useState('');
  const [contactEmail, setContactEmail] = useState('');
  const [contactPhone, setContactPhone] = useState('');
  const [address, setAddress] = useState('');
  const [gxpCertified, setGxpCertified] = useState(false);
  const [errors, setErrors] = useState<FormErrors>({});
  const [loading, setLoading] = useState(false);
  const [flashItems, setFlashItems] = useState<FlashbarProps.MessageDefinition[]>([]);

  function validate(): FormErrors {
    const result: FormErrors = {};
    if (!organizationName.trim()) result.organizationName = 'Organization name is required.';
    if (!contactEmail.trim()) {
      result.contactEmail = 'Contact email is required.';
    } else if (!EMAIL_REGEX.test(contactEmail.trim())) {
      result.contactEmail = 'Enter a valid email address.';
    }
    if (!contactPhone.trim()) result.contactPhone = 'Contact phone is required.';
    if (!address.trim()) result.address = 'Address is required.';
    return result;
  }

  async function handleSubmit() {
    const validationErrors = validate();
    setErrors(validationErrors);
    if (Object.keys(validationErrors).length > 0) return;

    setLoading(true);
    setFlashItems([]);
    try {
      const result = await registerCMO({
        organizationName: organizationName.trim(),
        contactEmail: contactEmail.trim(),
        contactPhone: contactPhone.trim(),
        address: address.trim(),
        gxpCertified,
      });
      navigate(`/products?cmoId=${encodeURIComponent(result.cmoId)}`);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'An unexpected error occurred.';
      setFlashItems([
        {
          type: 'error',
          dismissible: true,
          onDismiss: () => setFlashItems([]),
          content: `Registration failed: ${message}`,
        },
      ]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <SpaceBetween size="l">
      <Header variant="h1" description="Register a new Contract Manufacturing Organization">
        CMO Registration
      </Header>
      <Flashbar items={flashItems} />
      <form onSubmit={(e) => e.preventDefault()}>
        <Form
          actions={
            <Button variant="primary" loading={loading} onClick={handleSubmit}>
              Register CMO
            </Button>
          }
        >
          <Container header={<Header variant="h2">Organization Details</Header>}>
            <SpaceBetween size="l">
              <FormField
                label="Organization Name"
                description="Legal name of the CMO organization"
                errorText={errors.organizationName}
              >
                <Input
                  value={organizationName}
                  onChange={({ detail }) => setOrganizationName(detail.value)}
                  placeholder="Enter organization name"
                />
              </FormField>
              <FormField
                label="Contact Email"
                description="Primary contact email address"
                errorText={errors.contactEmail}
              >
                <Input
                  value={contactEmail}
                  onChange={({ detail }) => setContactEmail(detail.value)}
                  placeholder="email@example.com"
                  inputMode="email"
                />
              </FormField>
              <FormField
                label="Contact Phone"
                description="Primary contact phone number"
                errorText={errors.contactPhone}
              >
                <Input
                  value={contactPhone}
                  onChange={({ detail }) => setContactPhone(detail.value)}
                  placeholder="+1-555-000-0000"
                  inputMode="tel"
                />
              </FormField>
              <FormField
                label="Address"
                description="Physical address of the organization"
                errorText={errors.address}
              >
                <Input
                  value={address}
                  onChange={({ detail }) => setAddress(detail.value)}
                  placeholder="Enter full address"
                />
              </FormField>
              <FormField label="GxP Certification">
                <Checkbox
                  checked={gxpCertified}
                  onChange={({ detail }) => setGxpCertified(detail.checked)}
                >
                  This organization is GxP certified
                </Checkbox>
              </FormField>
            </SpaceBetween>
          </Container>
        </Form>
      </form>
    </SpaceBetween>
  );
}
