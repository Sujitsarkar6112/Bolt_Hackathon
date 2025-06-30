#!/usr/bin/env python3
"""
MongoDB Change Streams watcher for sales data
Triggers incremental model retraining on SKU data changes
"""

import asyncio
import logging
from typing import Dict, Any, Optional
from datetime import datetime
import json
from motor.motor_asyncio import AsyncIOMotorClient
from aiokafka import AIOKafkaProducer
from pymongo.errors import PyMongoError
import structlog

from .config import settings
from utils.db import ensure_connection, get_collection

logger = structlog.get_logger()


class SalesChangeStreamWatcher:
    """Watches MongoDB change streams and triggers retraining events"""
    
    def __init__(self):
        self.client: Optional[AsyncIOMotorClient] = None
        self.producer: Optional[AIOKafkaProducer] = None
        self.running = False
        self.change_stream = None
        
    async def start(self) -> None:
        """Start watching sales collection for changes"""
        logger.info("Starting sales change stream watcher")
        
        try:
            # Connect to MongoDB
            await ensure_connection(settings.mongodb_url)
            self.sales_collection = await get_collection("sales_db", "raw_sales")
            
            # Connect to Kafka producer
            self.producer = AIOKafkaProducer(
                bootstrap_servers=settings.kafka_bootstrap_servers,
                value_serializer=lambda x: json.dumps(x).encode('utf-8'),
                key_serializer=lambda x: x.encode('utf-8') if x else None,
                enable_idempotence=True,
                acks='all'
            )
            await self.producer.start()
            
            self.running = True
            
            # Start change stream monitoring
            await self._watch_changes()
            
        except Exception as e:
            logger.error("Failed to start change stream watcher", error=str(e))
            raise
    
    async def stop(self) -> None:
        """Stop the change stream watcher"""
        logger.info("Stopping sales change stream watcher")
        self.running = False
        
        if self.change_stream:
            await self.change_stream.close()
        
        if self.producer:
            await self.producer.stop()
    
    async def _watch_changes(self) -> None:
        """Watch for changes in sales collection"""
        try:
            # Create change stream with pipeline to filter relevant changes
            pipeline = [
                {
                    "$match": {
                        "operationType": {"$in": ["insert", "update", "replace"]},
                        "fullDocument.sku": {"$exists": True}
                    }
                }
            ]
            
            # Start change stream
            self.change_stream = self.sales_collection.native.watch(
                pipeline,
                full_document='updateLookup',
                resume_after=None
            )
            
            logger.info("Change stream established for sales collection")
            
            # Process changes
            async for change in self.change_stream:
                if not self.running:
                    break
                
                await self._process_change(change)
                
        except PyMongoError as e:
            logger.error("MongoDB change stream error", error=str(e))
            if self.running:
                # Attempt to reconnect after delay
                await asyncio.sleep(5)
                await self._watch_changes()
        except Exception as e:
            logger.error("Unexpected error in change stream", error=str(e))
            raise
    
    async def _process_change(self, change: Dict[str, Any]) -> None:
        """Process a single change event"""
        try:
            operation_type = change.get("operationType")
            full_document = change.get("fullDocument", {})
            sku = full_document.get("sku")
            
            if not sku:
                return
            
            logger.debug("Processing change event", 
                        operation_type=operation_type,
                        sku=sku)
            
            # Determine if this change warrants retraining
            should_retrain = await self._should_trigger_retrain(sku, change)
            
            if should_retrain:
                await self._send_retrain_event(sku, change)
            
        except Exception as e:
            logger.error("Error processing change event", error=str(e))
    
    async def _should_trigger_retrain(self, sku: str, change: Dict[str, Any]) -> bool:
        """
        Determine if change should trigger model retraining
        
        Args:
            sku: Product SKU
            change: MongoDB change event
            
        Returns:
            True if retraining should be triggered
        """
        # Check if enough new data points have accumulated
        recent_count = await self.sales_collection.count_documents({
            "sku": sku,
            "processed_at": {"$gte": datetime.utcnow().timestamp() - 3600}  # Last hour
        })
        
        # Trigger retraining if:
        # 1. More than 10 new data points in last hour
        # 2. Or if it's been more than 24 hours since last retrain
        if recent_count >= 10:
            logger.info("Triggering retrain due to data volume", 
                       sku=sku, 
                       recent_count=recent_count)
            return True
        
        # Check last retrain time (would be stored in models collection)
        # For now, use simple time-based trigger
        return False
    
    async def _send_retrain_event(self, sku: str, change: Dict[str, Any]) -> None:
        """Send retraining event to Kafka"""
        try:
            retrain_event = {
                "sku": sku,
                "trigger": "data_change",
                "timestamp": datetime.utcnow().isoformat(),
                "change_id": str(change.get("_id", {})),
                "operation_type": change.get("operationType"),
                "priority": "normal",
                "metadata": {
                    "source": "change_stream",
                    "collection": "raw_sales"
                }
            }
            
            # Send to retrain topic
            await self.producer.send(
                "model_retrain",
                value=retrain_event,
                key=sku
            )
            
            logger.info("Retrain event sent", 
                       sku=sku,
                       trigger="data_change")
            
        except Exception as e:
            logger.error("Failed to send retrain event", 
                        error=str(e),
                        sku=sku)


async def main():
    """Main function for standalone execution"""
    watcher = SalesChangeStreamWatcher()
    
    try:
        await watcher.start()
    except KeyboardInterrupt:
        logger.info("Received interrupt signal")
    finally:
        await watcher.stop()


if __name__ == "__main__":
    asyncio.run(main())