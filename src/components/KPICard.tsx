import React from 'react';
import { DivideIcon as LucideIcon, TrendingUp, TrendingDown } from 'lucide-react';

interface KPICardProps {
  title: string;
  value: string;
  icon: LucideIcon;
  trend?: 'up' | 'down';
  trendValue?: string;
  description?: string;
  className?: string;
}

export function KPICard({ 
  title, 
  value, 
  icon: Icon, 
  trend, 
  trendValue, 
  description,
  className = '' 
}: KPICardProps) {
  return (
    <div className={`p-6 ${className}`}>
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className="p-3 bg-blue-50 rounded-lg">
            <Icon size={24} className="text-blue-600" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-gray-700">{title}</h3>
            {description && (
              <p className="text-xs text-gray-500 mt-1">{description}</p>
            )}
          </div>
        </div>
        
        {trend && trendValue && (
          <div className={`flex items-center gap-1 text-sm ${
            trend === 'up' ? 'text-green-600' : 'text-red-600'
          }`}>
            {trend === 'up' ? (
              <TrendingUp size={16} />
            ) : (
              <TrendingDown size={16} />
            )}
            <span className="font-medium">{trendValue}</span>
          </div>
        )}
      </div>
      
      <div className="text-3xl font-bold text-gray-900 mb-2">
        {value}
      </div>
      
      {trend && (
        <div className="text-sm text-gray-600">
          {trend === 'up' ? 'Increased' : 'Decreased'} from last period
        </div>
      )}
    </div>
  );
}