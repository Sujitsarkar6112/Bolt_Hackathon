from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    """Application configuration"""
    
    # Kafka Configuration
    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_topic: str = "sales_txn"
    kafka_group_id: str = "ingest_service"
    kafka_auto_offset_reset: str = "latest"
    kafka_enable_auto_commit: bool = True
    kafka_max_poll_records: int = 500
    
    # MongoDB Configuration
    mongodb_url: str = "mongodb://localhost:27017"
    mongodb_database: str = "sales_db"
    mongodb_collection: str = "raw_sales"
    
    # Service Configuration
    service_name: str = "ingest_service"
    log_level: str = "INFO"
    metrics_port: int = 8001
    health_check_interval: int = 30
    
    # Performance Configuration
    batch_size: int = 100
    flush_interval: float = 5.0
    max_retries: int = 3
    retry_backoff: float = 1.0
    
    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()