import { signInWithRedirect } from 'aws-amplify/auth';
import Button from '@cloudscape-design/components/button';
import Box from '@cloudscape-design/components/box';
import Container from '@cloudscape-design/components/container';
import Header from '@cloudscape-design/components/header';
import SpaceBetween from '@cloudscape-design/components/space-between';

export default function Login() {
  return (
    <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '100vh', background: '#f2f3f3' }}>
      <div style={{ width: 400 }}>
        <Container header={<Header variant="h1">Pharma Data Exchange Hub</Header>}>
          <SpaceBetween size="l">
            <Box variant="p" color="text-body-secondary">
              Self-service portal for CMO data integration. Sign in with your Merck or CMO credentials.
            </Box>
            <Button
              variant="primary"
              fullWidth
              onClick={() => signInWithRedirect()}
            >
              Sign in
            </Button>
          </SpaceBetween>
        </Container>
      </div>
    </div>
  );
}
