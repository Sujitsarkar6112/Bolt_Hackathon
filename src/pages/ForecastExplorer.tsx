import React, { useState, useMemo } from 'react';
import { TrendingUp, Calendar, Target, Activity, RefreshCw, AlertCircle } from 'lucide-react';
import { ForecastChart } from '../components/ForecastChart';
import { ModelSelector } from '../components/ModelSelector';
import { KPICard } from '../components/KPICard';
import { SKUSelector } from '../components/SKUSelector';
import { useForecastData } from '../hooks/useForecastData';
import { LoadingSpinner } from '../components/LoadingSpinner';
import styles from './ForecastExplorer.module.css';

export type ModelType = 'prophet' | 'tft' | 'ensemble';

export function ForecastExplorer() {
  const [selectedSKU, setSelectedSKU] = useState<string>('SKU-ABC');
  const [selectedModel, setSelectedModel] = useState<ModelType>('ensemble');
  const [horizon, setHorizon] = useState<number>(30);

  const { 
    data: forecastData, 
    error, 
    isLoading, 
    mutate: refreshData 
  } = useForecastData(selectedSKU, horizon, selectedModel);

  // Calculate KPIs from forecast data
  const kpis = useMemo(() => {
    if (!forecastData) return null;

    const totalPredicted = forecastData.forecast.reduce((sum, point) => sum + point.predicted_units, 0);
    const avgPredicted = totalPredicted / forecastData.forecast.length;
    const lastActual = 1250; // Mock last actual value
    const velocity = ((avgPredicted - lastActual) / lastActual) * 100;
    
    // Calculate MAPE (mock calculation)
    const mape = 8.5; // Mock MAPE value
    
    // Calculate confidence score
    const confidenceScore = forecastData.forecast.reduce((sum, point) => {
      const range = (point.confidence_interval?.upper || point.predicted_units) - 
                   (point.confidence_interval?.lower || point.predicted_units);
      const confidence = Math.max(0, 100 - (range / point.predicted_units) * 100);
      return sum + confidence;
    }, 0) / forecastData.forecast.length;

    return {
      mape,
      velocity,
      totalPredicted: Math.round(totalPredicted),
      confidenceScore: Math.round(confidenceScore)
    };
  }, [forecastData]);

  const handleRefresh = () => {
    refreshData();
  };

  return (
    <div className={styles.container}>
      {/* Header */}
      <div className={styles.header}>
        <div className={styles.headerContent}>
          <div className={styles.titleSection}>
            <TrendingUp size={32} className={styles.titleIcon} />
            <div>
              <h1 className={styles.title}>Forecast Explorer</h1>
              <p className={styles.subtitle}>
                Advanced demand forecasting with multiple model comparison
              </p>
            </div>
          </div>
          
          <button 
            onClick={handleRefresh}
            disabled={isLoading}
            className={styles.refreshButton}
          >
            <RefreshCw size={16} className={isLoading ? styles.spinning : ''} />
            Refresh
          </button>
        </div>
      </div>

      {/* Controls */}
      <div className={styles.controls}>
        <SKUSelector 
          value={selectedSKU} 
          onChange={setSelectedSKU}
          className={styles.skuSelector}
        />
        
        <ModelSelector 
          value={selectedModel} 
          onChange={setSelectedModel}
          className={styles.modelSelector}
        />
        
        <div className={styles.horizonSelector}>
          <label htmlFor="horizon" className={styles.horizonLabel}>
            <Calendar size={16} />
            Forecast Horizon
          </label>
          <select
            id="horizon"
            value={horizon}
            onChange={(e) => setHorizon(Number(e.target.value))}
            className={styles.horizonSelect}
          >
            <option value={7}>7 days</option>
            <option value={14}>14 days</option>
            <option value={30}>30 days</option>
            <option value={60}>60 days</option>
            <option value={90}>90 days</option>
            <option value={180}>180 days</option>
          </select>
        </div>
      </div>

      {/* KPI Cards */}
      {kpis && (
        <div className={styles.kpiGrid}>
          <KPICard
            title="MAPE"
            value={`${kpis.mape}%`}
            icon={Target}
            trend="down"
            trendValue="2.1%"
            description="Mean Absolute Percentage Error"
            className={styles.kpiCard}
          />
          
          <KPICard
            title="Sales Velocity"
            value={`${kpis.velocity > 0 ? '+' : ''}${kpis.velocity.toFixed(1)}%`}
            icon={Activity}
            trend={kpis.velocity > 0 ? "up" : "down"}
            trendValue={`${Math.abs(kpis.velocity).toFixed(1)}%`}
            description="Week-over-week growth rate"
            className={styles.kpiCard}
          />
          
          <KPICard
            title="Total Forecast"
            value={kpis.totalPredicted.toLocaleString()}
            icon={TrendingUp}
            trend="up"
            trendValue="12.5%"
            description={`${horizon}-day total predicted units`}
            className={styles.kpiCard}
          />
          
          <KPICard
            title="Confidence"
            value={`${kpis.confidenceScore}%`}
            icon={AlertCircle}
            trend="up"
            trendValue="5.2%"
            description="Model prediction confidence"
            className={styles.kpiCard}
          />
        </div>
      )}

      {/* Main Chart */}
      <div className={styles.chartSection}>
        {isLoading && (
          <div className={styles.loadingOverlay}>
            <LoadingSpinner size="large" />
            <p className={styles.loadingText}>
              Generating {selectedModel.toUpperCase()} forecast for {selectedSKU}...
            </p>
          </div>
        )}
        
        {error && (
          <div className={styles.errorState}>
            <AlertCircle size={48} className={styles.errorIcon} />
            <h3 className={styles.errorTitle}>Failed to Load Forecast</h3>
            <p className={styles.errorMessage}>{error}</p>
            <button onClick={handleRefresh} className={styles.retryButton}>
              Try Again
            </button>
          </div>
        )}
        
        {forecastData && !isLoading && (
          <div className={styles.chartContainer}>
            <div className={styles.chartHeader}>
              <h2 className={styles.chartTitle}>
                {selectedSKU} - {selectedModel.toUpperCase()} Model
              </h2>
              <div className={styles.chartMeta}>
                <span className={styles.chartMetaItem}>
                  Horizon: {horizon} days
                </span>
                <span className={styles.chartMetaItem}>
                  Updated: {new Date(forecastData.forecast_date).toLocaleString()}
                </span>
              </div>
            </div>
            
            <ForecastChart 
              data={forecastData.forecast}
              showActuals={true}
              showConfidenceBands={true}
              height={400}
              className={styles.chart}
            />
            
            <div className={styles.chartFooter}>
              <div className={styles.legend}>
                <div className={styles.legendItem}>
                  <div className={styles.legendColor} style={{ backgroundColor: '#2563eb' }}></div>
                  <span>Forecast</span>
                </div>
                <div className={styles.legendItem}>
                  <div className={styles.legendColor} style={{ backgroundColor: '#10b981' }}></div>
                  <span>Actual</span>
                </div>
                <div className={styles.legendItem}>
                  <div className={styles.legendColor} style={{ backgroundColor: '#dbeafe', opacity: 0.5 }}></div>
                  <span>Confidence Band</span>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}