import React from 'react';
import { Bot, User } from 'lucide-react';
import { Message } from '../types';
import { CitationTooltip } from './CitationTooltip';

interface MessageBubbleProps {
  message: Message;
}

export function MessageBubble({ message }: MessageBubbleProps) {
  const isBot = message.sender === 'bot';
  
  // Parse citations in bot messages
  const renderContentWithCitations = (content: string) => {
    if (!isBot || !message.metadata?.sources) {
      return content;
    }

    // Replace citation markers [1], [2], etc. with tooltips
    let processedContent = content;
    const citationRegex = /\[(\d+)\]/g;
    const citations: React.ReactNode[] = [];
    let lastIndex = 0;

    let match;
    while ((match = citationRegex.exec(content)) !== null) {
      const citationNumber = parseInt(match[1]) - 1;
      const source = message.metadata.sources[citationNumber];
      
      if (source) {
        // Add text before citation
        if (match.index > lastIndex) {
          citations.push(content.slice(lastIndex, match.index));
        }
        
        // Add citation with tooltip
        citations.push(
          <CitationTooltip key={`citation-${citationNumber}`} source={source}>
            {match[0]}
          </CitationTooltip>
        );
        
        lastIndex = match.index + match[0].length;
      }
    }
    
    // Add remaining text
    if (lastIndex < content.length) {
      citations.push(content.slice(lastIndex));
    }
    
    return citations.length > 0 ? citations : content;
  };
  
  return (
    <div className={`flex gap-3 ${isBot ? 'justify-start' : 'justify-end'} mb-4`}>
      {isBot && (
        <div className="flex-shrink-0 w-8 h-8 bg-blue-600 rounded-full flex items-center justify-center">
          <Bot size={16} className="text-white" />
        </div>
      )}
      
      <div className={`max-w-3xl ${isBot ? 'bg-gray-50' : 'bg-blue-600 text-white'} rounded-lg p-4 shadow-sm`}>
        <div className={`text-sm ${isBot ? 'text-gray-900' : 'text-white'} whitespace-pre-wrap`}>
          {renderContentWithCitations(message.content)}
        </div>
        
        {message.metadata?.entities && message.metadata.entities.length > 0 && (
          <div className="mt-3 pt-3 border-t border-gray-200">
            <div className="text-xs text-gray-500 mb-1">Entities Referenced:</div>
            <div className="flex flex-wrap gap-1">
              {message.metadata.entities.map((entity, index) => (
                <span
                  key={index}
                  className="inline-block bg-blue-100 text-blue-800 text-xs px-2 py-1 rounded-md"
                >
                  {entity}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>
      
      {!isBot && (
        <div className="flex-shrink-0 w-8 h-8 bg-gray-600 rounded-full flex items-center justify-center">
          <User size={16} className="text-white" />
        </div>
      )}
    </div>
  );
}