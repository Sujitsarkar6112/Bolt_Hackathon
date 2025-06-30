import pytest
import asyncio
import httpx
from testcontainers.mongodb import MongoDbContainer
from testcontainers.compose import DockerCompose
import os
from datetime import datetime, timedelta
import random


class TestForecastServiceIntegration:
    """Integration tests for forecast service"""
    
    @pytest.fixture(scope="session")
    def docker_compose(self):
        """Start services with docker-compose"""
        compose_path = os.path.dirname(os.path.dirname(__file__))
        
        with DockerCompose(compose_path, compose_file_name="docker-compose.yml") as compose:
            # Wait for services to be ready
            compose.wait_for("http://localhost:5000/health")  # MLflow
            compose.wait_for("http://localhost:8002/health")  # Forecast service
            yield compose
    
    @pytest.fixture(scope="session")
    async def setup_test_data(self, docker_compose):
        """Setup test data in MongoDB"""
        from motor.motor_asyncio import AsyncIOMotorClient
        
        # Connect to MongoDB
        client = AsyncIOMotorClient("mongodb://admin:password@localhost:27018/sales_db?authSource=admin")
        db = client["sales_db"]
        collection = db["raw_sales"]
        
        # Clear existing data
        await collection.delete_many({})
        
        # Generate test data
        test_skus = ["TEST-SKU-001", "TEST-SKU-002", "TEST-SKU-003"]
        test_data = []
        
        base_date = datetime.utcnow() - timedelta(days=365)
        
        for sku in test_skus:
            for i in range(365):  # One year of daily data
                date = base_date + timedelta(days=i)
                
                # Generate realistic sales data with trend and seasonality
                base_demand = 100
                trend = i * 0.1  # Slight upward trend
                seasonal = 20 * (1 + 0.5 * (i % 7 == 0))  # Weekend boost
                noise = random.uniform(-10, 10)
                
                units_sold = max(1, int(base_demand + trend + seasonal + noise))
                price = round(random.uniform(10.0, 50.0), 2)
                
                test_data.append({
                    "sku": sku,
                    "ts": date.isoformat() + "Z",
                    "qty": units_sold,
                    "price": price,
                    "processed_at": datetime.utcnow().timestamp()
                })
        
        # Insert test data
        await collection.insert_many(test_data)
        
        # Create indexes
        await collection.create_index([("sku", 1), ("ts", 1)], unique=True)
        
        print(f"Inserted {len(test_data)} test records")
        
        yield test_skus
        
        # Cleanup
        await collection.delete_many({})
        client.close()
    
    @pytest.mark.asyncio
    async def test_health_endpoint(self, docker_compose):
        """Test health endpoint"""
        async with httpx.AsyncClient() as client:
            response = await client.get("http://localhost:8002/health")
            
            assert response.status_code == 200
            data = response.json()
            
            assert data["status"] in ["healthy", "degraded"]
            assert "timestamp" in data
            assert "database_connected" in data
    
    @pytest.mark.asyncio
    async def test_list_skus(self, docker_compose, setup_test_data):
        """Test listing available SKUs"""
        test_skus = setup_test_data
        
        async with httpx.AsyncClient() as client:
            response = await client.get("http://localhost:8002/skus")
            
            assert response.status_code == 200
            data = response.json()
            
            assert "skus" in data
            assert "count" in data
            assert len(data["skus"]) >= len(test_skus)
            
            # Check that our test SKUs are present
            for sku in test_skus:
                assert sku in data["skus"]
    
    @pytest.mark.asyncio
    async def test_forecast_short_term(self, docker_compose, setup_test_data):
        """Test short-term forecast (Prophet)"""
        test_skus = setup_test_data
        test_sku = test_skus[0]
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(f"http://localhost:8002/forecast/{test_sku}?horizon=7")
            
            assert response.status_code == 200
            data = response.json()
            
            assert data["sku"] == test_sku
            assert data["horizon_days"] == 7
            assert data["model_used"] in ["prophet", "tft"]  # Might fallback to Prophet
            assert len(data["forecast"]) == 7
            
            # Validate forecast structure
            for point in data["forecast"]:
                assert "date" in point
                assert "median" in point
                assert "p10" in point
                assert "p90" in point
                assert point["median"] >= 0
                assert point["p10"] >= 0
                assert point["p90"] >= point["median"]
    
    @pytest.mark.asyncio
    async def test_forecast_long_term(self, docker_compose, setup_test_data):
        """Test long-term forecast (TFT)"""
        test_skus = setup_test_data
        test_sku = test_skus[0]
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.get(f"http://localhost:8002/forecast/{test_sku}?horizon=60")
            
            assert response.status_code == 200
            data = response.json()
            
            assert data["sku"] == test_sku
            assert data["horizon_days"] == 60
            assert len(data["forecast"]) == 60
    
    @pytest.mark.asyncio
    async def test_forecast_invalid_sku(self, docker_compose):
        """Test forecast for non-existent SKU"""
        async with httpx.AsyncClient() as client:
            response = await client.get("http://localhost:8002/forecast/INVALID-SKU?horizon=7")
            
            assert response.status_code == 404
            assert "not found" in response.json()["detail"].lower()
    
    @pytest.mark.asyncio
    async def test_forecast_invalid_horizon(self, docker_compose, setup_test_data):
        """Test forecast with invalid horizon"""
        test_skus = setup_test_data
        test_sku = test_skus[0]
        
        async with httpx.AsyncClient() as client:
            # Test horizon too large
            response = await client.get(f"http://localhost:8002/forecast/{test_sku}?horizon=200")
            assert response.status_code == 422
            
            # Test horizon too small
            response = await client.get(f"http://localhost:8002/forecast/{test_sku}?horizon=0")
            assert response.status_code == 422
    
    @pytest.mark.asyncio
    async def test_model_status(self, docker_compose):
        """Test model status endpoint"""
        async with httpx.AsyncClient() as client:
            response = await client.get("http://localhost:8002/models/status")
            
            assert response.status_code == 200
            data = response.json()
            
            assert "prophet" in data
            assert "tft" in data
            assert "ensemble_config" in data
            
            # Check ensemble configuration
            config = data["ensemble_config"]
            assert "short_term_threshold" in config
            assert "long_term_threshold" in config
    
    @pytest.mark.asyncio
    async def test_retrain_trigger(self, docker_compose, setup_test_data):
        """Test manual retraining trigger"""
        async with httpx.AsyncClient(timeout=300.0) as client:  # Long timeout for training
            response = await client.post("http://localhost:8002/retrain")
            
            assert response.status_code == 200
            data = response.json()
            
            assert "message" in data
            assert "retraining initiated" in data["message"].lower()
            assert "timestamp" in data
    
    @pytest.mark.asyncio
    async def test_forecast_confidence_levels(self, docker_compose, setup_test_data):
        """Test different confidence levels"""
        test_skus = setup_test_data
        test_sku = test_skus[0]
        
        confidence_levels = [0.5, 0.8, 0.95]
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            for confidence in confidence_levels:
                response = await client.get(
                    f"http://localhost:8002/forecast/{test_sku}?horizon=7&confidence_level={confidence}"
                )
                
                assert response.status_code == 200
                data = response.json()
                
                assert data["confidence_level"] == confidence
                
                # Higher confidence should generally mean wider intervals
                for point in data["forecast"]:
                    interval_width = point["p90"] - point["p10"]
                    assert interval_width >= 0