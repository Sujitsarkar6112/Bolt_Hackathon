from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application configuration"""
    
    # Service Configuration
    service_name: str = "forecast_service"
    environment: str = "development"
    log_level: str = "INFO"
    
    # MongoDB Configuration
    mongodb_url: str = "mongodb://localhost:27017"
    mongodb_database: str = "sales_db"
    mongodb_collection: str = "raw_sales"
    
    # MLflow Configuration
    mlflow_tracking_uri: str = "http://localhost:5000"
    mlflow_experiment_name: str = "demand_forecasting"
    
    # Model Configuration
    prophet_seasonality_mode: str = "multiplicative"
    prophet_yearly_seasonality: bool = True
    prophet_weekly_seasonality: bool = True
    prophet_daily_seasonality: bool = False
    
    tft_max_epochs: int = 100
    tft_batch_size: int = 64
    tft_learning_rate: float = 0.03
    tft_hidden_size: int = 16
    tft_attention_head_size: int = 4
    tft_dropout: float = 0.1
    
    # Training Configuration
    min_training_samples: int = 90  # Minimum days of data required
    validation_split: float = 0.2
    test_split: float = 0.1
    
    # Ensemble Configuration
    short_term_threshold: int = 30  # Days - use Prophet for <= 30 days
    long_term_threshold: int = 180  # Days - maximum forecast horizon
    
    # Cron Configuration
    retrain_cron: str = "0 2 * * *"  # Daily at 2 AM
    
    # GPU Configuration
    use_gpu: bool = False
    gpu_device: int = 0
    
    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"  # Allow extra environment variables from other services


settings = Settings()