from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application configuration"""
    
    # Service Configuration
    service_name: str = "rag_service"
    environment: str = "development"
    log_level: str = "INFO"
    
    # MongoDB Atlas Configuration
    mongodb_atlas_uri: str = "mongodb+srv://username:password@cluster.mongodb.net/"
    mongodb_database: str = "enterprise_rag"
    mongodb_collection: str = "docs_vectors"
    
    # OpenAI Configuration
    openai_api_key: str = ""
    openai_embedding_model: str = "text-embedding-3-small"
    openai_chat_model: str = "gpt-3.5-turbo"
    openai_max_tokens: int = 1000
    openai_temperature: float = 0.1
    
    # Document Processing
    documents_path: str = "./enterprise_docs"
    chunk_size: int = 1000
    chunk_overlap: int = 200
    supported_extensions: list = [".pdf", ".txt", ".md"]
    
    # FAISS Configuration
    faiss_index_path: str = "./faiss_index"
    
    # Vector Search Configuration
    vector_index_name: str = "vector_index"
    embedding_dimension: int = 1536  # text-embedding-3-small dimension
    similarity_threshold: float = 0.7
    
    # RAG Configuration
    top_k_default: int = 4
    max_context_length: int = 4000
    citation_style: str = "ieee"  # ieee, apa, mla
    
    # File Watching
    watch_interval: int = 30  # seconds
    enable_auto_ingestion: bool = True
    
    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()