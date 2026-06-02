import { useState, useCallback } from 'react';
import { UseNotificationsReturn } from './useNotifications';

export interface UseApiCallReturn<T> {
  /** Whether the API call is in progress */
  loading: boolean;
  /**
   * Execute an async operation with automatic loading state management
   * and notification handling.
   *
   * @param fn - The async function to execute
   * @param successMessage - Message shown on success (or a function that receives the result)
   * @returns The result of the async function, or undefined on error
   */
  execute: (
    fn: () => Promise<T>,
    successMessage?: string | ((result: T) => string),
  ) => Promise<T | undefined>;
}

/**
 * Hook that wraps async API calls with loading state, success flash messages,
 * and error flash messages with actionable guidance.
 *
 * Usage:
 * ```ts
 * const notifications = useNotifications();
 * const { loading, execute } = useApiCall<MyResponse>(notifications);
 *
 * async function handleSubmit() {
 *   const result = await execute(
 *     () => myApiCall(data),
 *     (res) => `Created successfully: ${res.id}`
 *   );
 *   if (result) { // success path }
 * }
 * ```
 */
export function useApiCall<T = void>(
  notifications: UseNotificationsReturn,
): UseApiCallReturn<T> {
  const [loading, setLoading] = useState(false);

  const execute = useCallback(
    async (
      fn: () => Promise<T>,
      successMessage?: string | ((result: T) => string),
    ): Promise<T | undefined> => {
      setLoading(true);
      notifications.clearAll();
      try {
        const result = await fn();
        if (successMessage) {
          const msg =
            typeof successMessage === 'function'
              ? successMessage(result)
              : successMessage;
          notifications.notifySuccess(msg);
        }
        return result;
      } catch (err: unknown) {
        const message =
          err instanceof Error ? err.message : 'An unexpected error occurred.';
        notifications.notifyError(message);
        return undefined;
      } finally {
        setLoading(false);
      }
    },
    [notifications],
  );

  return { loading, execute };
}
