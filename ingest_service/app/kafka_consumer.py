import asyncio
from aiokafka import AIOKafkaConsumer
from aiokafka.errors import KafkaError
import structlog
from typing import AsyncGenerator, Optional
import time
from .config import settings
from .proto import sales_event_pb2

logger = structlog.get_logger()


class KafkaConsumerClient:
    """Kafka consumer with error handling and metrics"""
    
    def __init__(self):
        self.consumer: Optional[AIOKafkaConsumer] = None
        self._connected = False
        self._last_message_time = time.time()
    
    async def connect(self) -> None:
        """Initialize and start Kafka consumer"""
        try:
            self.consumer = AIOKafkaConsumer(
                settings.kafka_topic,
                bootstrap_servers=settings.kafka_bootstrap_servers,
                group_id=settings.kafka_group_id,
                auto_offset_reset=settings.kafka_auto_offset_reset,
                enable_auto_commit=settings.kafka_enable_auto_commit,
                max_poll_records=settings.kafka_max_poll_records,
                consumer_timeout_ms=1000,
                session_timeout_ms=30000,
                heartbeat_interval_ms=10000
            )
            
            await self.consumer.start()
            self._connected = True
            logger.info("Kafka consumer connected", 
                       topic=settings.kafka_topic,
                       group_id=settings.kafka_group_id)
            
        except Exception as e:
            logger.error("Failed to connect to Kafka", error=str(e))
            self._connected = False
            raise
    
    async def disconnect(self) -> None:
        """Stop and close Kafka consumer"""
        if self.consumer:
            await self.consumer.stop()
            self._connected = False
            logger.info("Kafka consumer disconnected")
    
    async def is_connected(self) -> bool:
        """Check if Kafka consumer is connected"""
        return self._connected and self.consumer is not None
    
    def get_lag_ms(self) -> float:
        """Calculate approximate lag in milliseconds"""
        current_time = time.time()
        return (current_time - self._last_message_time) * 1000
    
    async def consume_messages(self) -> AsyncGenerator[sales_event_pb2.SalesEvent, None]:
        """Consume and yield protobuf messages"""
        if not self.consumer:
            raise RuntimeError("Consumer not initialized")
        
        try:
            async for message in self.consumer:
                try:
                    # Update last message time for lag calculation
                    self._last_message_time = time.time()
                    
                    # Deserialize protobuf message
                    sales_event = sales_event_pb2.SalesEvent()
                    sales_event.ParseFromString(message.value)
                    
                    logger.debug("Received sales event", 
                               sku=sales_event.sku,
                               qty=sales_event.qty,
                               offset=message.offset)
                    
                    yield sales_event
                    
                except Exception as e:
                    logger.error("Failed to parse message", 
                               error=str(e),
                               offset=message.offset,
                               partition=message.partition)
                    continue
                    
        except KafkaError as e:
            logger.error("Kafka consumer error", error=str(e))
            self._connected = False
            raise
        except Exception as e:
            logger.error("Unexpected error in message consumption", error=str(e))
            raise


# Global Kafka consumer instance
kafka_consumer = KafkaConsumerClient()