from fastapi import FastAPI, HTTPException, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Literal
import asyncio
from datetime import datetime, timedelta
import logging
import os
from contextlib import asynccontextmanager

from .config import settings
from .models import ForecastRequest, ForecastResponse, HealthResponse
from .services.forecast_ensemble import ForecastEnsemble
from .services.data_loader import DataLoader
from .services.mlflow_client import MLflowClient
from .utils.logging_config import setup_logging
# Using SQLite instead of MongoDB - no centralized connection needed

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)

# Global services
forecast_ensemble = ForecastEnsemble()
data_loader = DataLoader()
mlflow_client = MLflowClient()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management with SQLite database"""
    logger.info("Starting forecast service")
    
    # Initialize services
    await data_loader.connect()
    await mlflow_client.initialize()
    
    # Load existing models if available
    await forecast_ensemble.load_models()
    
    yield
    
    # Cleanup
    logger.info("Shutting down forecast service")
    await data_loader.disconnect()


# Create FastAPI application
app = FastAPI(
    title="Forecast Service",
    description="Production MLOps service for demand forecasting using Prophet and TFT",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint with SQLite database status"""
    try:
        # Check database connection
        db_healthy = await data_loader.is_connected()
        
        # Check model availability
        models_loaded = forecast_ensemble.models_loaded()
        
        status = "healthy" if db_healthy else "degraded"
        
        return HealthResponse(
            status=status,
            timestamp=datetime.utcnow().isoformat(),
            database_connected=db_healthy,
            models_loaded=models_loaded,
            prophet_available=forecast_ensemble.prophet_model is not None,
            tft_available=forecast_ensemble.tft_model is not None
        )
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        raise HTTPException(status_code=503, detail="Service unhealthy")


@app.get("/forecast/{sku}", response_model=ForecastResponse)
async def get_forecast(
    sku: str,
    horizon: int = Query(default=30, ge=1, le=180, description="Forecast horizon in days"),
    confidence_level: float = Query(default=0.8, ge=0.5, le=0.99, description="Confidence level for intervals")
):
    """Get forecast for a specific SKU"""
    try:
        logger.info(f"Generating forecast for SKU: {sku}, horizon: {horizon} days")
        
        # Validate SKU exists in data
        if not await data_loader.sku_exists(sku):
            raise HTTPException(status_code=404, detail=f"SKU {sku} not found in historical data")
        
        # Generate forecast using ensemble
        forecast_result = await forecast_ensemble.predict(
            sku=sku,
            horizon=horizon,
            confidence_level=confidence_level
        )
        
        return forecast_result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Forecast generation failed for SKU {sku}: {str(e)}")
        raise HTTPException(status_code=500, detail="Forecast generation failed")


@app.post("/retrain")
async def trigger_retrain(background_tasks: BackgroundTasks):
    """Trigger model retraining"""
    try:
        background_tasks.add_task(forecast_ensemble.retrain_models)
        return {"message": "Model retraining initiated", "timestamp": datetime.utcnow().isoformat()}
    except Exception as e:
        logger.error(f"Failed to trigger retraining: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to trigger retraining")


@app.get("/models/status")
async def get_model_status():
    """Get current model status and metadata"""
    try:
        status = await forecast_ensemble.get_model_status()
        return status
    except Exception as e:
        logger.error(f"Failed to get model status: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get model status")


@app.get("/skus")
async def list_available_skus():
    """List all available SKUs in the database"""
    try:
        skus = await data_loader.get_available_skus()
        return {"skus": skus, "count": len(skus)}
    except Exception as e:
        logger.error(f"Failed to list SKUs: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to list SKUs")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8002,
        log_level=settings.log_level.lower(),
        reload=settings.environment == "development"
    )