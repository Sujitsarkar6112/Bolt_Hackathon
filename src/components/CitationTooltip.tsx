import React, { useState } from 'react';
import { ExternalLink, FileText } from 'lucide-react';
import { DocumentSource } from '../types';

interface CitationTooltipProps {
  source: DocumentSource;
  children: React.ReactNode;
}

export function CitationTooltip({ source, children }: CitationTooltipProps) {
  const [isVisible, setIsVisible] = useState(false);

  return (
    <div className="relative inline-block">
      <span
        className="cursor-help text-blue-600 hover:text-blue-800 underline decoration-dotted"
        onMouseEnter={() => setIsVisible(true)}
        onMouseLeave={() => setIsVisible(false)}
      >
        {children}
      </span>
      
      {isVisible && (
        <div className="absolute bottom-full left-1/2 transform -translate-x-1/2 mb-2 z-50">
          <div className="bg-white border border-gray-200 rounded-lg shadow-lg p-4 max-w-sm">
            <div className="flex items-center gap-2 mb-2">
              <FileText size={16} className="text-emerald-600" />
              <span className="font-semibold text-gray-900 text-sm">
                {source.document}
              </span>
              <ExternalLink size={12} className="text-gray-400" />
            </div>
            
            {source.page && (
              <p className="text-xs text-gray-500 mb-2">Page {source.page}</p>
            )}
            
            <p className="text-sm text-gray-600 italic mb-2">
              "{source.excerpt}"
            </p>
            
            <div className="flex justify-between items-center text-xs text-gray-500">
              <span>Relevance: {Math.round(source.relevance_score * 100)}%</span>
            </div>
            
            {/* Tooltip arrow */}
            <div className="absolute top-full left-1/2 transform -translate-x-1/2">
              <div className="border-4 border-transparent border-t-white"></div>
              <div className="border-4 border-transparent border-t-gray-200 -mt-1"></div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}