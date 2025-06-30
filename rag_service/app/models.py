from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Literal
from datetime import datetime


class AskRequest(BaseModel):
    """Request model for asking questions"""
    query: str = Field(..., description="Question to ask")
    sku: Optional[str] = Field(None, description="Optional SKU filter")
    top_k: int = Field(default=4, ge=1, le=20, description="Number of sources to retrieve")


class DocumentSource(BaseModel):
    """Document source with citation information"""
    document: str = Field(..., description="Document filename")
    page: Optional[int] = Field(None, description="Page number")
    chunk_id: str = Field(..., description="Unique chunk identifier")
    relevance_score: float = Field(..., description="Similarity score")
    content: str = Field(..., description="Source content")
    citation: str = Field(..., description="Formatted citation")


class AskResponse(BaseModel):
    """Response model for questions"""
    query: str = Field(..., description="Original question")
    answer: str = Field(..., description="Generated answer")
    sources: List[DocumentSource] = Field(..., description="Source documents")
    sku_filter: Optional[str] = Field(None, description="SKU filter applied")
    timestamp: str = Field(..., description="Response timestamp")
    model_used: str = Field(..., description="LLM model used")
    total_sources: int = Field(..., description="Total sources found")


class HealthResponse(BaseModel):
    """Health check response"""
    status: Literal["healthy", "degraded", "unhealthy"]
    timestamp: str
    vector_store_connected: bool
    documents_indexed: int
    embeddings_model: str


class DocumentChunk(BaseModel):
    """Document chunk for vector storage"""
    chunk_id: str
    document_name: str
    page_number: Optional[int]
    content: str
    embedding: List[float]
    metadata: Dict[str, Any]
    created_at: datetime
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class DocumentMetadata(BaseModel):
    """Document metadata"""
    filename: str
    file_path: str
    file_size: int
    created_at: datetime
    modified_at: datetime
    processed_at: Optional[datetime] = None
    chunk_count: int = 0
    status: Literal["pending", "processing", "completed", "error"] = "pending"
    error_message: Optional[str] = None