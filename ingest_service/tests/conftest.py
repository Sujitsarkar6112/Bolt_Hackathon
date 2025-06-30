import pytest
import asyncio
from testcontainers.mongodb import MongoDbContainer
from testcontainers.kafka import KafkaContainer
from motor.motor_asyncio import AsyncIOMotorClient
from aiokafka import AIOKafkaProducer
import os
from app.proto import sales_event_pb2


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def mongodb_container():
    """Start MongoDB test container"""
    with MongoDbContainer("mongo:7.0") as mongodb:
        yield mongodb


@pytest.fixture(scope="session")
async def kafka_container():
    """Start Kafka test container"""
    with KafkaContainer() as kafka:
        yield kafka


@pytest.fixture(scope="session")
async def mongodb_client(mongodb_container):
    """Create MongoDB client for testing"""
    connection_url = mongodb_container.get_connection_url()
    client = AsyncIOMotorClient(connection_url)
    yield client
    client.close()


@pytest.fixture(scope="session")
async def kafka_producer(kafka_container):
    """Create Kafka producer for testing"""
    bootstrap_servers = kafka_container.get_bootstrap_server()
    producer = AIOKafkaProducer(
        bootstrap_servers=bootstrap_servers,
        value_serializer=lambda x: x
    )
    await producer.start()
    yield producer
    await producer.stop()


@pytest.fixture
def sample_sales_event():
    """Create a sample sales event protobuf"""
    event = sales_event_pb2.SalesEvent()
    event.sku = "TEST-SKU-001"
    event.qty = 10
    event.price = 99.99
    event.ts = "2024-01-15T10:30:00Z"
    event.event_id = "test-event-001"
    return event


@pytest.fixture
def invalid_sales_event():
    """Create an invalid sales event for testing validation"""
    event = sales_event_pb2.SalesEvent()
    event.sku = ""  # Invalid empty SKU
    event.qty = -5  # Invalid negative quantity
    event.price = 0.0  # Invalid zero price
    event.ts = "invalid-timestamp"  # Invalid timestamp format
    return event


@pytest.fixture(autouse=True)
async def setup_test_environment(mongodb_container, kafka_container):
    """Setup test environment variables"""
    os.environ["MONGODB_URL"] = mongodb_container.get_connection_url()
    os.environ["KAFKA_BOOTSTRAP_SERVERS"] = kafka_container.get_bootstrap_server()
    os.environ["KAFKA_TOPIC"] = "test_sales_txn"
    os.environ["MONGODB_DATABASE"] = "test_sales_db"
    os.environ["MONGODB_COLLECTION"] = "test_raw_sales"
    yield
    # Cleanup environment variables
    for key in ["MONGODB_URL", "KAFKA_BOOTSTRAP_SERVERS", "KAFKA_TOPIC", 
                "MONGODB_DATABASE", "MONGODB_COLLECTION"]:
        os.environ.pop(key, None)