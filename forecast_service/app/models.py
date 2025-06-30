from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Literal
from datetime import datetime


class ForecastRequest(BaseModel):
    """Request model for forecast generation"""
    sku: str = Field(..., description="Product SKU")
    horizon: int = Field(default=30, ge=1, le=180, description="Forecast horizon in days")
    confidence_level: float = Field(default=0.8, ge=0.5, le=0.99, description="Confidence level")


class ForecastPoint(BaseModel):
    """Single forecast point"""
    date: str = Field(..., description="Forecast date (ISO format)")
    median: float = Field(..., description="Median forecast value")
    p10: float = Field(..., description="10th percentile (lower bound)")
    p90: float = Field(..., description="90th percentile (upper bound)")


class ForecastResponse(BaseModel):
    """Response model for forecast"""
    sku: str = Field(..., description="Product SKU")
    forecast_date: str = Field(..., description="When forecast was generated")
    horizon_days: int = Field(..., description="Forecast horizon in days")
    model_used: Literal["prophet", "tft", "ensemble"] = Field(..., description="Model used for forecast")
    confidence_level: float = Field(..., description="Confidence level used")
    forecast: List[ForecastPoint] = Field(..., description="Forecast points")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class HealthResponse(BaseModel):
    """Health check response"""
    status: Literal["healthy", "degraded", "unhealthy"]
    timestamp: str
    database_connected: bool
    models_loaded: bool
    prophet_available: bool
    tft_available: bool


class ModelMetadata(BaseModel):
    """Model metadata"""
    model_name: str
    version: str
    trained_at: Optional[str] = None
    training_samples: Optional[int] = None
    validation_mae: Optional[float] = None
    validation_mape: Optional[float] = None
    mlflow_run_id: Optional[str] = None


class TrainingData(BaseModel):
    """Training data structure"""
    sku: str
    timestamp: datetime
    units_sold: int
    price: float
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }