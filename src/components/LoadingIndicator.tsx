import React from 'react';
import { Bot, Loader2, Wifi, WifiOff } from 'lucide-react';

interface LoadingIndicatorProps {
  isConnected?: boolean;
  isStreaming?: boolean;
  reconnectCount?: number;
}

export function LoadingIndicator({ isConnected = true, isStreaming = false, reconnectCount = 0 }: LoadingIndicatorProps) {
  return (
    <div className="flex gap-3 justify-start mb-4">
      <div className="flex-shrink-0 w-8 h-8 bg-blue-600 rounded-full flex items-center justify-center">
        <Bot size={16} className="text-white" />
      </div>
      
      <div className="bg-gray-50 rounded-lg p-4 shadow-sm border">
        <div className="flex items-center gap-2 text-gray-600 mb-2">
          <Loader2 size={16} className="animate-spin" />
          <span className="text-sm">
            {isStreaming ? 'DemandBot is responding...' : 'DemandBot is analyzing your request...'}
          </span>
        </div>
        
        <div className="flex items-center gap-2 text-xs text-gray-500">
          {isConnected ? (
            <>
              <Wifi size={12} className="text-green-500" />
              <span>Connected</span>
            </>
          ) : (
            <>
              <WifiOff size={12} className="text-red-500" />
              <span>
                {reconnectCount > 0 ? `Reconnecting... (${reconnectCount})` : 'Connecting...'}
              </span>
            </>
          )}
        </div>
        
        {isStreaming && (
          <div className="mt-2">
            <div className="flex space-x-1">
              <div className="w-2 h-2 bg-blue-500 rounded-full animate-bounce"></div>
              <div className="w-2 h-2 bg-blue-500 rounded-full animate-bounce" style={{ animationDelay: '0.1s' }}></div>
              <div className="w-2 h-2 bg-blue-500 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}