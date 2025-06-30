import React, { useEffect, useRef, useState, useCallback } from 'react';
import { WSMessage, WSMessageSchema } from '../lib/schemas';

interface UseWebSocketOptions {
  url: string;
  onMessage?: (message: WSMessage) => void;
  onError?: (error: Event) => void;
  onConnect?: () => void;
  onDisconnect?: () => void;
  reconnectAttempts?: number;
  reconnectInterval?: number;
  exponentialBackoff?: boolean;
  enabled?: boolean; // New option to enable/disable WebSocket
}

export function useWebSocket({
  url,
  onMessage,
  onError,
  onConnect,
  onDisconnect,
  reconnectAttempts = 5,
  reconnectInterval = 3000,
  exponentialBackoff = true,
  enabled = true, // Default to enabled
}: UseWebSocketOptions) {
  const [isConnected, setIsConnected] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reconnectCount, setReconnectCount] = useState(0);
  
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const shouldReconnectRef = useRef(true);
  const reconnectDelayRef = useRef(reconnectInterval);
  const connectionIdRef = useRef<string | null>(null);

  const connect = useCallback(() => {
    if (!enabled) {
      return;
    }

    // Prevent multiple connections - important for React StrictMode
    if (wsRef.current?.readyState === WebSocket.OPEN || wsRef.current?.readyState === WebSocket.CONNECTING) {
      console.log('WebSocket already connecting or connected, skipping...');
      return;
    }

    // Clean up any existing connection first
    if (wsRef.current) {
      console.log('Cleaning up existing WebSocket connection');
      wsRef.current.close();
      wsRef.current = null;
    }

    setIsConnecting(true);
    setError(null);

    try {
      console.log(`🔄 Attempting to connect to WebSocket: ${url}`);
      const connectionId = Date.now().toString();
      connectionIdRef.current = connectionId;
      
      const ws = new WebSocket(url);
      console.log(`WebSocket object created, readyState: ${ws.readyState}, connectionId: ${connectionId}`);
      wsRef.current = ws;

      ws.onopen = () => {
        // Only proceed if this is still the current connection
        if (connectionIdRef.current !== connectionId) {
          console.log('⚠️ WebSocket opened but connection ID changed, closing stale connection');
          ws.close();
          return;
        }
        
        console.log('✅ WebSocket connection opened successfully!');
        setIsConnected(true);
        setIsConnecting(false);
        setReconnectCount(0);
        setError(null);
        
        // Reset reconnect delay on successful connection
        reconnectDelayRef.current = reconnectInterval;
        
        onConnect?.();
      };

      ws.onmessage = (event) => {
        // Only process messages if this is still the current connection
        if (connectionIdRef.current !== connectionId) {
          console.log('⚠️ Received message from stale connection, ignoring');
          return;
        }
        
        try {
          const data = JSON.parse(event.data);
          console.log('Raw WebSocket message received:', data);
          
          // Try to validate the message
          const validatedMessage = WSMessageSchema.parse(data);
          console.log('Validated WebSocket message:', validatedMessage);
          onMessage?.(validatedMessage);
        } catch (err) {
          console.error('WebSocket message validation failed:', err);
          console.error('Raw message data:', event.data);
          
          // Don't set error state for validation issues - just log and continue
          // The connection should remain stable even if a message format is unexpected
          console.warn('Continuing with connection despite message validation error');
          
          // Try to pass the raw message anyway for debugging
          try {
            const data = JSON.parse(event.data);
            if (data.type && data.data) {
              onMessage?.(data as any);
            }
          } catch (parseErr) {
            console.error('Failed to parse WebSocket message as JSON:', parseErr);
          }
        }
      };

      ws.onerror = (event) => {
        console.error(`❌ WebSocket error event: ${connectionId}`, event);
        console.error('WebSocket readyState:', ws.readyState);
        
        // Only handle errors for the current connection
        if (connectionIdRef.current === connectionId) {
          setError('WebSocket connection error');
          onError?.(event);
        } else {
          console.log('⚠️ Error event from stale connection, ignoring');
        }
      };

      ws.onclose = (event) => {
        console.log(`❌ WebSocket closed. Code: ${event.code}, Reason: "${event.reason}", WasClean: ${event.wasClean}, ConnectionId: ${connectionId}`);
        console.log('WebSocket close event details:', event);
        
        // Only handle close events for the current connection
        if (connectionIdRef.current !== connectionId) {
          console.log('⚠️ Close event from stale connection, ignoring');
          return;
        }
        
        setIsConnected(false);
        setIsConnecting(false);
        onDisconnect?.();

        // Auto-reconnect logic with exponential backoff
        if (enabled && shouldReconnectRef.current && reconnectCount < reconnectAttempts) {
          const delay = exponentialBackoff 
            ? reconnectDelayRef.current * Math.pow(2, reconnectCount)
            : reconnectDelayRef.current;
          
          // Cap maximum delay at 30 seconds
          const actualDelay = Math.min(delay, 30000);
          
          console.log(`Reconnecting in ${actualDelay}ms (attempt ${reconnectCount + 1}/${reconnectAttempts})`);
          
          reconnectTimeoutRef.current = setTimeout(() => {
            setReconnectCount(prev => prev + 1);
            connect();
          }, actualDelay);
        } else if (reconnectCount >= reconnectAttempts) {
          setError('Maximum reconnection attempts reached');
        }
      };
    } catch (err) {
      setIsConnecting(false);
      setError('Failed to create WebSocket connection');
    }
  }, [url, onMessage, onError, onConnect, onDisconnect, reconnectCount, reconnectAttempts, reconnectInterval, exponentialBackoff, enabled]);

  const disconnect = useCallback(() => {
    shouldReconnectRef.current = false;
    connectionIdRef.current = null; // Clear connection ID to invalidate any pending operations
    
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
  }, []);

  const sendMessage = useCallback((message: any) => {
    if (enabled && wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message));
      return true;
    }
    return false;
  }, [enabled]);

  // Manual reconnect function
  const reconnect = useCallback(() => {
    setReconnectCount(0);
    reconnectDelayRef.current = reconnectInterval;
    shouldReconnectRef.current = true;
    
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    
    disconnect();
    setTimeout(connect, 100); // Small delay before reconnecting
  }, [connect, disconnect, reconnectInterval]);

  useEffect(() => {
    if (enabled) {
      shouldReconnectRef.current = true;
      connect();
    } else {
      shouldReconnectRef.current = false;
      disconnect();
    }

    return () => {
      shouldReconnectRef.current = false;
      disconnect();
    };
  }, [connect, disconnect, enabled]);

  return {
    isConnected,
    isConnecting,
    error,
    reconnectCount,
    sendMessage,
    connect,
    disconnect,
    reconnect,
  };
}