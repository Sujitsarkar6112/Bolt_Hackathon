import { renderHook, act } from '@testing-library/react';
import { useWebSocket } from '../hooks/useWebSocket';

// Mock WebSocket
class MockWebSocket {
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSING = 2;
  static CLOSED = 3;

  readyState = MockWebSocket.CONNECTING;
  onopen: ((event: Event) => void) | null = null;
  onclose: ((event: CloseEvent) => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;

  constructor(public url: string) {
    setTimeout(() => {
      this.readyState = MockWebSocket.OPEN;
      this.onopen?.(new Event('open'));
    }, 10);
  }

  send(data: string) {
    if (this.readyState === MockWebSocket.OPEN) {
      // Simulate echo
      setTimeout(() => {
        this.onmessage?.(new MessageEvent('message', { data }));
      }, 10);
    }
  }

  close() {
    this.readyState = MockWebSocket.CLOSED;
    this.onclose?.(new CloseEvent('close'));
  }
}

// @ts-ignore
global.WebSocket = MockWebSocket;

describe('useWebSocket', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('should connect to WebSocket', async () => {
    const onConnect = jest.fn();
    const { result } = renderHook(() =>
      useWebSocket({
        url: 'ws://localhost:8000/ws',
        onConnect,
      })
    );

    expect(result.current.isConnecting).toBe(true);
    expect(result.current.isConnected).toBe(false);

    // Wait for connection
    await act(async () => {
      await new Promise(resolve => setTimeout(resolve, 20));
    });

    expect(result.current.isConnected).toBe(true);
    expect(result.current.isConnecting).toBe(false);
    expect(onConnect).toHaveBeenCalled();
  });

  it('should send messages when connected', async () => {
    const { result } = renderHook(() =>
      useWebSocket({
        url: 'ws://localhost:8000/ws',
      })
    );

    // Wait for connection
    await act(async () => {
      await new Promise(resolve => setTimeout(resolve, 20));
    });

    const success = result.current.sendMessage({ type: 'test', data: 'hello' });
    expect(success).toBe(true);
  });

  it('should handle message reception', async () => {
    const onMessage = jest.fn();
    const { result } = renderHook(() =>
      useWebSocket({
        url: 'ws://localhost:8000/ws',
        onMessage,
      })
    );

    // Wait for connection
    await act(async () => {
      await new Promise(resolve => setTimeout(resolve, 20));
    });

    // Send a message (which will be echoed back)
    act(() => {
      result.current.sendMessage({ type: 'test', data: 'hello' });
    });

    // Wait for echo
    await act(async () => {
      await new Promise(resolve => setTimeout(resolve, 20));
    });

    expect(onMessage).toHaveBeenCalledWith({
      type: 'test',
      data: 'hello',
    });
  });

  it('should handle disconnection', async () => {
    const onDisconnect = jest.fn();
    const { result } = renderHook(() =>
      useWebSocket({
        url: 'ws://localhost:8000/ws',
        onDisconnect,
      })
    );

    // Wait for connection
    await act(async () => {
      await new Promise(resolve => setTimeout(resolve, 20));
    });

    expect(result.current.isConnected).toBe(true);

    // Disconnect
    act(() => {
      result.current.disconnect();
    });

    expect(result.current.isConnected).toBe(false);
    expect(onDisconnect).toHaveBeenCalled();
  });
});