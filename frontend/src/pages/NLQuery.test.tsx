import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import NLQuery from './NLQuery';

vi.mock('../services/api', () => ({
  submitNLQuery: vi.fn(),
}));

import { submitNLQuery } from '../services/api';
const mockSubmitNLQuery = vi.mocked(submitNLQuery);

function renderPage() {
  return render(
    <MemoryRouter>
      <NLQuery />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe('NLQuery', () => {
  it('renders the query input and submit button', () => {
    renderPage();
    expect(screen.getByText('Natural Language Query')).toBeInTheDocument();
    expect(screen.getByText('Ask a Question')).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/average quality score/i)).toBeInTheDocument();
    expect(screen.getByText('Submit Query')).toBeInTheDocument();
  });

  it('disables submit button when query is empty', () => {
    renderPage();
    const button = screen.getByText('Submit Query').closest('button')!;
    expect(button).toBeDisabled();
  });

  it('enables submit button when query has text', () => {
    renderPage();
    const textarea = screen.getByPlaceholderText(/average quality score/i);
    fireEvent.change(textarea, { target: { value: 'Show me batch records' } });
    const button = screen.getByText('Submit Query').closest('button')!;
    expect(button).not.toBeDisabled();
  });

  it('shows loading indicator during query processing', async () => {
    let resolveQuery: (value: unknown) => void;
    mockSubmitNLQuery.mockImplementation(
      () => new Promise((resolve) => { resolveQuery = resolve; }),
    );

    renderPage();
    const textarea = screen.getByPlaceholderText(/average quality score/i);
    fireEvent.change(textarea, { target: { value: 'How many batches?' } });
    fireEvent.click(screen.getByText('Submit Query'));

    await waitFor(() => {
      expect(screen.getByText('Processing your query…')).toBeInTheDocument();
    });

    // Resolve to clean up
    resolveQuery!({
      query: 'How many batches?',
      sql: 'SELECT COUNT(*) FROM batches',
      results: [],
      response: '42 batches',
      query_execution_id: 'exec-1',
    });

    await waitFor(() => {
      expect(screen.queryByText('Processing your query…')).not.toBeInTheDocument();
    });
  });

  it('displays formatted response on successful query', async () => {
    mockSubmitNLQuery.mockResolvedValueOnce({
      query: 'What is the quality score?',
      sql: 'SELECT AVG(quality_score) FROM metrics',
      results: [{ avg_quality_score: 95.5 }],
      response: 'The average quality score is 95.5%.',
      query_execution_id: 'exec-123',
    });

    renderPage();
    const textarea = screen.getByPlaceholderText(/average quality score/i);
    fireEvent.change(textarea, { target: { value: 'What is the quality score?' } });
    fireEvent.click(screen.getByText('Submit Query'));

    await waitFor(() => {
      expect(screen.getByTestId('nl-response')).toHaveTextContent(
        'The average quality score is 95.5%.',
      );
    });
  });

  it('displays generated SQL in expandable section', async () => {
    mockSubmitNLQuery.mockResolvedValueOnce({
      query: 'Count batches',
      sql: 'SELECT COUNT(*) FROM batches',
      results: [{ count: 42 }],
      response: 'There are 42 batches.',
      query_execution_id: 'exec-456',
    });

    renderPage();
    const textarea = screen.getByPlaceholderText(/average quality score/i);
    fireEvent.change(textarea, { target: { value: 'Count batches' } });
    fireEvent.click(screen.getByText('Submit Query'));

    await waitFor(() => {
      expect(screen.getByText('Generated SQL')).toBeInTheDocument();
      expect(screen.getByText('SELECT COUNT(*) FROM batches')).toBeInTheDocument();
    });
  });

  it('shows error flash message on query failure', async () => {
    mockSubmitNLQuery.mockRejectedValueOnce(new Error('Query processing failed. Please try again.'));

    renderPage();
    const textarea = screen.getByPlaceholderText(/average quality score/i);
    fireEvent.change(textarea, { target: { value: 'Bad query' } });
    fireEvent.click(screen.getByText('Submit Query'));

    await waitFor(() => {
      expect(screen.getByText(/Query processing failed/)).toBeInTheDocument();
    });
  });

  it('does not submit when query is only whitespace', () => {
    renderPage();
    const textarea = screen.getByPlaceholderText(/average quality score/i);
    fireEvent.change(textarea, { target: { value: '   ' } });
    const button = screen.getByText('Submit Query').closest('button')!;
    expect(button).toBeDisabled();
  });

  it('calls API with correct parameters', async () => {
    mockSubmitNLQuery.mockResolvedValueOnce({
      query: 'Show batches',
      sql: 'SELECT * FROM batches',
      results: [],
      response: 'No batches found.',
      query_execution_id: null,
    });

    renderPage();
    const textarea = screen.getByPlaceholderText(/average quality score/i);
    fireEvent.change(textarea, { target: { value: 'Show batches' } });
    fireEvent.click(screen.getByText('Submit Query'));

    await waitFor(() => {
      expect(mockSubmitNLQuery).toHaveBeenCalledWith({
        query: 'Show batches',
        user_id: 'current-user',
      });
    });
  });
});
