import React from 'react';
import { Wifi, WifiOff, AlertCircle, Database } from 'lucide-react';

interface ConnectionStatusProps {
  isConnected: boolean;
  isConnecting: boolean;
  error: string | null;
  reconnectCount: number;
}

export function ConnectionStatus({ isConnected, isConnecting, error, reconnectCount }: ConnectionStatusProps) {
  if (isConnected) {
    return (
      <div className="flex items-center gap-2 text-sm text-green-600">
        <Database size={16} />
        <span>Connected</span>
      </div>
    );
  }

  if (isConnecting) {
    return (
      <div className="flex items-center gap-2 text-sm text-yellow-600">
        <WifiOff size={16} className="animate-pulse" />
        <span>
          {reconnectCount > 0 ? `Reconnecting... (${reconnectCount})` : 'Connecting...'}
        </span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center gap-2 text-sm text-red-600">
        <AlertCircle size={16} />
        <span>Connection Error</span>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2 text-sm text-gray-600">
      <WifiOff size={16} />
      <span>Disconnected</span>
    </div>
  );
}