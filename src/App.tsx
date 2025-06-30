import React, { useRef, useEffect } from 'react';
import { Brain, BarChart3 } from 'lucide-react';
import { ChatHistory } from './components/ChatHistory';
import { MessageBubble } from './components/MessageBubble';
import { ChatInput } from './components/ChatInput';
import { ContextPanel } from './components/ContextPanel';
import { LoadingIndicator } from './components/LoadingIndicator';
import { ConnectionStatus } from './components/ConnectionStatus';
import { ToastContainer } from './components/ToastContainer';
import { useChat } from './hooks/useChat';

function App() {
  const { 
    messages, 
    sendMessage, 
    isLoading, 
    isConnected, 
    isConnecting, 
    connectionError, 
    reconnectCount,
    isStreaming
  } = useChat();
  
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading]);

  const lastMessage = messages[messages.length - 1];

  return (
    <div className="h-screen flex flex-col bg-gray-100">
      {/* Toast Container */}
      <ToastContainer />
      
      {/* Header */}
      <header className="bg-white border-b border-gray-200 px-6 py-4 shadow-sm">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-gradient-to-br from-blue-600 to-blue-700 rounded-lg flex items-center justify-center">
              <Brain size={24} className="text-white" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-gray-900">DemandBot</h1>
              <p className="text-sm text-gray-600">AI-Powered Demand Forecasting Platform</p>
            </div>
          </div>
          
          <div className="flex items-center gap-4">
            <ConnectionStatus 
              isConnected={isConnected}
              isConnecting={isConnecting}
              error={connectionError}
              reconnectCount={reconnectCount}
            />
            
            <div className="flex items-center gap-2 text-sm text-gray-600">
              <BarChart3 size={16} />
              <span>1K+ Real Data Points</span>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left Panel - Chat History */}
        <div className="w-80 flex-shrink-0">
          <ChatHistory />
        </div>

        {/* Center Panel - Chat Interface */}
        <div className="flex-1 flex flex-col">
          <div className="flex-1 overflow-y-auto p-6">
            <div className="max-w-4xl mx-auto">
              {messages.map((message) => (
                <MessageBubble key={message.id} message={message} />
              ))}
              {isLoading && (
                <LoadingIndicator 
                  isConnected={isConnected}
                  isStreaming={isStreaming}
                  reconnectCount={reconnectCount}
                />
              )}
              <div ref={messagesEndRef} />
            </div>
          </div>
          <ChatInput 
            onSend={sendMessage} 
            isLoading={isLoading} 
            isConnected={isConnected}
          />
        </div>

        {/* Right Panel - Context */}
        <div className="w-96 flex-shrink-0">
          <ContextPanel lastMessage={lastMessage?.sender === 'bot' ? lastMessage : undefined} />
        </div>
      </div>
    </div>
  );
}

export default App;