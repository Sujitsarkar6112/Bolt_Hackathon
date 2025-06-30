import asyncio
import logging
from typing import Optional, Dict, Any, TypeVar, Generic, List
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection, AsyncIOMotorDatabase
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import os
from datetime import datetime

logger = logging.getLogger(__name__)

# Type variable for collection documents
T = TypeVar('T')

class MongoDBClient:
    """Singleton MongoDB client with connection pooling and retry logic"""
    
    _instance: Optional['MongoDBClient'] = None
    _client: Optional[AsyncIOMotorClient] = None
    _databases: Dict[str, AsyncIOMotorDatabase] = {}
    
    def __new__(cls) -> 'MongoDBClient':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((ConnectionFailure, ServerSelectionTimeoutError))
    )
    async def connect(self, mongo_uri: Optional[str] = None) -> None:
        """
        Establish MongoDB connection with retry logic
        
        Args:
            mongo_uri: MongoDB connection URI. If None, uses MONGO_URI env var
        """
        if self._client is not None:
            return
        
        uri = mongo_uri or os.getenv('MONGO_URI', 'mongodb://localhost:27017')
        
        try:
            self._client = AsyncIOMotorClient(
                uri,
                serverSelectionTimeoutMS=5000,
                connectTimeoutMS=5000,
                socketTimeoutMS=5000,
                maxPoolSize=50,
                minPoolSize=5,
                maxIdleTimeMS=30000,
                waitQueueTimeoutMS=5000,
                retryWrites=True,
                retryReads=True
            )
            
            # Test connection
            await self._client.admin.command('ping')
            logger.info("MongoDB connection established successfully")
            
        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            self._client = None
            raise
    
    async def disconnect(self) -> None:
        """Close MongoDB connection"""
        if self._client:
            self._client.close()
            self._client = None
            self._databases.clear()
            logger.info("MongoDB connection closed")
    
    async def is_connected(self) -> bool:
        """Check if MongoDB is connected and responsive"""
        if not self._client:
            return False
        
        try:
            await self._client.admin.command('ping')
            return True
        except Exception:
            return False
    
    def get_database(self, db_name: str) -> AsyncIOMotorDatabase:
        """
        Get database instance with caching
        
        Args:
            db_name: Database name
            
        Returns:
            AsyncIOMotorDatabase instance
        """
        if not self._client:
            raise RuntimeError("MongoDB client not connected. Call connect() first.")
        
        if db_name not in self._databases:
            self._databases[db_name] = self._client[db_name]
        
        return self._databases[db_name]
    
    def get_collection(self, db_name: str, collection_name: str) -> 'TypedCollection':
        """
        Get typed collection instance
        
        Args:
            db_name: Database name
            collection_name: Collection name
            
        Returns:
            TypedCollection instance with helper methods
        """
        database = self.get_database(db_name)
        collection = database[collection_name]
        return TypedCollection(collection, db_name, collection_name)


class TypedCollection(Generic[T]):
    """Typed wrapper around AsyncIOMotorCollection with helper methods"""
    
    def __init__(self, collection: AsyncIOMotorCollection, db_name: str, collection_name: str):
        self._collection = collection
        self.db_name = db_name
        self.collection_name = collection_name
    
    @property
    def native(self) -> AsyncIOMotorCollection:
        """Access to native AsyncIOMotorCollection for advanced operations"""
        return self._collection
    
    async def insert_one(self, document: Dict[str, Any]) -> str:
        """
        Insert single document with automatic timestamp
        
        Args:
            document: Document to insert
            
        Returns:
            Inserted document ID as string
        """
        if 'created_at' not in document:
            document['created_at'] = datetime.utcnow()
        
        result = await self._collection.insert_one(document)
        logger.debug(f"Inserted document in {self.db_name}.{self.collection_name}")
        return str(result.inserted_id)
    
    async def insert_many(self, documents: List[Dict[str, Any]], ordered: bool = False) -> List[str]:
        """
        Insert multiple documents with automatic timestamps
        
        Args:
            documents: List of documents to insert
            ordered: Whether to maintain order (affects error handling)
            
        Returns:
            List of inserted document IDs as strings
        """
        if not documents:
            return []
        
        # Add timestamps to documents that don't have them
        for doc in documents:
            if 'created_at' not in doc:
                doc['created_at'] = datetime.utcnow()
        
        try:
            result = await self._collection.insert_many(documents, ordered=ordered)
            logger.info(f"Inserted {len(result.inserted_ids)} documents in {self.db_name}.{self.collection_name}")
            return [str(id_) for id_ in result.inserted_ids]
        except Exception as e:
            # Handle partial success in unordered inserts
            if hasattr(e, 'details') and 'writeErrors' in e.details:
                successful = len(documents) - len(e.details['writeErrors'])
                logger.warning(f"Partial insert success: {successful}/{len(documents)} documents inserted")
                # Return IDs of successful inserts (if available)
                return []
            raise
    
    async def find_one(self, filter_dict: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Find single document
        
        Args:
            filter_dict: Query filter
            
        Returns:
            Document or None if not found
        """
        result = await self._collection.find_one(filter_dict)
        return result
    
    async def find_many(
        self, 
        filter_dict: Dict[str, Any], 
        limit: Optional[int] = None,
        sort: Optional[List[tuple]] = None
    ) -> List[Dict[str, Any]]:
        """
        Find multiple documents
        
        Args:
            filter_dict: Query filter
            limit: Maximum number of documents to return
            sort: Sort specification
            
        Returns:
            List of documents
        """
        cursor = self._collection.find(filter_dict)
        
        if sort:
            cursor = cursor.sort(sort)
        
        if limit:
            cursor = cursor.limit(limit)
        
        return await cursor.to_list(length=limit)
    
    async def update_one(
        self, 
        filter_dict: Dict[str, Any], 
        update_dict: Dict[str, Any],
        upsert: bool = False
    ) -> bool:
        """
        Update single document
        
        Args:
            filter_dict: Query filter
            update_dict: Update operations
            upsert: Whether to insert if document doesn't exist
            
        Returns:
            True if document was modified, False otherwise
        """
        # Add updated_at timestamp
        if '$set' not in update_dict:
            update_dict['$set'] = {}
        update_dict['$set']['updated_at'] = datetime.utcnow()
        
        result = await self._collection.update_one(filter_dict, update_dict, upsert=upsert)
        return result.modified_count > 0
    
    async def delete_one(self, filter_dict: Dict[str, Any]) -> bool:
        """
        Delete single document
        
        Args:
            filter_dict: Query filter
            
        Returns:
            True if document was deleted, False otherwise
        """
        result = await self._collection.delete_one(filter_dict)
        return result.deleted_count > 0
    
    async def delete_many(self, filter_dict: Dict[str, Any]) -> int:
        """
        Delete multiple documents
        
        Args:
            filter_dict: Query filter
            
        Returns:
            Number of documents deleted
        """
        result = await self._collection.delete_many(filter_dict)
        logger.info(f"Deleted {result.deleted_count} documents from {self.db_name}.{self.collection_name}")
        return result.deleted_count
    
    async def count_documents(self, filter_dict: Dict[str, Any]) -> int:
        """
        Count documents matching filter
        
        Args:
            filter_dict: Query filter
            
        Returns:
            Number of matching documents
        """
        return await self._collection.count_documents(filter_dict)
    
    async def distinct(self, field: str, filter_dict: Optional[Dict[str, Any]] = None) -> List[Any]:
        """
        Get distinct values for a field
        
        Args:
            field: Field name
            filter_dict: Optional query filter
            
        Returns:
            List of distinct values
        """
        return await self._collection.distinct(field, filter_dict or {})
    
    async def aggregate(self, pipeline: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Run aggregation pipeline
        
        Args:
            pipeline: Aggregation pipeline
            
        Returns:
            List of aggregation results
        """
        cursor = self._collection.aggregate(pipeline)
        return await cursor.to_list(length=None)
    
    async def create_index(self, keys: List[tuple], **kwargs) -> str:
        """
        Create index on collection
        
        Args:
            keys: Index specification as list of (field, direction) tuples
            **kwargs: Additional index options
            
        Returns:
            Index name
        """
        index_name = await self._collection.create_index(keys, **kwargs)
        logger.info(f"Created index '{index_name}' on {self.db_name}.{self.collection_name}")
        return index_name


# Global MongoDB client instance
mongodb_client = MongoDBClient()


# Convenience functions for common operations
async def get_collection(db_name: str, collection_name: str) -> TypedCollection:
    """
    Get typed collection instance (convenience function)
    
    Args:
        db_name: Database name
        collection_name: Collection name
        
    Returns:
        TypedCollection instance
    """
    return mongodb_client.get_collection(db_name, collection_name)


async def ensure_connection(mongo_uri: Optional[str] = None) -> None:
    """
    Ensure MongoDB connection is established
    
    Args:
        mongo_uri: Optional MongoDB URI override
    """
    await mongodb_client.connect(mongo_uri)


async def close_connection() -> None:
    """Close MongoDB connection"""
    await mongodb_client.disconnect()


# Context manager for automatic connection management
class MongoDBContext:
    """Context manager for MongoDB operations"""
    
    def __init__(self, mongo_uri: Optional[str] = None):
        self.mongo_uri = mongo_uri
    
    async def __aenter__(self) -> MongoDBClient:
        await ensure_connection(self.mongo_uri)
        return mongodb_client
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        # Don't close connection on exit to allow reuse
        # Connection will be closed when application shuts down
        pass


# Service-specific collection helpers
class IngestServiceCollections:
    """Collection helpers for ingest service"""
    
    @staticmethod
    async def get_sales_collection() -> TypedCollection:
        """Get sales events collection"""
        return await get_collection("sales_db", "raw_sales")
    
    @staticmethod
    async def setup_indexes() -> None:
        """Setup required indexes for ingest service"""
        sales_collection = await IngestServiceCollections.get_sales_collection()
        
        # Unique compound index on sku + ts
        await sales_collection.create_index(
            [("sku", 1), ("ts", 1)],
            unique=True,
            background=True,
            name="sku_ts_unique"
        )
        
        # Index on timestamp for time-based queries
        await sales_collection.create_index(
            [("ts", -1)],
            background=True,
            name="ts_desc"
        )


class ForecastServiceCollections:
    """Collection helpers for forecast service"""
    
    @staticmethod
    async def get_models_collection() -> TypedCollection:
        """Get models metadata collection"""
        return await get_collection("forecast_db", "models")
    
    @staticmethod
    async def get_predictions_collection() -> TypedCollection:
        """Get predictions collection"""
        return await get_collection("forecast_db", "predictions")
    
    @staticmethod
    async def setup_indexes() -> None:
        """Setup required indexes for forecast service"""
        models_collection = await ForecastServiceCollections.get_models_collection()
        predictions_collection = await ForecastServiceCollections.get_predictions_collection()
        
        # Index on model name and version
        await models_collection.create_index(
            [("model_name", 1), ("version", 1)],
            unique=True,
            background=True,
            name="model_version_unique"
        )
        
        # Index on SKU and forecast date
        await predictions_collection.create_index(
            [("sku", 1), ("forecast_date", -1)],
            background=True,
            name="sku_forecast_date"
        )


class RAGServiceCollections:
    """Collection helpers for RAG service"""
    
    @staticmethod
    async def get_documents_collection() -> TypedCollection:
        """Get document vectors collection"""
        return await get_collection("enterprise_rag", "docs_vectors")
    
    @staticmethod
    async def setup_indexes() -> None:
        """Setup required indexes for RAG service"""
        docs_collection = await RAGServiceCollections.get_documents_collection()
        
        # Index on document name
        await docs_collection.create_index(
            [("document_name", 1)],
            background=True,
            name="document_name"
        )
        
        # Index on chunk_id
        await docs_collection.create_index(
            [("chunk_id", 1)],
            unique=True,
            background=True,
            name="chunk_id_unique"
        )
        
        # Note: Vector search index must be created manually in MongoDB Atlas
        logger.info("Remember to create vector search index manually in MongoDB Atlas")