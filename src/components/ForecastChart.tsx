import React from 'react';
import { 
  LineChart, 
  Line, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer, 
  Area, 
  ComposedChart,
  ReferenceLine 
} from 'recharts';
import { ForecastData } from '../types';

interface ForecastChartProps {
  data: ForecastData[];
  showActuals?: boolean;
  showConfidenceBands?: boolean;
  height?: number;
  className?: string;
}

export function ForecastChart({ 
  data, 
  showActuals = false, 
  showConfidenceBands = true,
  height = 300,
  className = '' 
}: ForecastChartProps) {
  // Generate mock historical data for context
  const historicalData = React.useMemo(() => {
    const historical = [];
    const startDate = new Date();
    startDate.setDate(startDate.getDate() - 30); // 30 days of history
    
    for (let i = 0; i < 30; i++) {
      const date = new Date(startDate);
      date.setDate(date.getDate() + i);
      
      // Generate realistic historical values
      const baseValue = data[0]?.predicted_units || 1000;
      const trend = -i * 0.01; // Slight downward trend in history
      const seasonality = Math.sin((i / 7) * Math.PI) * 0.15;
      const noise = (Math.random() - 0.5) * 0.3;
      
      const actual = Math.round(baseValue * (1 + trend + seasonality + noise));
      
      historical.push({
        date: date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
        fullDate: date.toISOString().split('T')[0],
        actual_units: actual,
        isHistorical: true
      });
    }
    
    return historical;
  }, [data]);

  const chartData = React.useMemo(() => {
    const forecastData = data.map(item => ({
      date: new Date(item.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
      fullDate: item.date,
      predicted_units: item.predicted_units,
      lower: item.confidence_interval?.lower || item.predicted_units * 0.9,
      upper: item.confidence_interval?.upper || item.predicted_units * 1.1,
      isHistorical: false
    }));

    return showActuals ? [...historicalData, ...forecastData] : forecastData;
  }, [data, historicalData, showActuals]);

  const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload;
      const isHistorical = data.isHistorical;
      
      return (
        <div className="bg-white p-4 border border-gray-200 rounded-lg shadow-lg">
          <p className="font-semibold text-gray-900 mb-2">{label}</p>
          
          {isHistorical ? (
            <div className="space-y-1">
              <p className="text-green-600 flex items-center gap-2">
                <span className="w-3 h-3 bg-green-600 rounded-full"></span>
                Actual: {data.actual_units?.toLocaleString()} units
              </p>
            </div>
          ) : (
            <div className="space-y-1">
              <p className="text-blue-600 flex items-center gap-2">
                <span className="w-3 h-3 bg-blue-600 rounded-full"></span>
                Forecast: {data.predicted_units?.toLocaleString()} units
              </p>
              {showConfidenceBands && (
                <p className="text-gray-500 text-sm">
                  Range: {data.lower?.toLocaleString()} - {data.upper?.toLocaleString()}
                </p>
              )}
            </div>
          )}
        </div>
      );
    }
    return null;
  };

  return (
    <div className={`bg-white rounded-lg border border-gray-200 p-4 ${className}`}>
      <div className={`h-${height}`} style={{ height: `${height}px` }}>
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={chartData} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
            <XAxis 
              dataKey="date" 
              axisLine={false}
              tickLine={false}
              tick={{ fontSize: 12, fill: '#6b7280' }}
            />
            <YAxis 
              axisLine={false}
              tickLine={false}
              tick={{ fontSize: 12, fill: '#6b7280' }}
              tickFormatter={(value) => `${(value / 1000).toFixed(1)}K`}
            />
            <Tooltip content={<CustomTooltip />} />
            
            {/* Reference line to separate historical from forecast */}
            {showActuals && (
              <ReferenceLine 
                x={historicalData[historicalData.length - 1]?.date} 
                stroke="#e5e7eb" 
                strokeDasharray="5 5"
              />
            )}
            
            {/* Confidence bands */}
            {showConfidenceBands && (
              <>
                <Area
                  dataKey="lower"
                  stroke="none"
                  fill="#dbeafe"
                  fillOpacity={0.3}
                />
                <Area
                  dataKey="upper"
                  stroke="none"
                  fill="#dbeafe"
                  fillOpacity={0.3}
                />
              </>
            )}
            
            {/* Historical actual line */}
            {showActuals && (
              <Line
                type="monotone"
                dataKey="actual_units"
                stroke="#10b981"
                strokeWidth={2}
                dot={{ fill: '#10b981', strokeWidth: 2, r: 3 }}
                connectNulls={false}
              />
            )}
            
            {/* Forecast line */}
            <Line
              type="monotone"
              dataKey="predicted_units"
              stroke="#2563eb"
              strokeWidth={3}
              dot={{ fill: '#2563eb', strokeWidth: 2, r: 4 }}
              activeDot={{ r: 6, stroke: '#2563eb', strokeWidth: 2 }}
              connectNulls={false}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      
      <div className="mt-4 text-xs text-gray-500 text-center">
        {showActuals && 'Historical data (green) vs '}Forecast with {Math.round((1 - 0.05) * 100)}% confidence intervals
      </div>
    </div>
  );
}