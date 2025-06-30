import asyncio
from typing import Dict, Any, List
import structlog
from utils.db import IngestServiceCollections, ensure_connection, close_connection, TypedCollection

logger = structlog.get_logger()


class MongoDBClient:
    """MongoDB client for ingest service using centralized utilities"""
    
    def __init__(self):
        self.collection: TypedCollection = None
        self._connected = False
    
    async def connect(self) -> None:
        """Establish MongoDB connection and setup indexes"""
        try:
            await ensure_connection()
            self.collection = await IngestServiceCollections.get_sales_collection()
            await IngestServiceCollections.setup_indexes()
            
            self._connected = True
            logger.info("MongoDB connected successfully for ingest service")
            
        except Exception as e:
            logger.error("Failed to connect to MongoDB", error=str(e))
            self._connected = False
            raise
    
    async def disconnect(self) -> None:
        """Close MongoDB connection"""
        await close_connection()
        self._connected = False
        logger.info("MongoDB disconnected")
    
    async def is_connected(self) -> bool:
        """Check if MongoDB is connected"""
        if not self._connected or not self.collection:
            return False
        
        try:
            # Use the centralized connection check
            from utils.db import mongodb_client
            return await mongodb_client.is_connected()
        except Exception:
            self._connected = False
            return False
    
    async def insert_sales_event(self, event: Dict[str, Any]) -> bool:
        """Insert a single sales event"""
        try:
            await self.collection.insert_one(event)
            return True
        except Exception as e:
            if "duplicate key" in str(e).lower():
                logger.warning("Duplicate sales event ignored", 
                              sku=event.get('sku'), 
                              ts=event.get('ts'))
                return False
            else:
                logger.error("Failed to insert sales event", error=str(e), event=event)
                raise
    
    async def insert_sales_events_batch(self, events: List[Dict[str, Any]]) -> int:
        """Insert multiple sales events in batch"""
        if not events:
            return 0
        
        try:
            inserted_ids = await self.collection.insert_many(events, ordered=False)
            return len(inserted_ids)
        except Exception as e:
            logger.error("Failed to insert sales events batch", error=str(e))
            # The centralized utility handles partial success
            return 0
    
    async def get_collection_stats(self) -> Dict[str, Any]:
        """Get collection statistics"""
        try:
            count = await self.collection.count_documents({})
            return {"document_count": count}
        except Exception as e:
            logger.error("Failed to get collection stats", error=str(e))
            return {"document_count": 0}


# Global MongoDB client instance
mongodb_client = MongoDBClient()