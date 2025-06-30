import time
from prometheus_client import Counter, Histogram, Gauge, start_http_server
from typing import Dict, Any
import structlog

logger = structlog.get_logger()

# Prometheus metrics
events_processed_total = Counter(
    'sales_events_processed_total',
    'Total number of sales events processed',
    ['status']  # success, error, duplicate
)

events_per_second = Gauge(
    'sales_events_per_second',
    'Current rate of events processed per second'
)

kafka_lag_ms = Gauge(
    'kafka_consumer_lag_milliseconds',
    'Kafka consumer lag in milliseconds'
)

mongodb_writes_total = Counter(
    'mongodb_writes_total',
    'Total number of MongoDB write operations',
    ['status']  # success, error
)

processing_duration = Histogram(
    'event_processing_duration_seconds',
    'Time spent processing individual events',
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0]
)

service_uptime = Gauge(
    'service_uptime_seconds',
    'Service uptime in seconds'
)


class MetricsCollector:
    """Centralized metrics collection and reporting"""
    
    def __init__(self):
        self.start_time = time.time()
        self.events_count = 0
        self.last_events_time = time.time()
        self.last_events_count = 0
        
    def start_metrics_server(self, port: int = 8001) -> None:
        """Start Prometheus metrics HTTP server"""
        try:
            start_http_server(port)
            logger.info("Metrics server started", port=port)
        except Exception as e:
            logger.error("Failed to start metrics server", error=str(e))
    
    def record_event_processed(self, status: str = 'success') -> None:
        """Record a processed event"""
        events_processed_total.labels(status=status).inc()
        self.events_count += 1
        
        # Update events per second every 10 seconds
        current_time = time.time()
        if current_time - self.last_events_time >= 10:
            time_diff = current_time - self.last_events_time
            events_diff = self.events_count - self.last_events_count
            rate = events_diff / time_diff if time_diff > 0 else 0
            
            events_per_second.set(rate)
            self.last_events_time = current_time
            self.last_events_count = self.events_count
    
    def record_mongodb_write(self, status: str = 'success') -> None:
        """Record a MongoDB write operation"""
        mongodb_writes_total.labels(status=status).inc()
    
    def update_kafka_lag(self, lag_ms: float) -> None:
        """Update Kafka consumer lag metric"""
        kafka_lag_ms.set(lag_ms)
    
    def update_uptime(self) -> None:
        """Update service uptime metric"""
        uptime = time.time() - self.start_time
        service_uptime.set(uptime)
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get current metrics summary"""
        return {
            "events_processed_total": self.events_count,
            "events_per_second": events_per_second._value._value,
            "kafka_lag_ms": kafka_lag_ms._value._value,
            "mongodb_writes_total": sum(mongodb_writes_total._value.values()),
            "errors_total": events_processed_total.labels(status='error')._value._value,
            "uptime_seconds": time.time() - self.start_time
        }


# Global metrics collector
metrics = MetricsCollector()