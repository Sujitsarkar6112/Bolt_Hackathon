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
        "ENVIRONMENT": "test",
        "LOG_LEVEL": "DEBUG",
        "DOCUMENTS_PATH": "./test_docs",
        "CHUNK_SIZE": "500",  # Smaller chunks for testing
        "CHUNK_OVERLAP": "50",
        "TOP_K_DEFAULT": "3",
        "ENABLE_AUTO_INGESTION": "false",  # Disable for testing
    })
    
    yield
    
    # Cleanup
    test_vars = [
        "ENVIRONMENT", "LOG_LEVEL", "DOCUMENTS_PATH", 
        "CHUNK_SIZE", "CHUNK_OVERLAP", "TOP_K_DEFAULT", "ENABLE_AUTO_INGESTION"
    ]
    for var in test_vars:
        os.environ.pop(var, None)


@pytest.fixture
def sample_documents():
    """Sample documents for testing"""
    return {
        "marketing_plan.txt": """
        Q4 Marketing Plan
        
        Customer Shopping Analysis:
        - Data Source: Real customer shopping transactions
        - Timeline: Comprehensive historical analysis
        - Coverage: 94% across all shopping malls
        - Categories: SKU-CLOTHING, SKU-BEAUTY, SKU-ELECTRONICS
        
        Key Insights:
        1. Demographic patterns across age groups (18-65)
        2. Shopping mall performance variations by location
        3. Payment method preferences by category
        4. Seasonal purchasing patterns
        """,
        
        "sales_data.md": """
        # Sales Performance Report
        
        ## Real Customer Data Analysis
        
        ### SKU-CLOTHING Performance
        - Customer Engagement: Broad demographic appeal
        - Shopping Malls: Consistent performance across locations
        - Payment Methods: Multiple options indicate accessibility
        
        ### SKU-BEAUTY Performance  
        - Customer Loyalty: High repeat purchase rates
        - Demographics: Strong across all age groups
        - Premium Malls: Preferred locations for this category
        
        ### Customer Insights
        - Age Distribution: Balanced across 18-65 segments
        - Gender Preferences: Vary significantly by category
        - Location Clustering: Clear mall-specific patterns
        """
    }