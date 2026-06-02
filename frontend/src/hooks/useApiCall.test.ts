import { renderHook, act } from '@testing-library/react';
import { useNotifications } from './useNotifications';
import { useApiCall } from './useApiCall';

function setup<T = void>() {
  const { result } = renderHook(() => {
    const notifications = useNotifications();
    const apiCall = useApiCall<T>(notifications);
    return { notifications, apiCall };
  });
  return result;
}

describe('useApiCall', () => {
  it('starts with loading false', () => {
    const result = setup();
    expect(result.current.apiCall.loading).toBe(false);
  });

  it('sets loading during execution and clears after', async () => {
    const result = setup<string>();
    let resolvePromise!: (value: string) => void;
    const promise = new Promise<string>((resolve) => {
      resolvePromise = resolve;
    });

    let executePromise: Promise<string | undefined>;
    act(() => {
      executePromise = result.current.apiCall.execute(() => promise, 'Done');
    });

    expect(result.current.apiCall.loading).toBe(true);

    await act(async () => {
      resolvePromise('result');
      await executePromise;
    });

    expect(result.current.apiCall.loading).toBe(false);
  });

  it('shows success notification on success', async () => {
    const result = setup<string>();

    await act(async () => {
      await result.current.apiCall.execute(
        () => Promise.resolve('ok'),
        'It worked!',
      );
    });

    expect(result.current.notifications.items).toHaveLength(1);
    expect(result.current.notifications.items[0].type).toBe('success');
    expect(result.current.notifications.items[0].content).toBe('It worked!');
  });

  it('supports function-based success messages', async () => {
    const result = setup<{ id: string }>();

    await act(async () => {
      await result.current.apiCall.execute(
        () => Promise.resolve({ id: 'abc-123' }),
        (res) => `Created: ${res.id}`,
      );
    });

    expect(result.current.notifications.items[0].content).toBe('Created: abc-123');
  });

  it('shows error notification with guidance on failure', async () => {
    const result = setup();

    await act(async () => {
      await result.current.apiCall.execute(
        () => Promise.reject(new Error('Request timed out')),
      );
    });

    expect(result.current.notifications.items).toHaveLength(1);
    expect(result.current.notifications.items[0].type).toBe('error');
    expect(result.current.notifications.items[0].content).toContain('timed out');
    expect(result.current.notifications.items[0].content).toContain('network connection');
  });

  it('returns result on success and undefined on failure', async () => {
    const result = setup<string>();

    let successResult: string | undefined;
    let failResult: string | undefined;

    await act(async () => {
      successResult = await result.current.apiCall.execute(
        () => Promise.resolve('data'),
        'ok',
      );
    });
    expect(successResult).toBe('data');

    await act(async () => {
      failResult = await result.current.apiCall.execute(
        () => Promise.reject(new Error('fail')),
      );
    });
    expect(failResult).toBeUndefined();
  });

  it('clears previous notifications before each call', async () => {
    const result = setup<string>();

    await act(async () => {
      await result.current.apiCall.execute(
        () => Promise.resolve('first'),
        'First success',
      );
    });
    expect(result.current.notifications.items).toHaveLength(1);

    await act(async () => {
      await result.current.apiCall.execute(
        () => Promise.resolve('second'),
        'Second success',
      );
    });
    // Previous notification cleared, only new one present
    expect(result.current.notifications.items).toHaveLength(1);
    expect(result.current.notifications.items[0].content).toBe('Second success');
  });

  it('handles non-Error thrown values', async () => {
    const result = setup();

    await act(async () => {
      await result.current.apiCall.execute(() => Promise.reject('string error'));
    });

    expect(result.current.notifications.items[0].content).toContain(
      'An unexpected error occurred',
    );
  });
});
