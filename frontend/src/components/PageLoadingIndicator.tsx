import Box from '@cloudscape-design/components/box';
import Spinner from '@cloudscape-design/components/spinner';

interface PageLoadingIndicatorProps {
  /** Text displayed below the spinner */
  label?: string;
}

/**
 * Centered loading spinner for full-page loading states.
 * Uses Cloudscape Spinner with a descriptive label.
 */
export default function PageLoadingIndicator({
  label = 'Loading…',
}: PageLoadingIndicatorProps) {
  return (
    <Box textAlign="center" padding={{ vertical: 'xxxl' }}>
      <Spinner size="large" />
      <Box variant="p" color="text-body-secondary" margin={{ top: 's' }}>
        {label}
      </Box>
    </Box>
  );
}
