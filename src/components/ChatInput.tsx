import React, { useState, KeyboardEvent } from 'react';
import { Send, Loader2, WifiOff, Database } from 'lucide-react';

interface ChatInputProps {
  onSend: (message: string) => void;
  isLoading: boolean;
  isConnected: boolean;
}

export function ChatInput({ onSend, isLoading, isConnected }: ChatInputProps) {
  const [input, setInput] = useState('');

  const handleSend = () => {
    if (input.trim() && !isLoading && isConnected) {
      onSend(input.trim());
      setInput('');
    }
  };

  const handleKeyPress = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const isDisabled = !input.trim() || isLoading || !isConnected;

  const getPlaceholder = () => {
    if (!isConnected) {
      return "Connecting to DemandBot...";
    }
    return "Ask DemandBot about forecasts, trends, or market insights...";
  };

  const suggestions = [
    "What's the forecast for SKU-Electronics?",
    "Why is demand trending up for Beauty products?",
    "Compare Electronics vs Clothing performance",
    "Show me insights for all categories"
  ];

  return (
    <div className="border-t border-gray-200 bg-white p-4">
      <div className="flex gap-3 items-end">
        <div className="flex-1 relative">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder={getPlaceholder()}
            className="w-full resize-none border border-gray-300 rounded-lg px-4 py-3 focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all disabled:bg-gray-50 disabled:text-gray-500"
            rows={1}
            style={{ minHeight: '48px', maxHeight: '120px' }}
            disabled={!isConnected}
          />
          
          <div className="absolute right-3 top-1/2 transform -translate-y-1/2 flex items-center gap-2">
            {!isConnected ? (
              <WifiOff size={16} className="text-gray-400" />
            ) : (
              <Database size={16} className="text-green-500" title="Connected to Database" />
            )}
          </div>
        </div>
        
        <button
          onClick={handleSend}
          disabled={isDisabled}
          className="bg-blue-600 text-white p-3 rounded-lg hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
          title={
            !isConnected 
              ? "Not connected" 
              : isLoading 
                ? "Sending..." 
                : "Send message"
          }
        >
          {isLoading ? (
            <Loader2 size={20} className="animate-spin" />
          ) : (
            <Send size={20} />
          )}
        </button>
      </div>
      
      <div className="mt-2 flex flex-wrap gap-2">
        {suggestions.map((suggestion, index) => (
          <button
            key={index}
            onClick={() => setInput(suggestion)}
            disabled={!isConnected}
            className="text-xs bg-gray-100 text-gray-600 px-3 py-1 rounded-full hover:bg-gray-200 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {suggestion}
          </button>
        ))}
      </div>
    </div>
  );
}