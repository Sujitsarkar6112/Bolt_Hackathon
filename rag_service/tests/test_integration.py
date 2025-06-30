import pytest
import asyncio
import httpx
import os
import tempfile
from pathlib import Path
import json


class TestRAGServiceIntegration:
    """Integration tests for RAG service"""
    
    @pytest.fixture(scope="session")
    def test_documents(self):
        """Create test documents"""
        test_docs = {
            "customer_shopping_analysis.txt": """
Customer Shopping Data Analysis Report

Our customer shopping analysis across multiple categories shows consistent demand patterns:

1. Demographic Insights
   - Age distribution spans 18-65 with peak engagement in 25-45 segment
   - Gender preferences vary significantly by product category
   - Shopping mall preferences indicate location-based clustering

2. Purchase Patterns
   - Multiple payment methods indicate broad accessibility
   - Seasonal variations in quantity and pricing
   - Repeat purchase behavior varies by category

3. Geographic Performance
   - Shopping mall performance differs substantially by location
   - Category preferences show regional clustering
   - Customer loyalty patterns vary by demographic segment

Data source: Real customer shopping transactions
Timeline: Comprehensive historical analysis
Success metrics: 94% data coverage across all shopping malls
            """,
            
            "category_forecast.md": """
# Category Performance Analysis 2024

## SKU-CLOTHING Performance

### Customer Insights
- Strong demographic appeal across age groups
- Consistent purchase patterns across shopping malls
- Multiple payment method acceptance indicating accessibility

### Key Performance Factors
1. Customer demographic distribution
2. Shopping mall location preferences
3. Payment method diversity

### Customer Behavior Patterns
- Seasonal purchasing variations
- Location-specific preferences
- Age and gender segmentation

## Real Data Analysis
Customer shopping behavior analysis reveals strong insights:
- Diverse demographic engagement across all categories
- Consistent pricing acceptance patterns
- Strong location-based preference clustering
            """,
            
            "customer_behavior_analysis.txt": """
Customer Shopping Behavior Analysis

Real Customer Data Insights Across Categories

Category Performance:
1. SKU-CLOTHING
   - Broad demographic appeal with consistent mall performance
   - Balanced age and gender distribution
   - Strong accessibility across payment methods

2. SKU-BEAUTY
   - High-value transactions with strong customer loyalty
   - Premium shopping mall preferences
   - Strong repeat purchase patterns

3. SKU-ELECTRONICS
   - Premium segment with technology-focused demographics
   - Location-specific performance variations
   - Seasonal and promotional responsiveness

Customer Behavior Insights:
- Demographics vary significantly by product category
- Shopping mall performance differs by location and product type
- Payment method preferences indicate distinct customer behaviors
- Age and gender segmentation provides category-specific optimization opportunities

Data-Driven Recommendations:
- Focus on category-specific demographics
- Optimize mall-specific strategies based on customer patterns
- Leverage payment method insights for targeted approaches
            """
        }
        
        # Create temporary directory and files
        temp_dir = tempfile.mkdtemp()
        
        for filename, content in test_docs.items():
            file_path = Path(temp_dir) / filename
            with open(file_path, 'w') as f:
                f.write(content)
        
        yield temp_dir, test_docs
        
        # Cleanup
        import shutil
        shutil.rmtree(temp_dir)
    
    @pytest.mark.asyncio
    async def test_health_endpoint(self):
        """Test health endpoint"""
        async with httpx.AsyncClient() as client:
            response = await client.get("http://localhost:8003/health")
            
            assert response.status_code == 200
            data = response.json()
            
            assert data["status"] in ["healthy", "degraded", "unhealthy"]
            assert "timestamp" in data
            assert "vector_store_connected" in data
            assert "documents_indexed" in data
            assert "embeddings_model" in data
    
    @pytest.mark.asyncio
    async def test_document_ingestion(self, test_documents):
        """Test document ingestion via API"""
        temp_dir, test_docs = test_documents
        
        # Update documents path (in real scenario, this would be configured)
        # For testing, we'll use the ingest endpoint
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post("http://localhost:8003/ingest")
            
            assert response.status_code == 200
            data = response.json()
            
            assert "message" in data
            assert "ingestion initiated" in data["message"].lower()
            assert "timestamp" in data
    
    @pytest.mark.asyncio
    async def test_list_documents(self):
        """Test listing documents"""
        async with httpx.AsyncClient() as client:
            response = await client.get("http://localhost:8003/documents")
            
            assert response.status_code == 200
            data = response.json()
            
            assert "documents" in data
            assert "count" in data
            assert isinstance(data["documents"], list)
            assert data["count"] == len(data["documents"])
    
    @pytest.mark.asyncio
    async def test_search_documents(self):
        """Test document search without answer generation"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "http://localhost:8003/search?query=marketing strategy&top_k=3"
            )
            
            assert response.status_code == 200
            data = response.json()
            
            assert "query" in data
            assert "results" in data
            assert "count" in data
            assert data["query"] == "marketing strategy"
            assert isinstance(data["results"], list)
            assert len(data["results"]) <= 3
            
            # Check result structure
            if data["results"]:
                result = data["results"][0]
                assert "chunk_id" in result
                assert "document_name" in result
                assert "content" in result
                assert "score" in result
    
    @pytest.mark.asyncio
    async def test_ask_general_question(self):
        """Test asking a general question"""
        async with httpx.AsyncClient(timeout=60.0) as client:
            request_data = {
                "query": "What is our marketing strategy for Q4?",
                "top_k": 4
            }
            
            response = await client.post(
                "http://localhost:8003/ask",
                json=request_data
            )
            
            assert response.status_code == 200
            data = response.json()
            
            # Check response structure
            assert "query" in data
            assert "answer" in data
            assert "sources" in data
            assert "timestamp" in data
            assert "model_used" in data
            assert "total_sources" in data
            
            assert data["query"] == request_data["query"]
            assert isinstance(data["sources"], list)
            assert len(data["sources"]) <= 4
            
            # Check source structure
            if data["sources"]:
                source = data["sources"][0]
                assert "document" in source
                assert "chunk_id" in source
                assert "relevance_score" in source
                assert "content" in source
                assert "citation" in source
    
    @pytest.mark.asyncio
    async def test_ask_sku_specific_question(self):
        """Test asking a SKU-specific question"""
        async with httpx.AsyncClient(timeout=60.0) as client:
            request_data = {
                        "query": "What are the sales projections for SKU-CLOTHING?",
        "sku": "SKU-CLOTHING",
                "top_k": 3
            }
            
            response = await client.post(
                "http://localhost:8003/ask",
                json=request_data
            )
            
            assert response.status_code == 200
            data = response.json()
            
            assert data["query"] == request_data["query"]
            assert data["sku_filter"] == "SKU-CLOTHING"
            assert isinstance(data["sources"], list)
            
            # Answer should contain relevant information
            answer = data["answer"].lower()
            assert "sku-clothing" in answer or "sales" in answer or "forecast" in answer or "customer" in answer
    
    @pytest.mark.asyncio
    async def test_ask_with_citations(self):
        """Test that answers include proper citations"""
        async with httpx.AsyncClient(timeout=60.0) as client:
            request_data = {
                "query": "What is the budget for marketing campaigns?",
                "top_k": 2
            }
            
            response = await client.post(
                "http://localhost:8003/ask",
                json=request_data
            )
            
            assert response.status_code == 200
            data = response.json()
            
            answer = data["answer"]
            sources = data["sources"]
            
            # Check that answer contains citation markers
            if sources:
                # Should contain [1], [2], etc.
                citation_found = any(f"[{i+1}]" in answer for i in range(len(sources)))
                assert citation_found, "Answer should contain citation markers"
                
                # Check citation format (IEEE style)
                for source in sources:
                    citation = source["citation"]
                    assert '"' in citation  # Should have quotes around document name
                    assert "2024" in citation  # Should have year
    
    @pytest.mark.asyncio
    async def test_ask_no_relevant_context(self):
        """Test asking a question with no relevant context"""
        async with httpx.AsyncClient(timeout=60.0) as client:
            request_data = {
                "query": "What is the weather forecast for tomorrow?",
                "top_k": 4
            }
            
            response = await client.post(
                "http://localhost:8003/ask",
                json=request_data
            )
            
            assert response.status_code == 200
            data = response.json()
            
            # Should still return a response, but indicate lack of information
            answer = data["answer"].lower()
            assert any(phrase in answer for phrase in [
                "don't have", "not found", "no information", 
                "context doesn't contain", "unable to find"
            ])
    
    @pytest.mark.asyncio
    async def test_search_with_sku_filter(self):
        """Test search with SKU filter"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "http://localhost:8003/search?query=sales&sku=SKU-CLOTHING&top_k=2"
            )
            
            assert response.status_code == 200
            data = response.json()
            
            assert "results" in data
            results = data["results"]
            
            # Results should be relevant to SKU-CLOTHING
            if results:
                for result in results:
                    content = result["content"].lower()
                            # Should contain SKU-CLOTHING or related terms
        assert "sku-clothing" in content or "clothing" in content or "customer" in content
    
    @pytest.mark.asyncio
    async def test_invalid_requests(self):
        """Test various invalid requests"""
        async with httpx.AsyncClient() as client:
            # Empty query
            response = await client.post(
                "http://localhost:8003/ask",
                json={"query": "", "top_k": 4}
            )
            assert response.status_code == 422
            
            # Invalid top_k
            response = await client.post(
                "http://localhost:8003/ask",
                json={"query": "test", "top_k": 25}
            )
            assert response.status_code == 422
            
            # Invalid search parameters
            response = await client.get(
                "http://localhost:8003/search?query=test&top_k=0"
            )
            assert response.status_code == 422
    
    @pytest.mark.asyncio
    async def test_document_deletion(self):
        """Test document deletion"""
        async with httpx.AsyncClient() as client:
            # First, list documents to get a valid document name
            response = await client.get("http://localhost:8003/documents")
            assert response.status_code == 200
            
            documents = response.json()["documents"]
            
            if documents:
                # Delete the first document
                doc_name = documents[0]
                response = await client.delete(f"http://localhost:8003/documents/{doc_name}")
                
                assert response.status_code == 200
                data = response.json()
                
                assert "message" in data
                assert doc_name in data["message"]
                assert "timestamp" in data
    
    @pytest.mark.asyncio
    async def test_concurrent_requests(self):
        """Test handling of concurrent requests"""
        async with httpx.AsyncClient(timeout=60.0) as client:
            # Create multiple concurrent requests
            tasks = []
            for i in range(5):
                task = client.post(
                    "http://localhost:8003/ask",
                    json={
                        "query": f"What is the marketing strategy for product {i}?",
                        "top_k": 2
                    }
                )
                tasks.append(task)
            
            # Execute all requests concurrently
            responses = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Check that all requests completed successfully
            for response in responses:
                if isinstance(response, Exception):
                    pytest.fail(f"Request failed with exception: {response}")
                
                assert response.status_code == 200
                data = response.json()
                assert "answer" in data
                assert "sources" in data