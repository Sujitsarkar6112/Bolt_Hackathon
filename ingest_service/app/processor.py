import asyncio
import time
from typing import List, Dict, Any
import structlog
from .models import SalesEventModel
from .database import mongodb_client
from .kafka_producer import kafka_producer  # Updated import
from .kafka_consumer import kafka_consumer
from .metrics import metrics, processing_duration
from .proto import sales_event_pb2
from .config import settings

logger = structlog.get_logger()


class SalesEventProcessor:
    """Enhanced processor with exactly-once Kafka semantics"""
    
    def __init__(self):
        self.running = False
        self.batch_buffer: List[Dict[str, Any]] = []
        self.last_flush_time = time.time()
    
    async def start(self) -> None:
        """Start the event processing loop with transactional producer"""
        logger.info("Starting sales event processor with exactly-once semantics")
        self.running = True
        
        # Start metrics server
        metrics.start_metrics_server(settings.metrics_port)
        
        # Connect to services with transactional producer
        await mongodb_client.connect()
        await kafka_producer.connect()  # Transactional producer
        await kafka_consumer.connect()
        
        # Start processing loop
        await self._process_events()
    
    async def stop(self) -> None:
        """Stop the event processing loop"""
        logger.info("Stopping sales event processor")
        self.running = False
        
        # Flush remaining events
        if self.batch_buffer:
            await self._flush_batch()
        
        # Disconnect from services
        await kafka_consumer.disconnect()
        await kafka_producer.disconnect()  # Properly close transactions
        await mongodb_client.disconnect()
    
    async def _process_events(self) -> None:
        """Main event processing loop with transactional guarantees"""
        try:
            async for proto_event in kafka_consumer.consume_messages():
                if not self.running:
                    break
                
                await self._process_single_event(proto_event)
                
                # Check if we should flush the batch
                current_time = time.time()
                should_flush = (
                    len(self.batch_buffer) >= settings.batch_size or
                    current_time - self.last_flush_time >= settings.flush_interval
                )
                
                if should_flush and self.batch_buffer:
                    await self._flush_batch()
                
                # Update metrics
                metrics.update_kafka_lag(kafka_consumer.get_lag_ms())
                metrics.update_uptime()
                
        except Exception as e:
            logger.error("Error in event processing loop", error=str(e))
            raise
    
    async def _process_single_event(self, proto_event: sales_event_pb2.SalesEvent) -> None:
        """Process a single protobuf event"""
        start_time = time.time()
        
        try:
            # Convert protobuf to dict
            event_dict = {
                "sku": proto_event.sku,
                "qty": proto_event.qty,
                "price": proto_event.price,
                "ts": proto_event.ts,
                "event_id": proto_event.event_id if proto_event.event_id else None,
                "processed_at": time.time()
            }
            
            # Validate using Pydantic model
            validated_event = SalesEventModel(**event_dict)
            
            # Add to batch buffer
            self.batch_buffer.append(validated_event.dict())
            
            # Record metrics
            processing_time = time.time() - start_time
            processing_duration.observe(processing_time)
            metrics.record_event_processed('success')
            
            logger.debug("Event processed successfully", 
                        sku=validated_event.sku,
                        processing_time_ms=processing_time * 1000)
            
        except Exception as e:
            metrics.record_event_processed('error')
            logger.error("Failed to process event", 
                        error=str(e),
                        sku=getattr(proto_event, 'sku', 'unknown'))
    
    async def _flush_batch(self) -> None:
        """Flush batch to MongoDB and send success events via Kafka"""
        if not self.batch_buffer:
            return
        
        try:
            batch_size = len(self.batch_buffer)
            logger.debug("Flushing batch to MongoDB", batch_size=batch_size)
            
            # Insert to MongoDB
            inserted_count = await mongodb_client.insert_sales_events_batch(
                self.batch_buffer.copy()
            )
            
            # Send success events to Kafka (transactional)
            for event in self.batch_buffer:
                success_sent = await kafka_producer.send_sales_event(event)
                if not success_sent:
                    logger.warning("Failed to send success event", sku=event["sku"])
            
            # Record metrics
            metrics.record_mongodb_write('success')
            
            # Clear buffer and update timestamp
            self.batch_buffer.clear()
            self.last_flush_time = time.time()
            
            logger.info("Batch flushed successfully with Kafka notifications", 
                       batch_size=batch_size,
                       inserted_count=inserted_count)
            
        except Exception as e:
            metrics.record_mongodb_write('error')
            logger.error("Failed to flush batch", error=str(e))
            # Keep events in buffer for retry
            raise


# Global processor instance
processor = SalesEventProcessor()