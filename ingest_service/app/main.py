import asyncio
import signal
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import structlog
import sys
from .config import settings
from .models import HealthResponse, MetricsResponse
from .processor import processor
from .database import mongodb_client
from .kafka_consumer import kafka_consumer
from .metrics import metrics

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management"""
    logger.info("Starting ingest service", service=settings.service_name)
    
    # Start background processor
    processor_task = asyncio.create_task(processor.start())
    
    # Setup graceful shutdown
    def signal_handler(signum, frame):
        logger.info("Received shutdown signal", signal=signum)
        processor_task.cancel()
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        yield
    finally:
        logger.info("Shutting down ingest service")
        processor_task.cancel()
        try:
            await processor_task
        except asyncio.CancelledError:
            pass
        await processor.stop()


# Create FastAPI application
app = FastAPI(
    title="Sales Ingest Service",
    description="Production-grade microservice for ingesting sales events from Kafka to MongoDB",
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
    """Health check endpoint"""
    try:
        kafka_connected = await kafka_consumer.is_connected()
        mongodb_connected = await mongodb_client.is_connected()
        
        status = "healthy" if kafka_connected and mongodb_connected else "degraded"
        
        return HealthResponse(
            status=status,
            timestamp=str(asyncio.get_event_loop().time()),
            kafka_connected=kafka_connected,
            mongodb_connected=mongodb_connected,
            processed_events=metrics.events_count
        )
    except Exception as e:
        logger.error("Health check failed", error=str(e))
        raise HTTPException(status_code=503, detail="Service unhealthy")


@app.get("/metrics", response_model=MetricsResponse)
async def get_metrics():
    """Prometheus-style metrics endpoint"""
    try:
        metrics_data = metrics.get_metrics_summary()
        return MetricsResponse(**metrics_data)
    except Exception as e:
        logger.error("Failed to get metrics", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve metrics")


@app.get("/stats")
async def get_stats():
    """Get detailed service statistics"""
    try:
        mongo_stats = await mongodb_client.get_collection_stats()
        metrics_data = metrics.get_metrics_summary()
        
        return {
            "service": settings.service_name,
            "kafka": {
                "topic": settings.kafka_topic,
                "group_id": settings.kafka_group_id,
                "connected": await kafka_consumer.is_connected(),
                "lag_ms": kafka_consumer.get_lag_ms()
            },
            "mongodb": {
                "database": settings.mongodb_database,
                "collection": settings.mongodb_collection,
                "connected": await mongodb_client.is_connected(),
                **mongo_stats
            },
            "metrics": metrics_data
        }
    except Exception as e:
        logger.error("Failed to get stats", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve statistics")


@app.post("/shutdown")
async def shutdown():
    """Graceful shutdown endpoint"""
    logger.info("Shutdown requested via API")
    await processor.stop()
    return {"message": "Service shutdown initiated"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        log_level=settings.log_level.lower(),
        reload=False
    )