import pytest
import asyncio
import os
import sys

# Add app to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(autouse=True)
def setup_test_environment():
    """Setup test environment variables"""
    os.environ.update({
        "MONGODB_URL": "mongodb://admin:password@localhost:27018/sales_db?authSource=admin",
        "MLFLOW_TRACKING_URI": "http://localhost:5000",
        "ENVIRONMENT": "test",
        "LOG_LEVEL": "DEBUG",
        "MIN_TRAINING_SAMPLES": "30",  # Reduced for testing
        "TFT_MAX_EPOCHS": "5",  # Reduced for faster testing
    })
    
    yield
    
    # Cleanup
    test_vars = [
        "MONGODB_URL", "MLFLOW_TRACKING_URI", "ENVIRONMENT", 
        "LOG_LEVEL", "MIN_TRAINING_SAMPLES", "TFT_MAX_EPOCHS"
    ]
    for var in test_vars:
        os.environ.pop(var, None)