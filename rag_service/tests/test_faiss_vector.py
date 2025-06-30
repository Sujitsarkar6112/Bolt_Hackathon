import pytest
import asyncio
import tempfile
import shutil
from pathlib import Path
from app.services.vector_store import LocalVectorStore
from app.models import DocumentChunk
from datetime import datetime


class TestFAISSVectorStore:
    """Test cases for FAISS vector store functionality"""
    
    @pytest.fixture
    async def temp_vector_store(self):
        """Create temporary vector store for testing"""
        temp_dir = tempfile.mkdtemp()
        
        # Mock settings for testing
        import app.config
        original_path = app.config.settings.faiss_index_path
        app.config.settings.faiss_index_path = temp_dir
        
        vector_store = LocalVectorStore()
        await vector_store.connect()
        
        yield vector_store
        
        # Cleanup
        await vector_store.disconnect()
        app.config.settings.faiss_index_path = original_path
        shutil.rmtree(temp_dir)
    
    async def test_store_and_search_documents(self, temp_vector_store):
        """Test storing and searching documents"""
        # Create test chunks
        chunks = [
            DocumentChunk(
                chunk_id="test_chunk_1",
                document_name="test_doc.pdf",
                page_number=1,
                content="This is about demand forecasting for SKU-CLOTHING",
                embedding=[0.1] * 1536,  # Mock embedding
                metadata={"source": "test"},
                created_at=datetime.utcnow()
            ),
            DocumentChunk(
                chunk_id="test_chunk_2",
                document_name="test_doc.pdf",
                page_number=2,
                content="Marketing strategies for product sales",
                embedding=[0.2] * 1536,  # Mock embedding
                metadata={"source": "test"},
                created_at=datetime.utcnow()
            )
        ]
        
        # Store chunks
        await temp_vector_store.store_document_chunks(chunks)
        
        # Search for documents
        results = await temp_vector_store.similarity_search("demand forecasting", top_k=2)
        
        assert len(results) >= 1
        assert any("demand forecasting" in result["content"] for result in results)
    
    async def test_document_deletion(self, temp_vector_store):
        """Test document deletion"""
        # Create and store test chunk
        chunk = DocumentChunk(
            chunk_id="delete_test_chunk",
            document_name="delete_test.pdf",
            page_number=1,
            content="This document will be deleted",
            embedding=[0.3] * 1536,
            metadata={"source": "test"},
            created_at=datetime.utcnow()
        )
        
        await temp_vector_store.store_document_chunks([chunk])
        
        # Verify document exists
        documents = await temp_vector_store.list_documents()
        assert "delete_test.pdf" in documents
        
        # Delete document
        deleted_count = await temp_vector_store.delete_document("delete_test.pdf")
        assert deleted_count >= 1
        
        # Verify document is gone
        documents = await temp_vector_store.list_documents()
        assert "delete_test.pdf" not in documents
    
    async def test_sku_filtering(self, temp_vector_store):
        """Test SKU-based filtering in search"""
        # Create chunks with different SKUs
        chunks = [
            DocumentChunk(
                chunk_id="sku_chunk_1",
                document_name="sku_test.pdf",
                page_number=1,
                content="SKU-CLOTHING has high demand based on customer shopping data",
                embedding=[0.4] * 1536,
                metadata={"source": "test"},
                created_at=datetime.utcnow()
            ),
            DocumentChunk(
                chunk_id="sku_chunk_2",
                document_name="sku_test.pdf",
                page_number=2,
                content="Customer shopping patterns vary by category and demographics",
                embedding=[0.5] * 1536,
                metadata={"source": "test"},
                created_at=datetime.utcnow()
            )
        ]
        
        await temp_vector_store.store_document_chunks(chunks)
        
        # Search with SKU filter
        results = await temp_vector_store.similarity_search(
            "demand", 
            top_k=5, 
            sku_filter="SKU-CLOTHING"
        )
        
        # Should only return chunks containing SKU-CLOTHING
        assert len(results) >= 1
        assert all("SKU-CLOTHING" in result["content"] for result in results)
    
    async def test_collection_stats(self, temp_vector_store):
        """Test collection statistics"""
        # Add some test documents
        chunk = DocumentChunk(
            chunk_id="stats_chunk",
            document_name="stats_test.pdf",
            page_number=1,
            content="Test content for statistics",
            embedding=[0.6] * 1536,
            metadata={"source": "test"},
            created_at=datetime.utcnow()
        )
        
        await temp_vector_store.store_document_chunks([chunk])
        
        # Get stats
        stats = await temp_vector_store.get_collection_stats()
        
        assert "total_documents" in stats
        assert "total_chunks" in stats
        assert "index_size_mb" in stats
        assert stats["total_documents"] >= 1
        assert stats["total_chunks"] >= 1