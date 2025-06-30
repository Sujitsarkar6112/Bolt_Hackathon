import React from 'react';
import { Clock, Database, MessageSquare } from 'lucide-react';

interface ChatSession {
  id: string;
  title: string;
  timestamp: Date;
  lastMessage: string;
}

interface ChatHistoryProps {
  onSelectSession?: (sessionId: string) => void;
  className?: string;
}

export function ChatHistory({ onSelectSession, className = '' }: ChatHistoryProps) {
  // For now, show recent conversations based on current session
  const chatHistory: ChatSession[] = [
    {
      id: 'current',
      title: 'Current Session',
      timestamp: new Date(),
      lastMessage: 'Active conversation...'
    }
  ];

  return (
    <div className={`bg-white rounded-lg border border-gray-200 h-full flex flex-col ${className}`}>
      <div className="p-4 border-b border-gray-100">
        <div className="flex items-center gap-2">
          <MessageSquare size={16} className="text-gray-600" />
          <h3 className="font-semibold text-gray-900">Chat History</h3>
        </div>
      </div>
      
      <div className="flex-1 overflow-y-auto">
        {chatHistory.length === 0 ? (
          <div className="p-4 text-center text-gray-500">
            <MessageSquare size={48} className="mx-auto mb-3 text-gray-300" />
            <p className="text-sm">No chat history yet</p>
            <p className="text-xs mt-1">Start a conversation to see your history here</p>
          </div>
        ) : (
          <div className="space-y-1 p-2">
            {chatHistory.map((session) => (
              <button
                key={session.id}
                onClick={() => onSelectSession?.(session.id)}
                className="w-full text-left p-3 rounded-lg hover:bg-gray-50 transition-colors border border-transparent hover:border-gray-200"
              >
                <div className="flex items-start gap-3">
                  <div className="flex-1 min-w-0">
                    <h4 className="text-sm font-medium text-gray-900 truncate mb-1">
                      {session.title}
                    </h4>
                    <p className="text-xs text-gray-600 line-clamp-2 mb-2">
                      {session.lastMessage}
                    </p>
                    <div className="flex items-center gap-2 text-xs text-gray-500">
                      <Clock size={12} />
                      <span>{formatRelativeTime(session.timestamp)}</span>
                    </div>
                  </div>
                </div>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function formatRelativeTime(date: Date): string {
  const now = new Date();
  const diffInMinutes = Math.floor((now.getTime() - date.getTime()) / (1000 * 60));
  
  if (diffInMinutes < 1) return 'Just now';
  if (diffInMinutes < 60) return `${diffInMinutes}m ago`;
  
  const diffInHours = Math.floor(diffInMinutes / 60);
  if (diffInHours < 24) return `${diffInHours}h ago`;
  
  const diffInDays = Math.floor(diffInHours / 24);
  if (diffInDays < 7) return `${diffInDays}d ago`;
  
  return date.toLocaleDateString();
}