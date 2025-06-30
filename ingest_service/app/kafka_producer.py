import asyncio
import logging
from typing import Dict, Any, Optional
from aiokafka import AIOKafkaProducer
from aiokafka.errors import KafkaError
import structlog
import json
from .config import settings
from .proto import sales_event_pb2

logger = structlog.get_logger()


class IdempotentKafkaProducer:
    """Kafka producer with exactly-once semantics and transactional support"""
    
    def __init__(self):
        self.producer: Optional[AIOKafkaProducer] = None
        self._connected = False
        self.transaction_id = f"ingest_service_{settings.service_name}"
    
    async def connect(self) -> None:
        """Initialize transactional Kafka producer"""
        try:
            self.producer = AIOKafkaProducer(
                bootstrap_servers=settings.kafka_bootstrap_servers,
                # Exactly-once semantics configuration
                enable_idempotence=True,
                transactional_id=self.transaction_id,
                acks='all',
                retries=2147483647,  # Max retries
                max_in_flight_requests_per_connection=5,
                # Serialization
                value_serializer=lambda x: json.dumps(x).encode('utf-8'),
                key_serializer=lambda x: x.encode('utf-8') if x else None,
                # Timeouts
                request_timeout_ms=30000,
                delivery_timeout_ms=120000,
                # Batching for performance
                batch_size=16384,
                linger_ms=10,
                compression_type='snappy'
            )
            
            await self.producer.start()
            
            # Initialize transactions
            await self.producer.begin_transaction()
            
            self._connected = True
            logger.info("Idempotent Kafka producer connected with transactions enabled")
            
        except Exception as e:
            logger.error("Failed to connect Kafka producer", error=str(e))
            self._connected = False
            raise
    
    async def disconnect(self) -> None:
        """Stop Kafka producer"""
        if self.producer:
            try:
                # Abort any pending transaction
                await self.producer.abort_transaction()
            except:
                pass
            
            await self.producer.stop()
            self._connected = False
            logger.info("Kafka producer disconnected")
    
    async def is_connected(self) -> bool:
        """Check if producer is connected"""
        return self._connected and self.producer is not None
    
    async def send_sales_event(self, event: Dict[str, Any]) -> bool:
        """
        Send sales event with transactional guarantee
        
        Args:
            event: Sales event data
            
        Returns:
            True if sent successfully, False otherwise
        """
        if not self.producer:
            raise RuntimeError("Producer not connected")
        
        try:
            # Send to main sales topic
            await self.producer.send(
                settings.kafka_topic,
                value=event,
                key=f"{event['sku']}_{event['ts']}"  # Partition by SKU+timestamp
            )
            
            # Send success notification to ingested topic
            success_event = {
                "event_id": event.get("event_id"),
                "sku": event["sku"],
                "timestamp": event["ts"],
                "processed_at": event.get("processed_at"),
                "status": "ingested"
            }
            
            await self.producer.send(
                "sales_ingested",
                value=success_event,
                key=event["sku"]
            )
            
            # Commit transaction
            await self.producer.commit_transaction()
            
            # Begin new transaction for next batch
            await self.producer.begin_transaction()
            
            logger.debug("Sales event sent with transaction commit", 
                        sku=event["sku"], 
                        event_id=event.get("event_id"))
            
            return True
            
        except KafkaError as e:
            logger.error("Kafka error sending sales event", error=str(e))
            
            try:
                # Abort transaction on error
                await self.producer.abort_transaction()
                await self.producer.begin_transaction()
            except:
                pass
            
            return False
        except Exception as e:
            logger.error("Unexpected error sending sales event", error=str(e))
            return False


# Global producer instance
kafka_producer = IdempotentKafkaProducer()