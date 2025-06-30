from fastapi import FastAPI, HTTPException, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import logging
from datetime import datetime
from contextlib import asynccontextmanager

from .config import settings
from .models import AskRequest, AskResponse, DocumentSource, HealthResponse
from .services.document_processor import DocumentProcessor
from .services.simple_vector_store import simple_vector_store as vector_store
from .services.rag_chain import RAGChain
from .utils.logging_config import setup_logging

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)

# Global services
document_processor = DocumentProcessor()
rag_chain = RAGChain()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management"""
    logger.info("Starting RAG service")
    
    # Initialize services
    await vector_store.connect()
    await rag_chain.initialize(vector_store)
    
    # Start document watching
    await document_processor.start_watching()
    
    yield
    
    # Cleanup
    logger.info("Shutting down RAG service")
    await document_processor.stop_watching()
    await vector_store.disconnect()


# Create FastAPI application
app = FastAPI(
    title="RAG Service",
    description="Retrieval-Augmented Generation service with local FAISS vector search",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    try:
        # Check vector store connection
        vector_store_healthy = await vector_store.is_connected()
        
        # Check document count
        doc_count = await vector_store.get_document_count()
        
        status = "healthy" if vector_store_healthy else "degraded"
        
        return HealthResponse(
            status=status,
            timestamp=datetime.utcnow().isoformat(),
            vector_store_connected=vector_store_healthy,
            documents_indexed=doc_count,
            embeddings_model=settings.openai_embedding_model
        )
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        raise HTTPException(status_code=503, detail="Service unhealthy")


@app.post("/ask", response_model=AskResponse)
async def ask_question(request: AskRequest):
    """Ask a question and get grounded answer with sources"""
    try:
        logger.info(f"Processing question: {request.query[:100]}...")
        
        # Generate answer using RAG chain
        response = await rag_chain.ask(
            query=request.query,
            sku=request.sku,
            top_k=request.top_k
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Failed to process question: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to process question")


@app.post("/ingest")
async def trigger_ingestion(background_tasks: BackgroundTasks):
    """Trigger document ingestion"""
    try:
        background_tasks.add_task(document_processor.process_all_documents)
        return {
            "message": "Document ingestion initiated",
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to trigger ingestion: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to trigger ingestion")


@app.get("/documents")
async def list_documents():
    """List all indexed documents"""
    try:
        documents = await vector_store.list_documents()
        return {
            "documents": documents,
            "count": len(documents)
        }
    except Exception as e:
        logger.error(f"Failed to list documents: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to list documents")


@app.delete("/documents/{document_name}")
async def delete_document(document_name: str):
    """Delete a specific document from the vector store"""
    try:
        deleted_count = await vector_store.delete_document(document_name)
        return {
            "message": f"Deleted {deleted_count} chunks for document {document_name}",
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to delete document: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to delete document")


@app.get("/search")
async def search_documents(
    query: str,
    top_k: int = Query(default=4, ge=1, le=20),
    sku: Optional[str] = None
):
    """Search documents without generating an answer"""
    try:
        results = await vector_store.similarity_search(
            query=query,
            top_k=top_k,
            sku_filter=sku
        )
        
        return {
            "query": query,
            "results": results,
            "count": len(results)
        }
    except Exception as e:
        logger.error(f"Failed to search documents: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to search documents")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8003,
        log_level=settings.log_level.lower(),
        reload=settings.environment == "development"
    )