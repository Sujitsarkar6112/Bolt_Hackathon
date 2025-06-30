#!/usr/bin/env python3
"""
Local document watcher for filesystem events
Automatically triggers document re-indexing on changes
"""

import asyncio
import logging
import os
import hashlib
from pathlib import Path
from typing import Dict, Any, Optional, Set
from datetime import datetime
import aiofiles
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import structlog

from .config import settings
from .services.document_processor import DocumentProcessor

logger = structlog.get_logger()


class DocumentEventHandler(FileSystemEventHandler):
    """File system event handler for document changes"""
    
    def __init__(self, processor: 'DocumentWatcher'):
        self.processor = processor
        self.debounce_delay = 2.0  # seconds
        self.pending_files: Dict[str, float] = {}
    
    def on_created(self, event):
        if not event.is_directory and self._is_supported_file(event.src_path):
            self._schedule_processing(event.src_path)
    
    def on_modified(self, event):
        if not event.is_directory and self._is_supported_file(event.src_path):
            self._schedule_processing(event.src_path)
    
    def on_deleted(self, event):
        if not event.is_directory and self._is_supported_file(event.src_path):
            asyncio.create_task(self.processor.handle_file_deletion(event.src_path))
    
    def _is_supported_file(self, file_path: str) -> bool:
        """Check if file extension is supported"""
        return Path(file_path).suffix.lower() in settings.supported_extensions
    
    def _schedule_processing(self, file_path: str):
        """Schedule file processing with debouncing"""
        current_time = asyncio.get_event_loop().time()
        self.pending_files[file_path] = current_time + self.debounce_delay
        
        # Schedule processing after debounce delay
        asyncio.create_task(self._process_after_delay(file_path, current_time))
    
    async def _process_after_delay(self, file_path: str, scheduled_time: float):
        """Process file after debounce delay"""
        await asyncio.sleep(self.debounce_delay)
        
        # Check if file is still scheduled for this time
        if (file_path in self.pending_files and 
            self.pending_files[file_path] <= asyncio.get_event_loop().time()):
            
            del self.pending_files[file_path]
            await self.processor.handle_file_change(file_path)


class DocumentWatcher:
    """Main document watcher for local filesystem events"""
    
    def __init__(self):
        self.document_processor = DocumentProcessor()
        self.fs_observer: Optional[Observer] = None
        self.processed_files: Set[str] = set()
    
    async def start(self):
        """Start document watching"""
        logger.info("Starting local document watcher")
        
        # Start filesystem watcher
        await self._start_filesystem_watcher()
        
        logger.info("Document watcher started successfully")
    
    async def stop(self):
        """Stop document watching"""
        logger.info("Stopping document watcher")
        
        # Stop filesystem watcher
        if self.fs_observer:
            self.fs_observer.stop()
            self.fs_observer.join()
        
        logger.info("Document watcher stopped")
    
    async def _start_filesystem_watcher(self):
        """Start filesystem event watcher"""
        try:
            # Ensure documents directory exists
            os.makedirs(settings.documents_path, exist_ok=True)
            
            # Create and start observer
            event_handler = DocumentEventHandler(self)
            self.fs_observer = Observer()
            self.fs_observer.schedule(
                event_handler,
                settings.documents_path,
                recursive=True
            )
            self.fs_observer.start()
            
            logger.info("Filesystem watcher started", 
                       path=settings.documents_path)
            
        except Exception as e:
            logger.error("Failed to start filesystem watcher", error=str(e))
    
    async def handle_file_change(self, file_path: str):
        """Handle filesystem file change"""
        try:
            # Check if file was recently processed to avoid duplicates
            file_id = f"fs:{file_path}"
            if file_id in self.processed_files:
                return
            
            self.processed_files.add(file_id)
            
            logger.info("Processing file change", file_path=file_path)
            
            # Process the file
            await self.document_processor.process_file(file_path)
            
            # Remove from processed set after delay
            asyncio.create_task(self._remove_from_processed(file_id, 300))  # 5 minutes
            
        except Exception as e:
            logger.error("Error handling file change", 
                        error=str(e),
                        file_path=file_path)
    
    async def handle_file_deletion(self, file_path: str):
        """Handle filesystem file deletion"""
        try:
            document_name = Path(file_path).name
            
            logger.info("Processing file deletion", 
                       file_path=file_path,
                       document_name=document_name)
            
            # Delete from vector store
            from .services.vector_store import vector_store
            deleted_count = await vector_store.delete_document(document_name)
            
            logger.info("File deletion processed", 
                       document_name=document_name,
                       deleted_chunks=deleted_count)
            
        except Exception as e:
            logger.error("Error handling file deletion", 
                        error=str(e),
                        file_path=file_path)
    
    async def _remove_from_processed(self, file_id: str, delay: int):
        """Remove file from processed set after delay"""
        await asyncio.sleep(delay)
        self.processed_files.discard(file_id)


async def main():
    """Main function for standalone execution"""
    watcher = DocumentWatcher()
    
    try:
        await watcher.start()
        
        # Keep running until interrupted
        while True:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("Received interrupt signal")
    finally:
        await watcher.stop()


if __name__ == "__main__":
    asyncio.run(main())