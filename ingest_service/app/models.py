from pydantic import BaseModel, Field, validator
from datetime import datetime
from typing import Optional
import re


class SalesEventModel(BaseModel):
    """Pydantic model for sales event validation"""
    sku: str = Field(..., min_length=1, max_length=100, description="Product SKU")
    qty: int = Field(..., gt=0, description="Quantity sold")
    price: float = Field(..., gt=0, description="Unit price")
    ts: str = Field(..., description="ISO8601 timestamp")
    event_id: Optional[str] = Field(None, description="Unique event identifier")
    
    @validator('sku')
    def validate_sku(cls, v):
        """Validate SKU format"""
        if not re.match(r'^[A-Z0-9\-_]+$', v.upper()):
            raise ValueError('SKU must contain only alphanumeric characters, hyphens, and underscores')
        return v.upper()
    
    @validator('ts')
    def validate_timestamp(cls, v):
        """Validate ISO8601 timestamp format"""
        try:
            datetime.fromisoformat(v.replace('Z', '+00:00'))
        except ValueError:
            raise ValueError('Timestamp must be in ISO8601 format')
        return v
    
    @validator('price')
    def validate_price(cls, v):
        """Validate price precision"""
        if round(v, 2) != v:
            raise ValueError('Price must have at most 2 decimal places')
        return v


class HealthResponse(BaseModel):
    """Health check response model"""
    status: str
    timestamp: str
    kafka_connected: bool
    mongodb_connected: bool
    processed_events: int


class MetricsResponse(BaseModel):
    """Metrics response model"""
    events_processed_total: int
    events_per_second: float
    kafka_lag_ms: float
    mongodb_writes_total: int
    errors_total: int
    uptime_seconds: float