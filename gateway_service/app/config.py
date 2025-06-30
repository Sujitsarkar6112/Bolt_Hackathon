from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional


class Settings(BaseSettings):
    """Gateway service configuration"""
    
    # Service Configuration
    service_name: str = "gateway_service"
    environment: str = "development"
    log_level: str = "INFO"
    
    # Backend Services
    backend_url: str = "http://localhost:8000"
    forecast_url: str = Field(default="http://localhost:8002", alias="FORECAST_URL")
    rag_url: str = Field(default="http://localhost:8003", alias="RAG_URL")
    filter_url: str = Field(default="http://localhost:8001", alias="FILTER_URL")
    
    # WebSocket Configuration
    websocket_ping_interval: int = 20
    websocket_ping_timeout: int = 10
    max_connections: int = 1000
    
    # SSE Configuration
    sse_keepalive_interval: int = 30
    sse_retry_interval: int = 3000
    
    # HTTP Client Configuration
    http_timeout: int = 30
    max_retries: int = 3
    
    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()