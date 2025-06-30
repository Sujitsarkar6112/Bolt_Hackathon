import React from 'react';
import { Brain, Zap, Layers } from 'lucide-react';
import { ModelType } from '../pages/ForecastExplorer';

interface ModelSelectorProps {
  value: ModelType;
  onChange: (model: ModelType) => void;
  className?: string;
}

const modelConfig = {
  prophet: {
    name: 'Prophet',
    icon: Brain,
    description: 'Facebook Prophet - Best for seasonal patterns',
    color: '#10b981',
    features: ['Seasonal decomposition', 'Holiday effects', 'Trend analysis']
  },
  tft: {
    name: 'TFT',
    icon: Zap,
    description: 'Temporal Fusion Transformer - Advanced ML',
    color: '#f59e0b',
    features: ['Multi-variate inputs', 'Attention mechanism', 'Long-term forecasts']
  },
  ensemble: {
    name: 'Ensemble',
    icon: Layers,
    description: 'Hybrid approach combining both models',
    color: '#2563eb',
    features: ['Best of both models', 'Adaptive selection', 'Highest accuracy']
  }
};

export function ModelSelector({ value, onChange, className = '' }: ModelSelectorProps) {
  return (
    <div className={className}>
      <h3 className="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2">
        <Brain size={16} />
        Forecasting Model
      </h3>
      
      <div className="space-y-3">
        {(Object.keys(modelConfig) as ModelType[]).map((modelKey) => {
          const model = modelConfig[modelKey];
          const Icon = model.icon;
          const isSelected = value === modelKey;
          
          return (
            <button
              key={modelKey}
              onClick={() => onChange(modelKey)}
              className={`w-full text-left p-3 rounded-lg border-2 transition-all ${
                isSelected
                  ? 'border-blue-500 bg-blue-50'
                  : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'
              }`}
            >
              <div className="flex items-start gap-3">
                <div 
                  className="p-2 rounded-lg"
                  style={{ 
                    backgroundColor: isSelected ? model.color : '#f3f4f6',
                    color: isSelected ? 'white' : model.color
                  }}
                >
                  <Icon size={16} />
                </div>
                
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="font-semibold text-gray-900">{model.name}</span>
                    {isSelected && (
                      <span className="text-xs bg-blue-100 text-blue-800 px-2 py-1 rounded-full">
                        Active
                      </span>
                    )}
                  </div>
                  
                  <p className="text-sm text-gray-600 mb-2">
                    {model.description}
                  </p>
                  
                  <div className="flex flex-wrap gap-1">
                    {model.features.map((feature, index) => (
                      <span
                        key={index}
                        className="text-xs bg-gray-100 text-gray-700 px-2 py-1 rounded"
                      >
                        {feature}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}