#!/usr/bin/env python3
"""
Document watcher for filesystem and S3 events
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
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
import structlog

from .config import settings
from .services.document_processor import DocumentProcessor
from .services.vector_store import VectorStore

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


class S3EventWatcher:
    """Watches S3 bucket for document changes via SQS notifications"""
    
    def __init__(self, processor: 'DocumentWatcher'):
        self.processor = processor
        self.s3_client = None
        self.sqs_client = None
        self.queue_url = None
        self.running = False
    
    async def start(self):
        """Start S3 event watching"""
        if not settings.s3_bucket_name or not settings.sqs_queue_url:
            logger.info("S3 watching disabled - missing configuration")
            return
        
        try:
            # Initialize AWS clients
            self.s3_client = boto3.client(
                's3',
                aws_access_key_id=settings.aws_access_key_id,
                aws_secret_access_key=settings.aws_secret_access_key,
                region_name=settings.aws_region
            )
            
            self.sqs_client = boto3.client(
                'sqs',
                aws_access_key_id=settings.aws_access_key_id,
                aws_secret_access_key=settings.aws_secret_access_key,
                region_name=settings.aws_region
            )
            
            self.queue_url = settings.sqs_queue_url
            self.running = True
            
            logger.info("S3 event watcher started", 
                       bucket=settings.s3_bucket_name,
                       queue=settings.sqs_queue_url)
            
            # Start polling SQS for S3 events
            await self._poll_s3_events()
            
        except (NoCredentialsError, ClientError) as e:
            logger.error("Failed to initialize S3 watcher", error=str(e))
        except Exception as e:
            logger.error("Unexpected error in S3 watcher", error=str(e))
    
    async def stop(self):
        """Stop S3 event watching"""
        self.running = False
        logger.info("S3 event watcher stopped")
    
    async def _poll_s3_events(self):
        """Poll SQS for S3 events"""
        while self.running:
            try:
                # Receive messages from SQS
                response = self.sqs_client.receive_message(
                    QueueUrl=self.queue_url,
                    MaxNumberOfMessages=10,
                    WaitTimeSeconds=20,  # Long polling
                    MessageAttributeNames=['All']
                )
                
                messages = response.get('Messages', [])
                
                for message in messages:
                    await self._process_s3_event(message)
                    
                    # Delete processed message
                    self.sqs_client.delete_message(
                        QueueUrl=self.queue_url,
                        ReceiptHandle=message['ReceiptHandle']
                    )
                
            except Exception as e:
                logger.error("Error polling S3 events", error=str(e))
                await asyncio.sleep(5)  # Wait before retrying
    
    async def _process_s3_event(self, message: Dict[str, Any]):
        """Process S3 event from SQS message"""
        try:
            import json
            
            # Parse SQS message body
            body = json.loads(message['Body'])
            
            # Handle S3 test events
            if body.get('Type') == 'Notification':
                records = body.get('Records', [])
                
                for record in records:
                    event_name = record.get('eventName', '')
                    s3_info = record.get('s3', {})
                    bucket_name = s3_info.get('bucket', {}).get('name')
                    object_key = s3_info.get('object', {}).get('key')
                    
                    if bucket_name == settings.s3_bucket_name and object_key:
                        await self._handle_s3_object_event(event_name, object_key)
            
        except Exception as e:
            logger.error("Error processing S3 event", error=str(e))
    
    async def _handle_s3_object_event(self, event_name: str, object_key: str):
        """Handle S3 object event"""
        try:
            # Check if file is supported
            if not Path(object_key).suffix.lower() in settings.supported_extensions:
                return
            
            logger.info("Processing S3 event", 
                       event=event_name,
                       object_key=object_key)
            
            if event_name.startswith('ObjectCreated') or event_name.startswith('ObjectModified'):
                # Download and process file
                await self._download_and_process_s3_file(object_key)
            elif event_name.startswith('ObjectRemoved'):
                # Handle file deletion
                await self.processor.handle_s3_file_deletion(object_key)
            
        except Exception as e:
            logger.error("Error handling S3 object event", 
                        error=str(e),
                        object_key=object_key)
    
    async def _download_and_process_s3_file(self, object_key: str):
        """Download S3 file and process it"""
        try:
            # Create temporary file
            temp_file = Path(settings.temp_dir) / f"s3_{hashlib.md5(object_key.encode()).hexdigest()}"
            temp_file.parent.mkdir(exist_ok=True)
            
            # Download file from S3
            self.s3_client.download_file(
                settings.s3_bucket_name,
                object_key,
                str(temp_file)
            )
            
            # Process the downloaded file
            await self.processor.process_file(str(temp_file), source_path=object_key)
            
            # Clean up temporary file
            temp_file.unlink(missing_ok=True)
            
            logger.info("S3 file processed successfully", object_key=object_key)
            
        except Exception as e:
            logger.error("Error downloading/processing S3 file", 
                        error=str(e),
                        object_key=object_key)


class DocumentWatcher:
    """Main document watcher coordinating filesystem and S3 events"""
    
    def __init__(self):
        self.document_processor = DocumentProcessor()
        self.vector_store = VectorStore()
        self.fs_observer: Optional[Observer] = None
        self.s3_watcher = S3EventWatcher(self)
        self.processed_files: Set[str] = set()
    
    async def start(self):
        """Start document watching"""
        logger.info("Starting document watcher")
        
        # Initialize services
        await self.vector_store.connect()
        
        # Start filesystem watcher
        await self._start_filesystem_watcher()
        
        # Start S3 watcher
        await self.s3_watcher.start()
        
        logger.info("Document watcher started successfully")
    
    async def stop(self):
        """Stop document watching"""
        logger.info("Stopping document watcher")
        
        # Stop filesystem watcher
        if self.fs_observer:
            self.fs_observer.stop()
            self.fs_observer.join()
        
        # Stop S3 watcher
        await self.s3_watcher.stop()
        
        # Disconnect services
        await self.vector_store.disconnect()
        
        logger.info("Document watcher stopped")
    
    async def _start_filesystem_watcher(self):
        """Start filesystem event watcher"""
        if not settings.enable_filesystem_watching:
            logger.info("Filesystem watching disabled")
            return
        
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
            deleted_count = await self.vector_store.delete_document(document_name)
            
            logger.info("File deletion processed", 
                       document_name=document_name,
                       deleted_chunks=deleted_count)
            
        except Exception as e:
            logger.error("Error handling file deletion", 
                        error=str(e),
                        file_path=file_path)
    
    async def handle_s3_file_deletion(self, object_key: str):
        """Handle S3 file deletion"""
        try:
            document_name = Path(object_key).name
            
            logger.info("Processing S3 file deletion", 
                       object_key=object_key,
                       document_name=document_name)
            
            # Delete from vector store
            deleted_count = await self.vector_store.delete_document(document_name)
            
            logger.info("S3 file deletion processed", 
                       document_name=document_name,
                       deleted_chunks=deleted_count)
            
        except Exception as e:
            logger.error("Error handling S3 file deletion", 
                        error=str(e),
                        object_key=object_key)
    
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