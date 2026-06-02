import { renderHook, act } from '@testing-library/react';
import { useNotifications } from './useNotifications';

describe('useNotifications', () => {
  it('starts with empty items', () => {
    const { result } = renderHook(() => useNotifications());
    expect(result.current.items).toHaveLength(0);
  });

  it('adds a success notification', () => {
    const { result } = renderHook(() => useNotifications());
    act(() => result.current.notifySuccess('Operation completed'));
    expect(result.current.items).toHaveLength(1);
    expect(result.current.items[0].type).toBe('success');
    expect(result.current.items[0].content).toBe('Operation completed');
  });

  it('adds an error notification with actionable guidance', () => {
    const { result } = renderHook(() => useNotifications());
    act(() => result.current.notifyError('Request timed out'));
    expect(result.current.items).toHaveLength(1);
    expect(result.current.items[0].type).toBe('error');
    expect(result.current.items[0].content).toContain('timed out');
    expect(result.current.items[0].content).toContain('network connection');
  });

  it('enriches network errors with guidance', () => {
    const { result } = renderHook(() => useNotifications());
    act(() => result.current.notifyError('Failed to fetch'));
    expect(result.current.items[0].content).toContain('network error');
  });

  it('enriches 401 errors with session guidance', () => {
    const { result } = renderHook(() => useNotifications());
    act(() => result.current.notifyError('401 Unauthorized'));
    expect(result.current.items[0].content).toContain('sign in');
  });

  it('enriches 403 errors with permission guidance', () => {
    const { result } = renderHook(() => useNotifications());
    act(() => result.current.notifyError('403 Forbidden'));
    expect(result.current.items[0].content).toContain('permission');
  });

  it('enriches 404 errors with not-found guidance', () => {
    const { result } = renderHook(() => useNotifications());
    act(() => result.current.notifyError('404 Not Found'));
    expect(result.current.items[0].content).toContain('not found');
  });

  it('enriches credential errors with verification guidance', () => {
    const { result } = renderHook(() => useNotifications());
    act(() => result.current.notifyError('Invalid credential provided'));
    expect(result.current.items[0].content).toContain('credentials');
  });

  it('adds generic guidance for unknown errors', () => {
    const { result } = renderHook(() => useNotifications());
    act(() => result.current.notifyError('Something went wrong'));
    expect(result.current.items[0].content).toContain('contact support');
  });

  it('adds warning and info notifications', () => {
    const { result } = renderHook(() => useNotifications());
    act(() => {
      result.current.notifyWarning('Heads up');
      result.current.notifyInfo('FYI');
    });
    expect(result.current.items).toHaveLength(2);
    expect(result.current.items[0].type).toBe('warning');
    expect(result.current.items[1].type).toBe('info');
  });

  it('clears all notifications', () => {
    const { result } = renderHook(() => useNotifications());
    act(() => {
      result.current.notifySuccess('A');
      result.current.notifyError('B');
    });
    expect(result.current.items).toHaveLength(2);
    act(() => result.current.clearAll());
    expect(result.current.items).toHaveLength(0);
  });

  it('dismisses individual notifications', () => {
    const { result } = renderHook(() => useNotifications());
    act(() => {
      result.current.notifySuccess('First');
      result.current.notifySuccess('Second');
    });
    expect(result.current.items).toHaveLength(2);
    // Dismiss the first one
    act(() => result.current.items[0].onDismiss!(new CustomEvent('dismiss')));
    expect(result.current.items).toHaveLength(1);
    expect(result.current.items[0].content).toContain('Second');
  });

  it('marks all notifications as dismissible', () => {
    const { result } = renderHook(() => useNotifications());
    act(() => result.current.notifySuccess('Test'));
    expect(result.current.items[0].dismissible).toBe(true);
  });
});
