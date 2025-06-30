#!/usr/bin/env python3
"""
CLI script for document ingestion
Usage: python ingest_docs.py [--force] [--file FILE_PATH]
"""

import asyncio
import argparse
import logging
import sys
import os
from pathlib import Path

# Add app to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.services.document_processor import DocumentProcessor
from app.services.vector_store import vector_store
from app.utils.logging_config import setup_logging
from app.config import settings

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)


async def ingest_all_documents(force: bool = False):
    """Ingest all documents in the directory"""
    logger.info("Starting document ingestion")
    
    try:
        # Initialize services
        document_processor = DocumentProcessor()
        
        # Connect to vector store
        await vector_store.connect()
        
        if force:
            logger.info("Force mode: clearing existing documents")
            # Get all documents and delete them
            documents = await vector_store.list_documents()
            for doc in documents:
                await vector_store.delete_document(doc)
        
        # Process all documents
        await document_processor.process_all_documents()
        
        # Get final stats
        stats = await vector_store.get_collection_stats()
        logger.info(f"Ingestion completed. Stats: {stats}")
        
    except Exception as e:
        logger.error(f"Document ingestion failed: {e}")
        sys.exit(1)
    
    finally:
        # Cleanup
        try:
            await vector_store.disconnect()
        except:
            pass


async def ingest_single_file(file_path: str):
    """Ingest a single file"""
    logger.info(f"Ingesting single file: {file_path}")
    
    if not os.path.exists(file_path):
        logger.error(f"File not found: {file_path}")
        sys.exit(1)
    
    try:
        # Initialize services
        document_processor = DocumentProcessor()
        
        # Connect to vector store
        await vector_store.connect()
        
        # Process single file
        await document_processor.process_file(file_path)
        
        logger.info(f"Successfully ingested: {file_path}")
        
    except Exception as e:
        logger.error(f"Failed to ingest file {file_path}: {e}")
        sys.exit(1)
    
    finally:
        # Cleanup
        try:
            await vector_store.disconnect()
        except:
            pass


async def list_documents():
    """List all indexed documents"""
    try:
        await vector_store.connect()
        
        documents = await vector_store.list_documents()
        stats = await vector_store.get_collection_stats()
        
        print(f"\nIndexed Documents ({len(documents)} total):")
        print("-" * 50)
        for doc in documents:
            print(f"  • {doc}")
        
        print(f"\nCollection Statistics:")
        print(f"  • Total documents: {stats.get('total_documents', 0)}")
        print(f"  • Total chunks: {stats.get('total_chunks', 0)}")
        print(f"  • Avg chunks per doc: {stats.get('avg_chunks_per_doc', 0):.1f}")
        print(f"  • Index size: {stats.get('index_size_mb', 0):.1f} MB")
        
    except Exception as e:
        logger.error(f"Failed to list documents: {e}")
        sys.exit(1)
    
    finally:
        try:
            await vector_store.disconnect()
        except:
            pass


def main():
    """Main CLI function"""
    parser = argparse.ArgumentParser(description="Document ingestion CLI")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-ingestion by clearing existing documents"
    )
    parser.add_argument(
        "--file",
        type=str,
        help="Ingest a specific file instead of all documents"
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List all indexed documents"
    )
    
    args = parser.parse_args()
    
    # Validate configuration
    if not settings.openai_api_key:
        logger.error("OpenAI API key not configured. Set OPENAI_API_KEY environment variable.")
        sys.exit(1)
    
    # Ensure documents directory exists
    if not args.list:
        os.makedirs(settings.documents_path, exist_ok=True)
        logger.info(f"Documents directory: {settings.documents_path}")
    
    # Run appropriate function
    if args.list:
        asyncio.run(list_documents())
    elif args.file:
        asyncio.run(ingest_single_file(args.file))
    else:
        asyncio.run(ingest_all_documents(args.force))


if __name__ == "__main__":
    main()