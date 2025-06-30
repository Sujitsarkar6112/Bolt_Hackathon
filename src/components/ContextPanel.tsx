import React from 'react';
import { FileText, TrendingUp, Shield, ExternalLink } from 'lucide-react';
import { Message } from '../types';
import { ForecastChart } from './ForecastChart';

interface ContextPanelProps {
  lastMessage?: Message;
}

export function ContextPanel({ lastMessage }: ContextPanelProps) {
  const metadata = lastMessage?.metadata;
  
  if (!metadata) {
    return (
      <div className="h-full bg-gray-50 border-l border-gray-200 flex items-center justify-center">
        <div className="text-center text-gray-500">
          <TrendingUp size={48} className="mx-auto mb-3 opacity-50" />
          <p className="text-sm">Contextual information will appear here</p>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full bg-gray-50 border-l border-gray-200 flex flex-col">
      <div className="p-4 border-b border-gray-200 bg-white">
        <h2 className="text-lg font-semibold text-gray-900">Context</h2>
      </div>
      
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* Forecast Chart */}
        {metadata.forecast && (
          <ForecastChart data={metadata.forecast} />
        )}
        
        {/* Document Sources */}
        {metadata.sources && metadata.sources.length > 0 && (
          <div className="bg-white rounded-lg border border-gray-200 p-4">
            <div className="flex items-center gap-2 mb-3">
              <FileText size={16} className="text-emerald-600" />
              <h3 className="text-sm font-semibold text-gray-900">Sources</h3>
            </div>
            <div className="space-y-3">
              {metadata.sources.map((source, index) => (
                <div key={index} className="border-l-4 border-emerald-200 pl-3">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-sm font-medium text-gray-900">
                      {source.document}
                    </span>
                    <div className="flex items-center gap-1 text-xs text-gray-500">
                      <span>{Math.round(source.relevance_score * 100)}%</span>
                      <ExternalLink size={12} />
                    </div>
                  </div>
                  {source.page && (
                    <p className="text-xs text-gray-500 mb-2">Page {source.page}</p>
                  )}
                  <p className="text-sm text-gray-600 italic">
                    "{source.excerpt}"
                  </p>
                </div>
              ))}
            </div>
          </div>
        )}
        
        {/* Entity Validation */}
        {metadata.entities && metadata.entities.length > 0 && (
          <div className="bg-white rounded-lg border border-gray-200 p-4">
            <div className="flex items-center gap-2 mb-3">
              <Shield size={16} className="text-amber-600" />
              <h3 className="text-sm font-semibold text-gray-900">Validated Entities</h3>
            </div>
            <div className="space-y-2">
              {metadata.entities.map((entity, index) => (
                <div key={index} className="flex items-center justify-between">
                  <span className="text-sm text-gray-900">{entity}</span>
                  <span className="inline-flex items-center px-2 py-1 rounded-full text-xs bg-green-100 text-green-800">
                    ✓ Verified
                  </span>
                </div>
              ))}
            </div>
            <p className="text-xs text-gray-500 mt-3">
              All entities validated against enterprise product catalog
            </p>
          </div>
        )}
        
        {/* Model Information */}
        {metadata.forecast && (
          <div className="bg-white rounded-lg border border-gray-200 p-4">
            <h3 className="text-sm font-semibold text-gray-900 mb-3">Model Details</h3>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-gray-600">Algorithm:</span>
                <span className="text-gray-900">Hybrid Prophet-TFT</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">Confidence:</span>
                <span className="text-gray-900">95% Interval</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">Last Updated:</span>
                <span className="text-gray-900">2 hours ago</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">Data Points:</span>
                <span className="text-gray-900">18,247 records</span>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}