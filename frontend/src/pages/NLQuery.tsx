import { useState, useCallback } from 'react';
import Header from '@cloudscape-design/components/header';
import Container from '@cloudscape-design/components/container';
import SpaceBetween from '@cloudscape-design/components/space-between';
import FormField from '@cloudscape-design/components/form-field';
import Textarea from '@cloudscape-design/components/textarea';
import Button from '@cloudscape-design/components/button';
import Box from '@cloudscape-design/components/box';
import Flashbar from '@cloudscape-design/components/flashbar';
import Spinner from '@cloudscape-design/components/spinner';
import ExpandableSection from '@cloudscape-design/components/expandable-section';
import { useNotifications } from '../hooks/useNotifications';
import { submitNLQuery, NLQueryResponse } from '../services/api';

export default function NLQuery() {
  const [queryText, setQueryText] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<NLQueryResponse | null>(null);
  const notifications = useNotifications();

  const handleSubmit = useCallback(async () => {
    const trimmed = queryText.trim();
    if (!trimmed) return;

    notifications.clearAll();
    setLoading(true);
    setResult(null);

    try {
      const response = await submitNLQuery({
        query: trimmed,
        user_id: 'current-user', // Resolved server-side via authorizer in production
      });
      setResult(response);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'An unexpected error occurred.';
      notifications.notifyError(message);
    } finally {
      setLoading(false);
    }
  }, [queryText, notifications]);

  const handleKeyDown = useCallback(
    (e: CustomEvent<{ keyCode: number; key: string; ctrlKey: boolean }>) => {
      if (e.detail.key === 'Enter' && e.detail.ctrlKey) {
        handleSubmit();
      }
    },
    [handleSubmit],
  );

  return (
    <SpaceBetween size="l">
      <Header variant="h1" description="Query CMO data using natural language">
        Natural Language Query
      </Header>

      <Flashbar items={notifications.items} />

      <Container header={<Header variant="h2">Ask a Question</Header>}>
        <SpaceBetween size="m">
          <FormField
            label="Your question"
            description="Ask about batch records, quality metrics, SLA compliance, or any CMO data. Press Ctrl+Enter to submit."
          >
            <Textarea
              value={queryText}
              onChange={({ detail }) => setQueryText(detail.value)}
              onKeyDown={handleKeyDown}
              placeholder="e.g. What was the average quality score for CMO Alpha last month?"
              rows={3}
              disabled={loading}
              ariaLabel="Natural language query input"
            />
          </FormField>
          <Button
            variant="primary"
            onClick={handleSubmit}
            loading={loading}
            disabled={!queryText.trim()}
            ariaLabel="Submit query"
          >
            Submit Query
          </Button>
        </SpaceBetween>
      </Container>

      {loading && (
        <Container>
          <Box textAlign="center" padding="l">
            <SpaceBetween size="s" alignItems="center" direction="vertical">
              <Spinner size="large" />
              <Box variant="p" color="text-body-secondary">
                Processing your query…
              </Box>
            </SpaceBetween>
          </Box>
        </Container>
      )}

      {result && !loading && (
        <Container header={<Header variant="h2">Results</Header>}>
          <SpaceBetween size="m">
            <Box variant="p" data-testid="nl-response">
              {result.response}
            </Box>

            {result.sql && (
              <ExpandableSection headerText="Generated SQL">
                <Box variant="code">{result.sql}</Box>
              </ExpandableSection>
            )}
          </SpaceBetween>
        </Container>
      )}
    </SpaceBetween>
  );
}
