import logging
import os
import pickle
from typing import List, Optional, Dict, Any
from datetime import datetime
from pathlib import Path

import faiss
import numpy as np
from langchain.vectorstores import FAISS
from langchain.embeddings.openai import OpenAIEmbeddings
from langchain.schema import Document

from ..config import settings
from ..models import DocumentChunk

logger = logging.getLogger(__name__)


class LocalVectorStore:
    """Local FAISS-based vector store implementation"""
    
    def __init__(self):
        self.vector_db: Optional[FAISS] = None
        self.embeddings = OpenAIEmbeddings(
            openai_api_key=settings.openai_api_key,
            model=settings.openai_embedding_model
        )
        self.index_path = Path(settings.faiss_index_path)
        self.metadata_path = self.index_path / "metadata.pkl"
        self._connected = False
        self.document_metadata: Dict[str, Dict[str, Any]] = {}
    
    async def connect(self):
        """Initialize vector store and load existing index if present"""
        try:
            # Ensure index directory exists
            self.index_path.mkdir(parents=True, exist_ok=True)
            
            # Load existing index if present
            if self._index_exists():
                await self._load_index()
                logger.info(f"Loaded existing FAISS index from {self.index_path}")
            else:
                # Initialize empty index
                await self._initialize_empty_index()
                logger.info("Initialized empty FAISS index")
            
            self._connected = True
            logger.info("LocalVectorStore connected successfully")
            
        except Exception as e:
            logger.error(f"Failed to connect LocalVectorStore: {e}")
            self._connected = False
            raise
    
    async def disconnect(self):
        """Save index and cleanup"""
        if self.vector_db and self._connected:
            await self._save_index()
        
        self._connected = False
        logger.info("LocalVectorStore disconnected")
    
    async def is_connected(self) -> bool:
        """Check if vector store is connected"""
        return self._connected and self.vector_db is not None
    
    def _index_exists(self) -> bool:
        """Check if FAISS index files exist"""
        return (self.index_path / "index.faiss").exists() and (self.index_path / "index.pkl").exists()
    
    async def _load_index(self):
        """Load existing FAISS index from disk"""
        try:
            self.vector_db = FAISS.load_local(
                str(self.index_path),
                self.embeddings
            )
            
            # Load metadata
            if self.metadata_path.exists():
                with open(self.metadata_path, 'rb') as f:
                    self.document_metadata = pickle.load(f)
            
        except Exception as e:
            logger.error(f"Failed to load FAISS index: {e}")
            await self._initialize_empty_index()
    
    async def _initialize_empty_index(self):
        """Initialize empty FAISS index"""
        # Create a dummy document to initialize the index
        dummy_doc = Document(page_content="dummy", metadata={"source": "init"})
        self.vector_db = FAISS.from_documents([dummy_doc], self.embeddings)
        
        # Remove the dummy document
        self.vector_db.delete([0])
        
        self.document_metadata = {}
    
    async def _save_index(self):
        """Save FAISS index to disk"""
        try:
            if self.vector_db:
                self.vector_db.save_local(str(self.index_path))
                
                # Save metadata
                with open(self.metadata_path, 'wb') as f:
                    pickle.dump(self.document_metadata, f)
                
                logger.debug(f"Saved FAISS index to {self.index_path}")
        except Exception as e:
            logger.error(f"Failed to save FAISS index: {e}")
    
    async def store_document_chunks(self, chunks: List[DocumentChunk]):
        """Store document chunks in vector database"""
        if not self.vector_db:
            raise RuntimeError("Vector store not connected")
        
        if not chunks:
            return
        
        # Delete existing chunks for the same document
        document_name = chunks[0].document_name
        await self.delete_document(document_name)
        
        # Convert chunks to LangChain documents
        documents = []
        for chunk in chunks:
            doc = Document(
                page_content=chunk.content,
                metadata={
                    "source": chunk.document_name,
                    "chunk_id": chunk.chunk_id,
                    "page_number": chunk.page_number,
                    "created_at": chunk.created_at.isoformat(),
                    **chunk.metadata
                }
            )
            documents.append(doc)
        
        # Add documents to FAISS index
        if hasattr(self.vector_db, 'add_documents'):
            self.vector_db.add_documents(documents)
        else:
            # Fallback for older versions
            texts = [doc.page_content for doc in documents]
            metadatas = [doc.metadata for doc in documents]
            self.vector_db.add_texts(texts, metadatas)
        
        # Update document metadata
        self.document_metadata[document_name] = {
            "chunk_count": len(chunks),
            "last_updated": datetime.utcnow().isoformat(),
            "file_path": chunks[0].metadata.get("file_path", ""),
            "file_size": chunks[0].metadata.get("file_size", 0)
        }
        
        # Save index after adding documents
        await self._save_index()
        
        logger.info(f"Stored {len(chunks)} chunks for document {document_name}")
    
    async def similarity_search(
        self,
        query: str,
        top_k: int = 4,
        sku_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Perform similarity search using FAISS"""
        if not self.vector_db:
            raise RuntimeError("Vector store not connected")
        
        try:
            # Perform similarity search
            docs = self.vector_db.similarity_search_with_score(query, k=top_k * 2)  # Get more for filtering
            
            # Format results
            results = []
            for doc, score in docs:
                # Apply SKU filter if specified
                if sku_filter:
                    content_lower = doc.page_content.lower()
                    if sku_filter.lower() not in content_lower:
                        continue
                
                result = {
                    "chunk_id": doc.metadata.get("chunk_id", ""),
                    "document_name": doc.metadata.get("source", ""),
                    "page_number": doc.metadata.get("page_number"),
                    "content": doc.page_content,
                    "score": float(score),
                    "metadata": doc.metadata
                }
                results.append(result)
                
                # Stop when we have enough results
                if len(results) >= top_k:
                    break
            
            logger.info(f"Found {len(results)} similar chunks for query")
            return results
            
        except Exception as e:
            logger.error(f"Similarity search failed: {e}")
            return []
    
    async def get_document_count(self) -> int:
        """Get total number of document chunks indexed"""
        if not self.vector_db:
            return 0
        
        try:
            # Get total number of vectors in index
            if hasattr(self.vector_db, 'index') and hasattr(self.vector_db.index, 'ntotal'):
                return self.vector_db.index.ntotal
            else:
                # Fallback: count from metadata
                return sum(meta.get("chunk_count", 0) for meta in self.document_metadata.values())
        except Exception as e:
            logger.error(f"Failed to get document count: {e}")
            return 0
    
    async def list_documents(self) -> List[str]:
        """List all unique document names"""
        return sorted(self.document_metadata.keys())
    
    async def delete_document(self, document_name: str) -> int:
        """Delete all chunks for a specific document"""
        if not self.vector_db:
            return 0
        
        try:
            # Get all document IDs for this document
            if hasattr(self.vector_db, 'docstore') and hasattr(self.vector_db, 'index_to_docstore_id'):
                # Find documents to delete
                ids_to_delete = []
                for i, doc_id in self.vector_db.index_to_docstore_id.items():
                    doc = self.vector_db.docstore.search(doc_id)
                    if doc and doc.metadata.get("source") == document_name:
                        ids_to_delete.append(doc_id)
                
                # Delete documents
                if ids_to_delete:
                    self.vector_db.delete(ids_to_delete)
                    deleted_count = len(ids_to_delete)
                else:
                    deleted_count = 0
            else:
                # For simpler implementations, rebuild index without the document
                deleted_count = self.document_metadata.get(document_name, {}).get("chunk_count", 0)
                await self._rebuild_index_without_document(document_name)
            
            # Remove from metadata
            if document_name in self.document_metadata:
                del self.document_metadata[document_name]
            
            # Save updated index
            await self._save_index()
            
            logger.info(f"Deleted {deleted_count} chunks for document {document_name}")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Failed to delete document {document_name}: {e}")
            return 0
    
    async def _rebuild_index_without_document(self, document_name: str):
        """Rebuild index excluding a specific document"""
        if not self.vector_db:
            return
        
        try:
            # Get all documents except the one to delete
            all_docs = []
            if hasattr(self.vector_db, 'docstore') and hasattr(self.vector_db, 'index_to_docstore_id'):
                for doc_id in self.vector_db.index_to_docstore_id.values():
                    doc = self.vector_db.docstore.search(doc_id)
                    if doc and doc.metadata.get("source") != document_name:
                        all_docs.append(doc)
            
            # Rebuild index with remaining documents
            if all_docs:
                self.vector_db = FAISS.from_documents(all_docs, self.embeddings)
            else:
                await self._initialize_empty_index()
                
        except Exception as e:
            logger.error(f"Failed to rebuild index: {e}")
    
    async def get_collection_stats(self) -> Dict[str, Any]:
        """Get collection statistics"""
        try:
            total_documents = len(self.document_metadata)
            total_chunks = await self.get_document_count()
            avg_chunks_per_doc = total_chunks / total_documents if total_documents > 0 else 0
            
            return {
                "total_documents": total_documents,
                "total_chunks": total_chunks,
                "avg_chunks_per_doc": avg_chunks_per_doc,
                "index_path": str(self.index_path),
                "index_size_mb": self._get_index_size_mb()
            }
        except Exception as e:
            logger.error(f"Failed to get collection stats: {e}")
            return {}
    
    def _get_index_size_mb(self) -> float:
        """Get index size in MB"""
        try:
            total_size = 0
            for file_path in self.index_path.glob("*"):
                if file_path.is_file():
                    total_size += file_path.stat().st_size
            return total_size / (1024 * 1024)  # Convert to MB
        except Exception:
            return 0.0


# Global vector store instance
vector_store = LocalVectorStore()