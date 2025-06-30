import pytest
import asyncio
from aiokafka import AIOKafkaProducer
from motor.motor_asyncio import AsyncIOMotorClient
from app.proto import sales_event_pb2
from app.processor import SalesEventProcessor
from app.database import MongoDBClient
from app.kafka_consumer import KafkaConsumerClient
import time


class TestIntegration:
    """Integration tests using testcontainers"""
    
    @pytest.fixture
    async def setup_integration_test(self, mongodb_container, kafka_container):
        """Setup integration test environment"""
        # Setup MongoDB
        mongodb_url = mongodb_container.get_connection_url()
        mongo_client = AsyncIOMotorClient(mongodb_url)
        db = mongo_client["test_sales_db"]
        collection = db["test_raw_sales"]
        
        # Create indexes
        await collection.create_index([("sku", 1), ("ts", 1)], unique=True)
        await collection.delete_many({})  # Clean slate
        
        # Setup Kafka producer
        bootstrap_servers = kafka_container.get_bootstrap_server()
        producer = AIOKafkaProducer(
            bootstrap_servers=bootstrap_servers,
            value_serializer=lambda x: x
        )
        await producer.start()
        
        # Create topic
        from aiokafka.admin import AIOKafkaAdminClient, NewTopic
        admin_client = AIOKafkaAdminClient(bootstrap_servers=bootstrap_servers)
        await admin_client.start()
        
        try:
            topic = NewTopic(name="test_sales_txn", num_partitions=1, replication_factor=1)
            await admin_client.create_topics([topic])
        except Exception:
            pass  # Topic might already exist
        
        await admin_client.close()
        
        yield {
            'mongodb_url': mongodb_url,
            'kafka_servers': bootstrap_servers,
            'producer': producer,
            'collection': collection,
            'mongo_client': mongo_client
        }
        
        # Cleanup
        await producer.stop()
        mongo_client.close()
    
    async def test_end_to_end_processing(self, setup_integration_test):
        """Test complete end-to-end event processing"""
        test_env = setup_integration_test
        
        # Create test events
        events = []
        for i in range(5):
            event = sales_event_pb2.SalesEvent()
            event.sku = f"INTEGRATION-SKU-{i:03d}"
            event.qty = i + 1
            event.price = (i + 1) * 10.0
            event.ts = f"2024-01-15T10:{30+i:02d}:00Z"
            event.event_id = f"integration-{i:03d}"
            events.append(event)
        
        # Send events to Kafka
        for event in events:
            await test_env['producer'].send(
                "test_sales_txn",
                value=event.SerializeToString()
            )
        
        await test_env['producer'].flush()
        
        # Setup processor with test configuration
        processor = SalesEventProcessor()
        
        # Mock the configuration for testing
        import app.config
        original_settings = app.config.settings
        
        class TestSettings:
            kafka_bootstrap_servers = test_env['kafka_servers']
            kafka_topic = "test_sales_txn"
            kafka_group_id = "test_ingest_service"
            kafka_auto_offset_reset = "earliest"
            kafka_enable_auto_commit = True
            kafka_max_poll_records = 500
            mongodb_url = test_env['mongodb_url']
            mongodb_database = "test_sales_db"
            mongodb_collection = "test_raw_sales"
            service_name = "test_ingest_service"
            log_level = "INFO"
            metrics_port = 8002
            health_check_interval = 30
            batch_size = 2
            flush_interval = 1.0
            max_retries = 3
            retry_backoff = 1.0
        
        app.config.settings = TestSettings()
        
        try:
            # Start processor
            processor_task = asyncio.create_task(processor.start())
            
            # Wait for processing
            await asyncio.sleep(5)
            
            # Stop processor
            await processor.stop()
            processor_task.cancel()
            
            try:
                await processor_task
            except asyncio.CancelledError:
                pass
            
            # Verify events were processed
            count = await test_env['collection'].count_documents({})
            assert count == 5
            
            # Verify event data
            docs = await test_env['collection'].find({}).to_list(length=10)
            skus = [doc['sku'] for doc in docs]
            
            for i in range(5):
                expected_sku = f"INTEGRATION-SKU-{i:03d}"
                assert expected_sku in skus
            
            # Verify specific event data
            doc = await test_env['collection'].find_one({"sku": "INTEGRATION-SKU-000"})
            assert doc is not None
            assert doc['qty'] == 1
            assert doc['price'] == 10.0
            assert doc['ts'] == "2024-01-15T10:30:00Z"
            
        finally:
            # Restore original settings
            app.config.settings = original_settings
    
    async def test_duplicate_event_handling_integration(self, setup_integration_test):
        """Test duplicate event handling in integration environment"""
        test_env = setup_integration_test
        
        # Create duplicate events
        event = sales_event_pb2.SalesEvent()
        event.sku = "DUPLICATE-TEST-SKU"
        event.qty = 5
        event.price = 29.99
        event.ts = "2024-01-15T10:30:00Z"
        event.event_id = "duplicate-test"
        
        # Send same event multiple times
        for _ in range(3):
            await test_env['producer'].send(
                "test_sales_txn",
                value=event.SerializeToString()
            )
        
        await test_env['producer'].flush()
        
        # Setup and run processor
        processor = SalesEventProcessor()
        
        # Mock configuration
        import app.config
        original_settings = app.config.settings
        
        class TestSettings:
            kafka_bootstrap_servers = test_env['kafka_servers']
            kafka_topic = "test_sales_txn"
            kafka_group_id = "test_duplicate_service"
            kafka_auto_offset_reset = "earliest"
            kafka_enable_auto_commit = True
            kafka_max_poll_records = 500
            mongodb_url = test_env['mongodb_url']
            mongodb_database = "test_sales_db"
            mongodb_collection = "test_raw_sales"
            service_name = "test_duplicate_service"
            log_level = "INFO"
            metrics_port = 8003
            health_check_interval = 30
            batch_size = 10
            flush_interval = 1.0
            max_retries = 3
            retry_backoff = 1.0
        
        app.config.settings = TestSettings()
        
        try:
            processor_task = asyncio.create_task(processor.start())
            await asyncio.sleep(3)
            await processor.stop()
            processor_task.cancel()
            
            try:
                await processor_task
            except asyncio.CancelledError:
                pass
            
            # Verify only one document was inserted
            count = await test_env['collection'].count_documents({"sku": "DUPLICATE-TEST-SKU"})
            assert count == 1
            
        finally:
            app.config.settings = original_settings