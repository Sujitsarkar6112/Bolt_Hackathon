import pytest
from httpx import AsyncClient
from app.main import app
from unittest.mock import patch, AsyncMock, MagicMock


class TestAPI:
    """Test cases for FastAPI endpoints"""
    
    @pytest.fixture
    async def client(self):
        """Create test client"""
        async with AsyncClient(app=app, base_url="http://test") as ac:
            yield ac
    
    @pytest.fixture
    def mock_services(self):
        """Mock external services"""
        with patch('app.main.kafka_consumer') as mock_kafka, \
             patch('app.main.mongodb_client') as mock_mongo, \
             patch('app.main.metrics') as mock_metrics:
            
            mock_kafka.is_connected = AsyncMock(return_value=True)
            mock_mongo.is_connected = AsyncMock(return_value=True)
            mock_mongo.get_collection_stats = AsyncMock(return_value={"document_count": 100})
            
            mock_metrics.events_count = 50
            mock_metrics.get_metrics_summary = MagicMock(return_value={
                "events_processed_total": 50,
                "events_per_second": 5.0,
                "kafka_lag_ms": 100.0,
                "mongodb_writes_total": 10,
                "errors_total": 0,
                "uptime_seconds": 3600.0
            })
            
            yield {
                'kafka': mock_kafka,
                'mongodb': mock_mongo,
                'metrics': mock_metrics
            }
    
    async def test_health_check_healthy(self, client, mock_services):
        """Test health check when all services are healthy"""
        response = await client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "healthy"
        assert data["kafka_connected"] is True
        assert data["mongodb_connected"] is True
        assert data["processed_events"] == 50
        assert "timestamp" in data
    
    async def test_health_check_degraded(self, client, mock_services):
        """Test health check when services are degraded"""
        # Make Kafka appear disconnected
        mock_services['kafka'].is_connected.return_value = False
        
        response = await client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "degraded"
        assert data["kafka_connected"] is False
        assert data["mongodb_connected"] is True
    
    async def test_health_check_error(self, client, mock_services):
        """Test health check when there's an error"""
        # Make health check raise an exception
        mock_services['kafka'].is_connected.side_effect = Exception("Connection error")
        
        response = await client.get("/health")
        
        assert response.status_code == 503
        assert "Service unhealthy" in response.json()["detail"]
    
    async def test_metrics_endpoint(self, client, mock_services):
        """Test metrics endpoint"""
        response = await client.get("/metrics")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["events_processed_total"] == 50
        assert data["events_per_second"] == 5.0
        assert data["kafka_lag_ms"] == 100.0
        assert data["mongodb_writes_total"] == 10
        assert data["errors_total"] == 0
        assert data["uptime_seconds"] == 3600.0
    
    async def test_metrics_endpoint_error(self, client, mock_services):
        """Test metrics endpoint when there's an error"""
        mock_services['metrics'].get_metrics_summary.side_effect = Exception("Metrics error")
        
        response = await client.get("/metrics")
        
        assert response.status_code == 500
        assert "Failed to retrieve metrics" in response.json()["detail"]
    
    async def test_stats_endpoint(self, client, mock_services):
        """Test stats endpoint"""
        mock_services['kafka'].get_lag_ms = MagicMock(return_value=150.0)
        
        response = await client.get("/stats")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["service"] == "ingest_service"
        assert "kafka" in data
        assert "mongodb" in data
        assert "metrics" in data
        
        # Check Kafka stats
        kafka_stats = data["kafka"]
        assert kafka_stats["topic"] == "sales_txn"
        assert kafka_stats["connected"] is True
        assert kafka_stats["lag_ms"] == 150.0
        
        # Check MongoDB stats
        mongodb_stats = data["mongodb"]
        assert mongodb_stats["database"] == "sales_db"
        assert mongodb_stats["collection"] == "raw_sales"
        assert mongodb_stats["connected"] is True
        assert mongodb_stats["document_count"] == 100
    
    async def test_stats_endpoint_error(self, client, mock_services):
        """Test stats endpoint when there's an error"""
        mock_services['mongodb'].get_collection_stats.side_effect = Exception("Stats error")
        
        response = await client.get("/stats")
        
        assert response.status_code == 500
        assert "Failed to retrieve statistics" in response.json()["detail"]
    
    async def test_shutdown_endpoint(self, client, mock_services):
        """Test shutdown endpoint"""
        with patch('app.main.processor') as mock_processor:
            mock_processor.stop = AsyncMock()
            
            response = await client.post("/shutdown")
            
            assert response.status_code == 200
            assert response.json()["message"] == "Service shutdown initiated"
            mock_processor.stop.assert_called_once()