import { useState, useCallback } from 'react';
import { FlashbarProps } from '@cloudscape-design/components/flashbar';

export type NotificationType = 'success' | 'error' | 'warning' | 'info';

let idCounter = 0;

/**
 * Provides actionable error guidance based on common error patterns.
 */
function enrichErrorMessage(message: string): string {
  const lower = message.toLowerCase();

  if (lower.includes('timeout') || lower.includes('timed out')) {
    return `${message} — The request took too long. Check your network connection and try again.`;
  }
  if (lower.includes('network') || lower.includes('fetch') || lower.includes('failed to fetch')) {
    return `${message} — A network error occurred. Verify your internet connection and try again.`;
  }
  if (lower.includes('401') || lower.includes('unauthorized')) {
    return `${message} — Your session may have expired. Please sign in again.`;
  }
  if (lower.includes('403') || lower.includes('forbidden')) {
    return `${message} — You do not have permission to perform this action. Contact your administrator.`;
  }
  if (lower.includes('404') || lower.includes('not found')) {
    return `${message} — The requested resource was not found. It may have been deleted or the ID is incorrect.`;
  }
  if (lower.includes('409') || lower.includes('conflict')) {
    return `${message} — A conflict occurred. The resource may have been modified by another user. Refresh and try again.`;
  }
  if (lower.includes('500') || lower.includes('internal server')) {
    return `${message} — An internal server error occurred. Please try again later or contact support.`;
  }
  if (lower.includes('schema') || lower.includes('validation')) {
    return `${message} — Review your input data for correctness and try again.`;
  }
  if (lower.includes('credential') || lower.includes('auth') || lower.includes('password')) {
    return `${message} — Verify your credentials are correct and have the required permissions.`;
  }

  return `${message} — If this issue persists, please contact support.`;
}

export interface UseNotificationsReturn {
  /** Current flash bar items */
  items: FlashbarProps.MessageDefinition[];
  /** Add a success notification */
  notifySuccess: (content: string) => void;
  /** Add an error notification with actionable guidance */
  notifyError: (content: string) => void;
  /** Add a warning notification */
  notifyWarning: (content: string) => void;
  /** Add an info notification */
  notifyInfo: (content: string) => void;
  /** Clear all notifications */
  clearAll: () => void;
}

/**
 * Hook for managing Cloudscape Flashbar notifications with consistent
 * loading feedback and actionable error messages.
 */
export function useNotifications(): UseNotificationsReturn {
  const [items, setItems] = useState<FlashbarProps.MessageDefinition[]>([]);

  const dismiss = useCallback((id: string) => {
    setItems((prev) => prev.filter((item) => item.id !== id));
  }, []);

  const addNotification = useCallback(
    (type: NotificationType, content: string) => {
      const id = `notification-${++idCounter}`;
      const enrichedContent = type === 'error' ? enrichErrorMessage(content) : content;

      setItems((prev) => [
        ...prev,
        {
          id,
          type,
          dismissible: true,
          dismissLabel: 'Dismiss',
          onDismiss: () => dismiss(id),
          content: enrichedContent,
        },
      ]);
    },
    [dismiss],
  );

  const notifySuccess = useCallback(
    (content: string) => addNotification('success', content),
    [addNotification],
  );

  const notifyError = useCallback(
    (content: string) => addNotification('error', content),
    [addNotification],
  );

  const notifyWarning = useCallback(
    (content: string) => addNotification('warning', content),
    [addNotification],
  );

  const notifyInfo = useCallback(
    (content: string) => addNotification('info', content),
    [addNotification],
  );

  const clearAll = useCallback(() => setItems([]), []);

  return { items, notifySuccess, notifyError, notifyWarning, notifyInfo, clearAll };
}
