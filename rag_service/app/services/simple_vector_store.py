import logging
from typing import List, Optional, Dict, Any
from datetime import datetime
import json
import os

from ..config import settings
from ..models import DocumentChunk

logger = logging.getLogger(__name__)


class SimpleVectorStore:
    """Simple in-memory vector store implementation for testing without MongoDB"""
    
    def __init__(self):
        self.documents: List[Dict[str, Any]] = []
        self._connected = False
        self.storage_file = "local_vector_store.json"
    
    async def connect(self):
        """Initialize the simple vector store"""
        try:
            # Load existing data if available
            if os.path.exists(self.storage_file):
                with open(self.storage_file, 'r') as f:
                    self.documents = json.load(f)
            
            self._connected = True
            logger.info("SimpleVectorStore initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize SimpleVectorStore: {e}")
            self._connected = False
            raise
    
    async def disconnect(self):
        """Save data and disconnect"""
        try:
            # Save data to file
            with open(self.storage_file, 'w') as f:
                json.dump(self.documents, f, indent=2)
            
            self._connected = False
            logger.info("SimpleVectorStore disconnected and data saved")
        except Exception as e:
            logger.error(f"Failed to save data: {e}")
    
    async def is_connected(self) -> bool:
        """Check if vector store is connected"""
        return self._connected
    
    async def store_document_chunks(self, chunks: List[DocumentChunk]):
        """Store document chunks in memory"""
        if not self._connected:
            raise RuntimeError("Vector store not connected")
        
        # Delete existing chunks for the same document
        if chunks:
            document_name = chunks[0].document_name
            await self.delete_document(document_name)
        
        # Add new chunks
        for chunk in chunks:
            doc = {
                "chunk_id": chunk.chunk_id,
                "document_name": chunk.document_name,
                "page_number": chunk.page_number,
                "content": chunk.content,
                "embedding": chunk.embedding if chunk.embedding else [],
                "metadata": chunk.metadata,
                "created_at": chunk.created_at.isoformat() if chunk.created_at else datetime.utcnow().isoformat()
            }
            self.documents.append(doc)
        
        logger.info(f"Stored {len(chunks)} chunks for document {chunks[0].document_name if chunks else 'unknown'}")
    
    async def similarity_search(
        self,
        query: str,
        top_k: int = 4,
        sku_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Simple text-based search (without embeddings for now)"""
        if not self._connected:
            raise RuntimeError("Vector store not connected")
        
        # Simple keyword-based search
        query_words = query.lower().split()
        results = []
        
        for doc in self.documents:
            content = doc.get("content", "").lower()
            
            # Apply SKU filter if provided
            if sku_filter and sku_filter.lower() not in content:
                continue
            
            # Calculate simple relevance score based on keyword matches
            score = sum(1 for word in query_words if word in content) / len(query_words) if query_words else 0
            
            if score > 0:
                results.append({
                    "chunk_id": doc["chunk_id"],
                    "document_name": doc["document_name"],
                    "page_number": doc.get("page_number"),
                    "content": doc["content"],
                    "score": score,
                    "metadata": doc.get("metadata", {})
                })
        
        # Sort by score and return top_k
        results.sort(key=lambda x: x["score"], reverse=True)
        results = results[:top_k]
        
        logger.info(f"Found {len(results)} relevant chunks for query")
        return results
    
    async def get_document_count(self) -> int:
        """Get total number of document chunks"""
        return len(self.documents)
    
    async def list_documents(self) -> List[str]:
        """List all unique document names"""
        if not self._connected:
            return []
        
        document_names = list(set(doc["document_name"] for doc in self.documents))
        return sorted(document_names)
    
    async def delete_document(self, document_name: str) -> int:
        """Delete all chunks for a specific document"""
        if not self._connected:
            return 0
        
        initial_count = len(self.documents)
        self.documents = [doc for doc in self.documents if doc["document_name"] != document_name]
        deleted_count = initial_count - len(self.documents)
        
        logger.info(f"Deleted {deleted_count} chunks for document {document_name}")
        return deleted_count


# Create global instance
simple_vector_store = SimpleVectorStore() 