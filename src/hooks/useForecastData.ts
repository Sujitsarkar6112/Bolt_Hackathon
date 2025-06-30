import React, { useState, useEffect, useCallback } from 'react';
import { ModelType } from '../pages/ForecastExplorer';
import { ForecastData } from '../types';

interface ForecastResponse {
  sku: string;
  forecast_date: string;
  horizon_days: number;
  model_used: string;
  confidence_level: number;
  forecast: ForecastData[];
  metadata?: any;
}

interface UseForecastDataReturn {
  data: ForecastResponse | null;
  error: string | null;
  isLoading: boolean;
  mutate: () => void;
}

// Simple cache implementation
const cache = new Map<string, { data: ForecastResponse; timestamp: number }>();
const CACHE_DURATION = 5 * 60 * 1000; // 5 minutes

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8005';

export function useForecastData(
  sku: string, 
  horizon: number, 
  model: ModelType
): UseForecastDataReturn {
  const [data, setData] = useState<ForecastResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const cacheKey = `${sku}-${horizon}-${model}`;

  const fetchData = useCallback(async () => {
    // Check cache first
    const cached = cache.get(cacheKey);
    if (cached && Date.now() - cached.timestamp < CACHE_DURATION) {
      setData(cached.data);
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      // Make API call to backend forecast service
      const response = await fetch(`${API_BASE_URL}/forecast/${sku}?horizon=${horizon}&model=${model}`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        throw new Error(`Failed to fetch forecast data: ${response.statusText}`);
      }

      const forecastData = await response.json();
      
      // Cache the result
      cache.set(cacheKey, { data: forecastData, timestamp: Date.now() });
      
      setData(forecastData);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch forecast data');
      console.error('Forecast API error:', err);
    } finally {
      setIsLoading(false);
    }
  }, [sku, horizon, model, cacheKey]);

  const mutate = useCallback(() => {
    // Clear cache for this key and refetch
    cache.delete(cacheKey);
    fetchData();
  }, [cacheKey, fetchData]);

  useEffect(() => {
    if (sku && horizon > 0) {
      fetchData();
    }
  }, [fetchData, sku, horizon]);

  return { data, error, isLoading, mutate };
}