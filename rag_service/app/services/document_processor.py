import asyncio
import logging
import os
import hashlib
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
import aiofiles
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import PyPDF2
from langchain.text_splitter import RecursiveCharacterTextSplitter

from ..config import settings
from ..models import DocumentChunk, DocumentMetadata
from .vector_store import VectorStore
from .embeddings import EmbeddingService

logger = logging.getLogger(__name__)


class DocumentFileHandler(FileSystemEventHandler):
    """File system event handler for document changes"""
    
    def __init__(self, processor):
        self.processor = processor
    
    def on_created(self, event):
        if not event.is_directory:
            asyncio.create_task(self.processor.process_file(event.src_path))
    
    def on_modified(self, event):
        if not event.is_directory:
            asyncio.create_task(self.processor.process_file(event.src_path))


class DocumentProcessor:
    """Service for processing and watching documents"""
    
    def __init__(self):
        self.vector_store = VectorStore()
        self.embedding_service = EmbeddingService()
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
            separators=["\n\n", "\n", ". ", " ", ""]
        )
        self.observer: Optional[Observer] = None
        self.processed_files: Dict[str, str] = {}  # filepath -> hash
    
    async def start_watching(self):
        """Start watching the documents directory"""
        if not settings.enable_auto_ingestion:
            logger.info("Auto-ingestion disabled")
            return
        
        # Ensure documents directory exists
        os.makedirs(settings.documents_path, exist_ok=True)
        
        # Process existing files
        await self.process_all_documents()
        
        # Start file watcher
        if self.observer is None:
            event_handler = DocumentFileHandler(self)
            self.observer = Observer()
            self.observer.schedule(
                event_handler,
                settings.documents_path,
                recursive=True
            )
            self.observer.start()
            logger.info(f"Started watching directory: {settings.documents_path}")
    
    async def stop_watching(self):
        """Stop watching the documents directory"""
        if self.observer:
            self.observer.stop()
            self.observer.join()
            self.observer = None
            logger.info("Stopped watching documents directory")
    
    async def process_all_documents(self):
        """Process all documents in the directory"""
        logger.info("Processing all documents in directory")
        
        docs_path = Path(settings.documents_path)
        if not docs_path.exists():
            logger.warning(f"Documents directory does not exist: {docs_path}")
            return
        
        for file_path in docs_path.rglob("*"):
            if file_path.is_file() and file_path.suffix.lower() in settings.supported_extensions:
                await self.process_file(str(file_path))
    
    async def process_file(self, file_path: str):
        """Process a single file"""
        try:
            file_path = Path(file_path)
            
            # Check if file has been modified
            file_hash = await self._get_file_hash(file_path)
            if file_path.name in self.processed_files and self.processed_files[file_path.name] == file_hash:
                logger.debug(f"File unchanged, skipping: {file_path.name}")
                return
            
            logger.info(f"Processing file: {file_path.name}")
            
            # Extract text based on file type
            if file_path.suffix.lower() == '.pdf':
                text = await self._extract_pdf_text(file_path)
            else:
                text = await self._extract_text_file(file_path)
            
            if not text.strip():
                logger.warning(f"No text extracted from: {file_path.name}")
                return
            
            # Split into chunks
            chunks = self.text_splitter.split_text(text)
            logger.info(f"Split {file_path.name} into {len(chunks)} chunks")
            
            # Create document chunks with embeddings
            document_chunks = []
            for i, chunk_text in enumerate(chunks):
                # Generate embedding
                embedding = await self.embedding_service.get_embedding(chunk_text)
                
                # Create chunk
                chunk = DocumentChunk(
                    chunk_id=f"{file_path.stem}_{i}_{hashlib.md5(chunk_text.encode()).hexdigest()[:8]}",
                    document_name=file_path.name,
                    page_number=None,  # Could be enhanced to track page numbers
                    content=chunk_text,
                    embedding=embedding,
                    metadata={
                        "file_path": str(file_path),
                        "chunk_index": i,
                        "total_chunks": len(chunks),
                        "file_size": file_path.stat().st_size,
                        "file_extension": file_path.suffix.lower()
                    },
                    created_at=datetime.utcnow()
                )
                document_chunks.append(chunk)
            
            # Store in vector database
            await self.vector_store.store_document_chunks(document_chunks)
            
            # Update processed files tracking
            self.processed_files[file_path.name] = file_hash
            
            logger.info(f"Successfully processed {file_path.name} with {len(chunks)} chunks")
            
        except Exception as e:
            logger.error(f"Failed to process file {file_path}: {str(e)}")
    
    async def _get_file_hash(self, file_path: Path) -> str:
        """Get MD5 hash of file for change detection"""
        hash_md5 = hashlib.md5()
        async with aiofiles.open(file_path, 'rb') as f:
            async for chunk in self._read_chunks(f):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    
    async def _read_chunks(self, file_obj, chunk_size: int = 8192):
        """Read file in chunks asynchronously"""
        while True:
            chunk = await file_obj.read(chunk_size)
            if not chunk:
                break
            yield chunk
    
    async def _extract_pdf_text(self, file_path: Path) -> str:
        """Extract text from PDF file"""
        try:
            text = ""
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                for page_num, page in enumerate(pdf_reader.pages):
                    page_text = page.extract_text()
                    if page_text:
                        text += f"\n\n--- Page {page_num + 1} ---\n\n"
                        text += page_text
            return text
        except Exception as e:
            logger.error(f"Failed to extract PDF text from {file_path}: {str(e)}")
            return ""
    
    async def _extract_text_file(self, file_path: Path) -> str:
        """Extract text from text/markdown file"""
        try:
            async with aiofiles.open(file_path, 'r', encoding='utf-8') as file:
                return await file.read()
        except UnicodeDecodeError:
            # Try with different encoding
            try:
                async with aiofiles.open(file_path, 'r', encoding='latin-1') as file:
                    return await file.read()
            except Exception as e:
                logger.error(f"Failed to read text file {file_path}: {str(e)}")
                return ""
        except Exception as e:
            logger.error(f"Failed to extract text from {file_path}: {str(e)}")
            return ""