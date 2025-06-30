import pytest
from app.database import MongoDBClient
from app.config import settings


class TestMongoDBClient:
    """Test cases for MongoDB client functionality"""
    
    @pytest.fixture
    async def db_client(self, mongodb_client):
        """Create MongoDB client for testing"""
        client = MongoDBClient()
        client.client = mongodb_client
        client.collection = mongodb_client[settings.mongodb_database][settings.mongodb_collection]
        client._connected = True
        
        # Ensure clean state
        await client.collection.delete_many({})
        
        yield client
        
        # Cleanup
        await client.collection.delete_many({})
    
    async def test_insert_sales_event(self, db_client):
        """Test inserting a single sales event"""
        event = {
            "sku": "TEST-SKU-001",
            "qty": 5,
            "price": 29.99,
            "ts": "2024-01-15T10:30:00Z",
            "event_id": "test-001"
        }
        
        result = await db_client.insert_sales_event(event)
        assert result is True
        
        # Verify insertion
        doc = await db_client.collection.find_one({"sku": "TEST-SKU-001"})
        assert doc is not None
        assert doc["qty"] == 5
        assert doc["price"] == 29.99
    
    async def test_duplicate_event_handling(self, db_client):
        """Test handling of duplicate events"""
        event = {
            "sku": "TEST-SKU-002",
            "qty": 3,
            "price": 19.99,
            "ts": "2024-01-15T10:31:00Z",
            "event_id": "test-002"
        }
        
        # Insert first time
        result1 = await db_client.insert_sales_event(event)
        assert result1 is True
        
        # Insert duplicate (should be ignored)
        result2 = await db_client.insert_sales_event(event)
        assert result2 is False
        
        # Verify only one document exists
        count = await db_client.collection.count_documents({"sku": "TEST-SKU-002"})
        assert count == 1
    
    async def test_batch_insert(self, db_client):
        """Test batch insertion of events"""
        events = [
            {
                "sku": f"BATCH-SKU-{i:03d}",
                "qty": i + 1,
                "price": (i + 1) * 10.0,
                "ts": f"2024-01-15T10:{30+i:02d}:00Z",
                "event_id": f"batch-{i:03d}"
            }
            for i in range(5)
        ]
        
        inserted_count = await db_client.insert_sales_events_batch(events)
        assert inserted_count == 5
        
        # Verify all documents were inserted
        count = await db_client.collection.count_documents({"sku": {"$regex": "^BATCH-SKU-"}})
        assert count == 5
    
    async def test_batch_insert_with_duplicates(self, db_client):
        """Test batch insertion with some duplicate events"""
        # Insert initial event
        initial_event = {
            "sku": "DUPLICATE-SKU",
            "qty": 1,
            "price": 10.0,
            "ts": "2024-01-15T10:30:00Z",
            "event_id": "initial"
        }
        await db_client.insert_sales_event(initial_event)
        
        # Batch with duplicate
        batch_events = [
            initial_event,  # Duplicate
            {
                "sku": "NEW-SKU-001",
                "qty": 2,
                "price": 20.0,
                "ts": "2024-01-15T10:31:00Z",
                "event_id": "new-001"
            },
            {
                "sku": "NEW-SKU-002",
                "qty": 3,
                "price": 30.0,
                "ts": "2024-01-15T10:32:00Z",
                "event_id": "new-002"
            }
        ]
        
        inserted_count = await db_client.insert_sales_events_batch(batch_events)
        assert inserted_count == 2  # Only new events should be inserted
        
        # Verify total count
        total_count = await db_client.collection.count_documents({})
        assert total_count == 3  # 1 initial + 2 new
    
    async def test_collection_stats(self, db_client):
        """Test getting collection statistics"""
        # Insert some test data
        events = [
            {
                "sku": f"STATS-SKU-{i:03d}",
                "qty": 1,
                "price": 10.0,
                "ts": f"2024-01-15T10:{30+i:02d}:00Z",
                "event_id": f"stats-{i:03d}"
            }
            for i in range(3)
        ]
        
        await db_client.insert_sales_events_batch(events)
        
        stats = await db_client.get_collection_stats()
        assert "document_count" in stats
        assert stats["document_count"] >= 3