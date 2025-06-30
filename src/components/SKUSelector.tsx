import React, { useState } from 'react';
import { Package, Search, TrendingUp, TrendingDown } from 'lucide-react';

interface SKUSelectorProps {
  value: string;
  onChange: (sku: string) => void;
  className?: string;
}

const mockSKUs = [
  {
    sku: 'SKU-ABC',
    name: 'Premium Widget Pro',
    category: 'Electronics',
    trend: 'up',
    trendValue: '+15.2%',
    lastSales: 1250
  },
  {
    sku: 'SKU-XYZ',
    name: 'Standard Widget',
    category: 'Electronics',
    trend: 'down',
    trendValue: '-8.1%',
    lastSales: 890
  },
  {
    sku: 'SKU-ABC-V2',
    name: 'Premium Widget Pro V2',
    category: 'Electronics',
    trend: 'up',
    trendValue: '+32.5%',
    lastSales: 2100
  },
  {
    sku: 'Product-X',
    name: 'Deluxe Gadget',
    category: 'Accessories',
    trend: 'up',
    trendValue: '+5.7%',
    lastSales: 650
  },
  {
    sku: 'Product-Y',
    name: 'Basic Gadget',
    category: 'Accessories',
    trend: 'down',
    trendValue: '-2.3%',
    lastSales: 420
  }
];

export function SKUSelector({ value, onChange, className = '' }: SKUSelectorProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');

  const selectedSKU = mockSKUs.find(sku => sku.sku === value);
  
  const filteredSKUs = mockSKUs.filter(sku =>
    sku.sku.toLowerCase().includes(searchTerm.toLowerCase()) ||
    sku.name.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const handleSelect = (sku: string) => {
    onChange(sku);
    setIsOpen(false);
    setSearchTerm('');
  };

  return (
    <div className={`relative ${className}`}>
      <h3 className="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2">
        <Package size={16} />
        Product SKU
      </h3>
      
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full p-3 text-left bg-white border border-gray-300 rounded-lg hover:border-gray-400 transition-colors"
      >
        {selectedSKU ? (
          <div className="flex items-center justify-between">
            <div>
              <div className="font-semibold text-gray-900">{selectedSKU.sku}</div>
              <div className="text-sm text-gray-600">{selectedSKU.name}</div>
            </div>
            <div className="flex items-center gap-1 text-sm">
              {selectedSKU.trend === 'up' ? (
                <TrendingUp size={14} className="text-green-600" />
              ) : (
                <TrendingDown size={14} className="text-red-600" />
              )}
              <span className={selectedSKU.trend === 'up' ? 'text-green-600' : 'text-red-600'}>
                {selectedSKU.trendValue}
              </span>
            </div>
          </div>
        ) : (
          <span className="text-gray-500">Select a SKU...</span>
        )}
      </button>

      {isOpen && (
        <div className="absolute top-full left-0 right-0 mt-1 bg-white border border-gray-300 rounded-lg shadow-lg z-50 max-h-80 overflow-hidden">
          <div className="p-3 border-b border-gray-200">
            <div className="relative">
              <Search size={16} className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400" />
              <input
                type="text"
                placeholder="Search SKUs..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full pl-10 pr-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>
          </div>
          
          <div className="max-h-60 overflow-y-auto">
            {filteredSKUs.map((sku) => (
              <button
                key={sku.sku}
                onClick={() => handleSelect(sku.sku)}
                className={`w-full p-3 text-left hover:bg-gray-50 transition-colors ${
                  sku.sku === value ? 'bg-blue-50 border-r-2 border-blue-500' : ''
                }`}
              >
                <div className="flex items-center justify-between">
                  <div>
                    <div className="font-semibold text-gray-900">{sku.sku}</div>
                    <div className="text-sm text-gray-600">{sku.name}</div>
                    <div className="text-xs text-gray-500">{sku.category}</div>
                  </div>
                  <div className="text-right">
                    <div className="flex items-center gap-1 text-sm mb-1">
                      {sku.trend === 'up' ? (
                        <TrendingUp size={14} className="text-green-600" />
                      ) : (
                        <TrendingDown size={14} className="text-red-600" />
                      )}
                      <span className={sku.trend === 'up' ? 'text-green-600' : 'text-red-600'}>
                        {sku.trendValue}
                      </span>
                    </div>
                    <div className="text-xs text-gray-500">
                      Last: {sku.lastSales.toLocaleString()}
                    </div>
                  </div>
                </div>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}