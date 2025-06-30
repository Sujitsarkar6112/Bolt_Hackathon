#!/usr/bin/env python3
"""
Kafka consumer for model retraining events
Processes retrain requests and triggers incremental model updates
"""

import asyncio
import logging
import json
from typing import Dict, Any, Optional
from aiokafka import AIOKafkaConsumer
from aiokafka.errors import KafkaError
import structlog

from .config import settings
from .services.forecast_ensemble import ForecastEnsemble
from .services.data_loader import DataLoader

logger = structlog.get_logger()


class RetrainConsumer:
    """Kafka consumer for processing model retraining events"""
    
    def __init__(self):
        self.consumer: Optional[AIOKafkaConsumer] = None
        self.forecast_ensemble = ForecastEnsemble()
        self.data_loader = DataLoader()
        self.running = False
    
    async def start(self) -> None:
        """Start the retrain consumer"""
        logger.info("Starting model retrain consumer")
        
        try:
            # Initialize services
            await self.data_loader.connect()
            await self.forecast_ensemble.load_models()
            
            # Create Kafka consumer
            self.consumer = AIOKafkaConsumer(
                "model_retrain",
                bootstrap_servers=settings.kafka_bootstrap_servers,
                group_id="forecast_retrain_consumer",
                auto_offset_reset="latest",
                enable_auto_commit=True,
                value_deserializer=lambda x: json.loads(x.decode('utf-8'))
            )
            
            await self.consumer.start()
            self.running = True
            
            logger.info("Retrain consumer started successfully")
            
            # Start consuming messages
            await self._consume_retrain_events()
            
        except Exception as e:
            logger.error("Failed to start retrain consumer", error=str(e))
            raise
    
    async def stop(self) -> None:
        """Stop the retrain consumer"""
        logger.info("Stopping retrain consumer")
        self.running = False
        
        if self.consumer:
            await self.consumer.stop()
        
        await self.data_loader.disconnect()
    
    async def _consume_retrain_events(self) -> None:
        """Consume and process retrain events"""
        try:
            async for message in self.consumer:
                if not self.running:
                    break
                
                try:
                    retrain_event = message.value
                    await self._process_retrain_event(retrain_event)
                    
                except Exception as e:
                    logger.error("Error processing retrain event", 
                               error=str(e),
                               offset=message.offset)
                    
        except KafkaError as e:
            logger.error("Kafka consumer error", error=str(e))
            if self.running:
                # Attempt to reconnect
                await asyncio.sleep(5)
                await self._consume_retrain_events()
    
    async def _process_retrain_event(self, event: Dict[str, Any]) -> None:
        """Process a single retrain event"""
        sku = event.get("sku")
        trigger = event.get("trigger", "unknown")
        priority = event.get("priority", "normal")
        
        logger.info("Processing retrain event", 
                   sku=sku,
                   trigger=trigger,
                   priority=priority)
        
        try:
            # Check if SKU has sufficient data for retraining
            if not await self.data_loader.sku_exists(sku):
                logger.warning("SKU not found in data", sku=sku)
                return
            
            # Perform incremental retrain for specific SKU
            await self._retrain_sku_models(sku, priority)
            
            logger.info("Retrain completed successfully", sku=sku)
            
        except Exception as e:
            logger.error("Retrain failed", error=str(e), sku=sku)
    
    async def _retrain_sku_models(self, sku: str, priority: str) -> None:
        """Retrain models for specific SKU"""
        try:
            # Get latest training data for SKU
            training_data = await self.data_loader.get_training_data(sku)
            
            if len(training_data) < settings.min_training_samples:
                logger.warning("Insufficient training data for retrain", 
                             sku=sku,
                             data_points=len(training_data))
                return
            
            # Perform incremental training
            if priority == "high":
                # Full retrain for high priority
                await self.forecast_ensemble.retrain_models()
            else:
                # Incremental update for normal priority
                await self.forecast_ensemble.incremental_update(sku, training_data)
            
            logger.info("Model retrain completed", 
                       sku=sku,
                       priority=priority,
                       data_points=len(training_data))
            
        except Exception as e:
            logger.error("Model retrain failed", error=str(e), sku=sku)
            raise


async def main():
    """Main function for standalone execution"""
    consumer = RetrainConsumer()
    
    try:
        await consumer.start()
    except KeyboardInterrupt:
        logger.info("Received interrupt signal")
    finally:
        await consumer.stop()


if __name__ == "__main__":
    asyncio.run(main())