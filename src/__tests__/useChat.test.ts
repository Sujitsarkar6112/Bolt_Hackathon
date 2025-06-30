import { renderHook, act } from '@testing-library/react';
import { useChat } from '../hooks/useChat';

// Mock the WebSocket hook
jest.mock('../hooks/useWebSocket', () => ({
  useWebSocket: jest.fn(() => ({
    isConnected: true,
    isConnecting: false,
    error: null,
    sendMessage: jest.fn(() => true),
    reconnectCount: 0,
  })),
}));

// Mock the toast hook
jest.mock('../hooks/useToast', () => ({
  useToast: () => ({
    showToast: jest.fn(),
  }),
}));

describe('useChat', () => {
  it('should initialize with welcome message', () => {
    const { result } = renderHook(() => useChat());

    expect(result.current.messages).toHaveLength(1);
    expect(result.current.messages[0].sender).toBe('bot');
    expect(result.current.messages[0].content).toContain('DemandBot');
  });

  it('should add user message when sending', async () => {
    const { result } = renderHook(() => useChat());

    await act(async () => {
      result.current.sendMessage('Hello, DemandBot!');
    });

    expect(result.current.messages).toHaveLength(2);
    expect(result.current.messages[1].sender).toBe('user');
    expect(result.current.messages[1].content).toBe('Hello, DemandBot!');
    expect(result.current.isLoading).toBe(true);
  });

  it('should handle streaming messages', () => {
    const { result } = renderHook(() => useChat());

    // Simulate stream start
    act(() => {
      // This would normally be triggered by WebSocket message
      // For testing, we'll verify the hook structure
      expect(result.current.isStreaming).toBe(false);
    });
  });
});