import React, { useState, useCallback, useRef } from 'react';
import { Message } from '../types';
import { v4 as uuidv4 } from 'uuid';
import { useWebSocket } from './useWebSocket';
import { WSMessage, ChatResponse, ChatResponseSchema, ErrorResponseSchema } from '../lib/schemas';
import { useToast } from './useToast';

const WS_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8005/chat';

export function useChat() {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: uuidv4(),
      content: "Hello! I'm DemandBot, your AI-powered demand forecasting assistant. I can help you analyze sales forecasts, understand market trends, and answer questions about your product portfolio. What would you like to know?",
      sender: 'bot',
      timestamp: new Date(),
    }
  ]);
  const [isLoading, setIsLoading] = useState(false);
  const [streamingMessageId, setStreamingMessageId] = useState<string | null>(null);
  
  const { showToast } = useToast();
  const streamingContentRef = useRef<string>('');

  const handleWebSocketMessage = useCallback((wsMessage: WSMessage) => {
    switch (wsMessage.type) {
      case 'stream_start':
        const messageId = uuidv4();
        setStreamingMessageId(messageId);
        streamingContentRef.current = '';
        
        // Add placeholder message for streaming
        const placeholderMessage: Message = {
          id: messageId,
          content: '',
          sender: 'bot',
          timestamp: new Date(),
        };
        setMessages(prev => [...prev, placeholderMessage]);
        break;

      case 'stream_chunk':
        if (streamingMessageId && wsMessage.data?.content) {
          streamingContentRef.current += wsMessage.data.content;
          
          // Update the streaming message
          setMessages(prev => prev.map(msg => 
            msg.id === streamingMessageId 
              ? { ...msg, content: streamingContentRef.current }
              : msg
          ));
        }
        break;

      case 'stream_end':
        if (streamingMessageId && wsMessage.data) {
          try {
            const chatResponse = ChatResponseSchema.parse(wsMessage.data);
            
            // Update final message with complete data
            setMessages(prev => prev.map(msg => 
              msg.id === streamingMessageId 
                ? {
                    ...msg,
                    content: chatResponse.content,
                    metadata: {
                      forecast: chatResponse.forecast,
                      sources: chatResponse.sources,
                      entities: chatResponse.entities,
                    }
                  }
                : msg
            ));
          } catch (err) {
            console.error('Invalid chat response:', err);
            showToast('Received invalid response format', 'error');
          }
        }
        
        setStreamingMessageId(null);
        setIsLoading(false);
        break;

      case 'chat_response':
        // Handle non-streaming response
        try {
          const chatResponse = ChatResponseSchema.parse(wsMessage.data);
          
          const botMessage: Message = {
            id: uuidv4(),
            content: chatResponse.content,
            sender: 'bot',
            timestamp: new Date(),
            metadata: {
              forecast: chatResponse.forecast,
              sources: chatResponse.sources,
              entities: chatResponse.entities,
            }
          };

          setMessages(prev => [...prev, botMessage]);
        } catch (err) {
          console.error('Invalid chat response:', err);
          showToast('Received invalid response format', 'error');
        }
        
        setIsLoading(false);
        break;

      case 'error':
        try {
          const errorResponse = ErrorResponseSchema.parse(wsMessage.data);
          showToast(errorResponse.error, 'error');
          
          const errorMessage: Message = {
            id: uuidv4(),
            content: "I apologize, but I encountered an error processing your request. Please try again.",
            sender: 'bot',
            timestamp: new Date(),
          };
          
          setMessages(prev => [...prev, errorMessage]);
        } catch (err) {
          showToast('An unexpected error occurred', 'error');
        }
        
        setIsLoading(false);
        setStreamingMessageId(null);
        break;
    }
  }, [streamingMessageId, showToast]);

  const handleWebSocketError = useCallback(() => {
    showToast('Connection lost. Attempting to reconnect...', 'error');
    setIsLoading(false);
    setStreamingMessageId(null);
  }, [showToast]);

  const handleWebSocketConnect = useCallback(() => {
    // Temporarily disable toast notifications to prevent re-render loops
    // showToast('Connected to DemandBot', 'success');
    console.log('✅ Connected to DemandBot');
  }, []);

  const handleWebSocketDisconnect = useCallback(() => {
    // Temporarily disable toast notifications to prevent re-render loops  
    // showToast('Disconnected from DemandBot', 'warning');
    console.log('⚠️ Disconnected from DemandBot');
  }, []);

  const { isConnected, isConnecting, error, sendMessage, reconnectCount } = useWebSocket({
    url: WS_URL,
    onMessage: handleWebSocketMessage,
    onError: handleWebSocketError,
    onConnect: handleWebSocketConnect,
    onDisconnect: handleWebSocketDisconnect,
    enabled: true,
  });

  const sendChatMessage = useCallback(async (content: string) => {
    const userMessage: Message = {
      id: uuidv4(),
      content,
      sender: 'user',
      timestamp: new Date(),
    };

    setMessages(prev => [...prev, userMessage]);
    setIsLoading(true);

    if (!isConnected) {
      showToast('Not connected to server. Please wait...', 'error');
      setIsLoading(false);
      return;
    }

    const success = sendMessage({
      type: 'chat_message',
      data: {
        content,
        user_id: 'default',
      },
      id: uuidv4(),
      timestamp: new Date().toISOString(),
    });

    if (!success) {
      showToast('Failed to send message. Please try again.', 'error');
      setIsLoading(false);
    }
  }, [isConnected, sendMessage, showToast]);

  return {
    messages,
    sendMessage: sendChatMessage,
    isLoading,
    isConnected,
    isConnecting,
    connectionError: error,
    reconnectCount,
    isStreaming: streamingMessageId !== null,
  };
}