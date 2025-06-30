import logging
from typing import List, Optional, Dict, Any
from datetime import datetime

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../../../'))
from utils.db import RAGServiceCollections, ensure_connection, close_connection, TypedCollection
from ..config import settings
from ..models import DocumentChunk

logger = logging.getLogger(__name__)


class VectorStore:
    """MongoDB Atlas Vector Search implementation using centralized utilities"""
    
    def __init__(self):
        self.collection: TypedCollection = None
        self._connected = False
    
    async def connect(self):
        """Connect to MongoDB Atlas and setup indexes"""
        try:
            await ensure_connection(settings.mongodb_atlas_uri)
            self.collection = await RAGServiceCollections.get_documents_collection()
            await RAGServiceCollections.setup_indexes()
            
            self._connected = True
            logger.info("VectorStore connected to MongoDB Atlas successfully")
            
        except Exception as e:
            logger.error(f"Failed to connect VectorStore to MongoDB Atlas: {e}")
            self._connected = False
            raise
    
    async def disconnect(self):
        """Disconnect from MongoDB Atlas"""
        await close_connection()
        self._connected = False
        logger.info("VectorStore disconnected from MongoDB Atlas")
    
    async def is_connected(self) -> bool:
        """Check if MongoDB Atlas is connected"""
        if not self._connected or not self.collection:
            return False
        
        try:
            from utils.db import mongodb_client
            return await mongodb_client.is_connected()
        except Exception:
            self._connected = False
            return False
    
    async def store_document_chunks(self, chunks: List[DocumentChunk]):
        """Store document chunks in vector database"""
        if not self.collection:
            raise RuntimeError("Vector store not connected")
        
        # Delete existing chunks for the same document
        if chunks:
            document_name = chunks[0].document_name
            await self.delete_document(document_name)
        
        # Prepare documents for insertion
        documents = []
        for chunk in chunks:
            doc = {
                "chunk_id": chunk.chunk_id,
                "document_name": chunk.document_name,
                "page_number": chunk.page_number,
                "content": chunk.content,
                "embedding": chunk.embedding,
                "metadata": chunk.metadata,
                "created_at": chunk.created_at
            }
            documents.append(doc)
        
        # Insert documents using centralized utilities
        if documents:
            inserted_ids = await self.collection.insert_many(documents)
            logger.info(f"Stored {len(inserted_ids)} chunks for document {chunks[0].document_name}")
    
    async def similarity_search(
        self,
        query: str,
        top_k: int = 4,
        sku_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Perform similarity search using vector search"""
        if not self.collection:
            raise RuntimeError("Vector store not connected")
        
        # Import here to avoid circular dependency
        from .embeddings import EmbeddingService
        embedding_service = EmbeddingService()
        
        # Get query embedding
        query_embedding = await embedding_service.get_embedding(query)
        
        # Build aggregation pipeline
        pipeline = [
            {
                "$vectorSearch": {
                    "index": settings.vector_index_name,
                    "path": "embedding",
                    "queryVector": query_embedding,
                    "numCandidates": top_k * 10,
                    "limit": top_k
                }
            },
            {
                "$addFields": {
                    "score": {"$meta": "vectorSearchScore"}
                }
            }
        ]
        
        # Add SKU filter if provided
        if sku_filter:
            pipeline.insert(1, {
                "$match": {
                    "$or": [
                        {"content": {"$regex": sku_filter, "$options": "i"}},
                        {"metadata.sku": sku_filter}
                    ]
                }
            })
        
        # Execute search using centralized utilities
        results = await self.collection.aggregate(pipeline)
        
        # Format results
        formatted_results = []
        for result in results:
            formatted_results.append({
                "chunk_id": result["chunk_id"],
                "document_name": result["document_name"],
                "page_number": result.get("page_number"),
                "content": result["content"],
                "score": result.get("score", 0.0),
                "metadata": result.get("metadata", {})
            })
        
        logger.info(f"Found {len(formatted_results)} similar chunks for query")
        return formatted_results
    
    async def get_document_count(self) -> int:
        """Get total number of documents indexed"""
        if not self.collection:
            return 0
        
        try:
            count = await self.collection.count_documents({})
            return count
        except Exception as e:
            logger.error(f"Failed to get document count: {e}")
            return 0
    
    async def list_documents(self) -> List[str]:
        """List all unique document names"""
        if not self.collection:
            return []
        
        try:
            documents = await self.collection.distinct("document_name")
            return sorted(documents)
        except Exception as e:
            logger.error(f"Failed to list documents: {e}")
            return []
    
    async def delete_document(self, document_name: str) -> int:
        """Delete all chunks for a specific document"""
        if not self.collection:
            return 0
        
        try:
            deleted_count = await self.collection.delete_many({"document_name": document_name})
            logger.info(f"Deleted {deleted_count} chunks for document {document_name}")
            return deleted_count
        except Exception as e:
            logger.error(f"Failed to delete document {document_name}: {e}")
            return 0
    
    async def get_collection_stats(self) -> Dict[str, Any]:
        """Get collection statistics"""
        if not self.collection:
            return {}
        
        try:
            pipeline = [
                {
                    "$group": {
                        "_id": "$document_name",
                        "chunk_count": {"$sum": 1},
                        "avg_content_length": {"$avg": {"$strLenCP": "$content"}},
                        "created_at": {"$min": "$created_at"}
                    }
                },
                {
                    "$group": {
                        "_id": None,
                        "total_documents": {"$sum": 1},
                        "total_chunks": {"$sum": "$chunk_count"},
                        "avg_chunks_per_doc": {"$avg": "$chunk_count"},
                        "avg_content_length": {"$avg": "$avg_content_length"}
                    }
                }
            ]
            
            results = await self.collection.aggregate(pipeline)
            
            if results:
                return results[0]
            else:
                return {
                    "total_documents": 0,
                    "total_chunks": 0,
                    "avg_chunks_per_doc": 0,
                    "avg_content_length": 0
                }
        except Exception as e:
            logger.error(f"Failed to get collection stats: {e}")
            return {}

# Create global instance
vector_store = VectorStore()