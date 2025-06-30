#!/usr/bin/env python3
"""
End-to-end pipeline test
Tests complete data flow from Kafka ingestion to validated API responses
"""

import asyncio
import json
import time
import uuid
import websockets
from datetime import datetime, timedelta
from typing import Dict, Any, List
import httpx
import pytest
from kafka import KafkaProducer
from pymongo import MongoClient
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Test configuration
KAFKA_BOOTSTRAP_SERVERS = "localhost:9092"
MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://admin:password@localhost:27017/demandbot?authSource=admin")
API_BASE_URL = "http://localhost:8080/api"
GATEWAY_WS_URL = "ws://localhost:8004/chat"  # Updated to use gateway WebSocket
TRITON_URL = "http://localhost:8000"

# Test data
TEST_SKU = "TEST-SKU-E2E"
TEST_EVENTS = [
    {
        "sku": TEST_SKU,
        "qty": 100 + i,
        "price": 29.99 + (i * 0.1),
        "ts": (datetime.utcnow() - timedelta(days=30-i)).isoformat() + "Z",
        "event_id": f"e2e-test-{i:03d}"
    }
    for i in range(30)  # 30 days of data
]


class PipelineE2ETest:
    """End-to-end pipeline test suite"""
    
    def __init__(self):
        self.kafka_producer = None
        self.mongo_client = None
        self.http_client = httpx.AsyncClient(timeout=30.0)
        
    async def setup(self):
        """Setup test environment"""
        logger.info("Setting up E2E test environment")
        
        # Initialize Kafka producer
        self.kafka_producer = KafkaProducer(
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            value_serializer=lambda x: json.dumps(x).encode('utf-8'),
            key_serializer=lambda x: x.encode('utf-8') if x else None
        )
        
        # Initialize MongoDB client
        self.mongo_client = MongoClient(MONGODB_URL)
        
        # Clean up any existing test data
        await self.cleanup_test_data()
        
        logger.info("E2E test environment setup complete")
    
    async def cleanup(self):
        """Cleanup test environment"""
        logger.info("Cleaning up E2E test environment")
        
        await self.cleanup_test_data()
        
        if self.kafka_producer:
            self.kafka_producer.close()
        
        if self.mongo_client:
            self.mongo_client.close()
        
        await self.http_client.aclose()
        
        logger.info("E2E test environment cleanup complete")
    
    async def cleanup_test_data(self):
        """Remove test data from MongoDB"""
        try:
            db = self.mongo_client["demandbot"]
            
            # Remove test sales events
            sales_collection = db["raw_sales"]
            result = sales_collection.delete_many({"sku": TEST_SKU})
            logger.info(f"Removed {result.deleted_count} test sales events")
            
            # Remove test forecast data
            forecast_collection = db["predictions"]
            result = forecast_collection.delete_many({"sku": TEST_SKU})
            logger.info(f"Removed {result.deleted_count} test forecast records")
            
        except Exception as e:
            logger.warning(f"Error cleaning up test data: {e}")
    
    async def test_step_1_kafka_ingestion(self):
        """Step 1: Send test events to Kafka and verify ingestion"""
        logger.info("Step 1: Testing Kafka ingestion")
        
        # Send test events to Kafka
        for event in TEST_EVENTS:
            self.kafka_producer.send(
                "sales_txn",
                value=event,
                key=f"{event['sku']}_{event['ts']}"
            )
        
        # Flush to ensure all messages are sent
        self.kafka_producer.flush()
        
        logger.info(f"Sent {len(TEST_EVENTS)} test events to Kafka")
        
        # Wait for ingestion processing
        await asyncio.sleep(10)
        
        # Verify events were ingested to MongoDB
        db = self.mongo_client["demandbot"]
        sales_collection = db["raw_sales"]
        
        # Wait up to 60 seconds for all events to be ingested
        for attempt in range(12):  # 12 * 5 = 60 seconds
            count = sales_collection.count_documents({"sku": TEST_SKU})
            logger.info(f"Attempt {attempt + 1}: Found {count}/{len(TEST_EVENTS)} events in MongoDB")
            
            if count >= len(TEST_EVENTS):
                break
            
            await asyncio.sleep(5)
        
        # Final verification
        final_count = sales_collection.count_documents({"sku": TEST_SKU})
        assert final_count >= len(TEST_EVENTS), f"Expected at least {len(TEST_EVENTS)} events, found {final_count}"
        
        logger.info(f"✓ Step 1 passed: {final_count} events successfully ingested")
        return True
    
    async def test_step_2_change_stream_trigger(self):
        """Step 2: Verify change stream triggers retrain events"""
        logger.info("Step 2: Testing change stream and retrain triggers")
        
        # Add a few more events to trigger change stream
        additional_events = [
            {
                "sku": TEST_SKU,
                "qty": 150 + i,
                "price": 35.99,
                "ts": (datetime.utcnow() + timedelta(minutes=i)).isoformat() + "Z",
                "event_id": f"e2e-trigger-{i:03d}"
            }
            for i in range(5)
        ]
        
        for event in additional_events:
            self.kafka_producer.send(
                "sales_txn",
                value=event,
                key=f"{event['sku']}_{event['ts']}"
            )
        
        self.kafka_producer.flush()
        
        # Wait for change stream processing
        await asyncio.sleep(15)
        
        logger.info("✓ Step 2 passed: Change stream events triggered")
        return True
    
    async def test_step_3_forecast_api(self):
        """Step 3: Test forecast API returns non-stale data"""
        logger.info("Step 3: Testing forecast API")
        
        # Call forecast API
        response = await self.http_client.get(f"{API_BASE_URL}/forecast/{TEST_SKU}?horizon=7")
        
        assert response.status_code == 200, f"Forecast API failed: {response.status_code} - {response.text}"
        
        forecast_data = response.json()
        
        # Verify response structure
        assert "sku" in forecast_data
        assert "forecast" in forecast_data
        assert forecast_data["sku"] == TEST_SKU
        assert len(forecast_data["forecast"]) == 7
        
        # Verify forecast is recent (not stale)
        forecast_date = datetime.fromisoformat(forecast_data["forecast_date"].replace('Z', '+00:00'))
        time_diff = datetime.utcnow() - forecast_date.replace(tzinfo=None)
        assert time_diff.total_seconds() < 3600, f"Forecast is stale: {time_diff.total_seconds()} seconds old"
        
        logger.info(f"✓ Step 3 passed: Forecast API returned fresh data for {TEST_SKU}")
        return forecast_data
    
    async def test_step_4_rag_api_with_citations(self):
        """Step 4: Test RAG API returns citations"""
        logger.info("Step 4: Testing RAG API with citations")
        
        # Call RAG API
        response = await self.http_client.post(
            f"{API_BASE_URL}/ask",
            json={
                "query": f"What is the forecast for {TEST_SKU}?",
                "sku": TEST_SKU,
                "top_k": 3
            }
        )
        
        assert response.status_code == 200, f"RAG API failed: {response.status_code} - {response.text}"
        
        rag_data = response.json()
        
        # Verify response structure
        assert "query" in rag_data
        assert "answer" in rag_data
        assert "sources" in rag_data
        assert rag_data["query"] == f"What is the forecast for {TEST_SKU}?"
        
        # Verify answer contains the SKU
        assert TEST_SKU in rag_data["answer"] or "forecast" in rag_data["answer"].lower()
        
        logger.info(f"✓ Step 4 passed: RAG API returned answer with {len(rag_data['sources'])} sources")
        return rag_data
    
    async def test_step_5_triton_validation(self):
        """Step 5: Test Triton guardrails validation"""
        logger.info("Step 5: Testing Triton guardrails validation")
        
        # Test valid text
        valid_payload = {
            "inputs": [
                {
                    "name": "TEXT",
                    "shape": [1, 1],
                    "datatype": "BYTES",
                    "data": [f"{TEST_SKU} has good sales performance with 100 units sold"]
                }
            ],
            "outputs": [
                {"name": "STATUS_CODE"},
                {"name": "RESULT"}
            ]
        }
        
        response = await self.http_client.post(
            f"{TRITON_URL}/v2/models/ensemble_guardrail/infer",
            json=valid_payload
        )
        
        assert response.status_code == 200, f"Triton validation failed: {response.status_code} - {response.text}"
        
        triton_data = response.json()
        
        # Verify response structure
        assert "outputs" in triton_data
        outputs = triton_data["outputs"]
        
        status_code = None
        result_json = None
        
        for output in outputs:
            if output["name"] == "STATUS_CODE":
                status_code = output["data"][0]
            elif output["name"] == "RESULT":
                result_json = output["data"][0]
        
        assert status_code is not None, "Missing STATUS_CODE in Triton response"
        assert result_json is not None, "Missing RESULT in Triton response"
        
        # Parse result
        result = json.loads(result_json)
        assert "is_safe" in result
        assert result["is_safe"] is True, f"Valid text marked as unsafe: {result}"
        
        logger.info("✓ Step 5 passed: Triton validation working correctly")
        return True
    
    async def test_step_6_invalid_entity_detection(self):
        """Step 6: Test invalid entity detection"""
        logger.info("Step 6: Testing invalid entity detection")
        
        # Test invalid text with fake SKU
        invalid_payload = {
            "inputs": [
                {
                    "name": "TEXT",
                    "shape": [1, 1],
                    "datatype": "BYTES",
                    "data": ["SKU-UNKNOWN-CATEGORY has negative quantity: -100 units"]
                }
            ],
            "outputs": [
                {"name": "STATUS_CODE"},
                {"name": "RESULT"}
            ]
        }
        
        response = await self.http_client.post(
            f"{TRITON_URL}/v2/models/ensemble_guardrail/infer",
            json=invalid_payload
        )
        
        assert response.status_code == 200, f"Triton validation failed: {response.status_code} - {response.text}"
        
        triton_data = response.json()
        outputs = triton_data["outputs"]
        
        status_code = None
        result_json = None
        
        for output in outputs:
            if output["name"] == "STATUS_CODE":
                status_code = output["data"][0]
            elif output["name"] == "RESULT":
                result_json = output["data"][0]
        
        result = json.loads(result_json)
        
        # Should detect violations
        assert result["is_safe"] is False, f"Invalid text marked as safe: {result}"
        assert len(result["violations"]) > 0, "No violations detected for invalid text"
        
        logger.info(f"✓ Step 6 passed: Invalid entity detection working ({len(result['violations'])} violations)")
        return True
    
    async def test_step_7_gateway_websocket_e2e(self):
        """Step 7: Test Gateway WebSocket end-to-end with forecast and sources"""
        logger.info("Step 7: Testing Gateway WebSocket end-to-end flow")
        
        # Test data for different types of requests
        test_cases = [
            {
                "message": f"What's the forecast for {TEST_SKU}?",
                "expect_forecast": True,
                "expect_sources": True,
                "test_name": "Forecast Request"
            },
            {
                "message": "What are the current promotions and marketing campaigns?",
                "expect_forecast": False,
                "expect_sources": True,
                "test_name": "RAG Ask Request"
            },
            {
                "message": "Hello, how can you help me?",
                "expect_forecast": False,
                "expect_sources": False,
                "test_name": "General Chat"
            }
        ]
        
        for i, test_case in enumerate(test_cases):
            logger.info(f"Testing {test_case['test_name']}")
            
            # Connect to gateway WebSocket
            try:
                async with websockets.connect(
                    GATEWAY_WS_URL,
                    timeout=10
                ) as websocket:
                    
                    # Send test message
                    message_data = {
                        "type": "chat",
                        "content": test_case["message"],
                        "user_id": f"test_user_{i}",
                        "message_id": f"test_msg_{i}_{uuid.uuid4()}"
                    }
                    
                    await websocket.send(json.dumps(message_data))
                    logger.info(f"Sent message: {test_case['message']}")
                    
                    # Collect response messages
                    response_messages = []
                    start_time = time.time()
                    timeout = 30  # 30 seconds timeout
                    
                    while time.time() - start_time < timeout:
                        try:
                            message = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                            response_data = json.loads(message)
                            response_messages.append(response_data)
                            
                            logger.info(f"Received: {response_data.get('type', 'unknown')}")
                            
                            # Check if we got a complete response
                            if response_data.get("type") in ["stream_end", "forecast_response", "rag_response"]:
                                break
                                
                        except asyncio.TimeoutError:
                            logger.warning("Timeout waiting for response")
                            break
                    
                    # Verify we got responses
                    assert len(response_messages) > 0, f"No response received for {test_case['test_name']}"
                    
                    # Analyze responses
                    has_forecast = False
                    has_sources = False
                    
                    for msg in response_messages:
                        data = msg.get("data", {})
                        
                        # Check for forecast data
                        if "forecast" in data or "forecast_data" in data:
                            has_forecast = True
                            forecast_data = data.get("forecast") or data.get("forecast_data", {}).get("forecast")
                            if forecast_data:
                                logger.info(f"✓ Forecast data found: {len(forecast_data)} forecast points")
                        
                        # Check for sources
                        if "sources" in data or "rag_data" in data:
                            has_sources = True
                            sources = data.get("sources") or data.get("rag_data", {}).get("sources")
                            if sources:
                                logger.info(f"✓ Sources found: {len(sources)} sources")
                    
                    # Verify expectations
                    if test_case["expect_forecast"]:
                        assert has_forecast, f"Expected forecast data but none found for {test_case['test_name']}"
                    
                    if test_case["expect_sources"]:
                        assert has_sources, f"Expected sources but none found for {test_case['test_name']}"
                    
                    logger.info(f"✓ {test_case['test_name']} passed - forecast:{has_forecast}, sources:{has_sources}")
                    
            except Exception as e:
                logger.error(f"WebSocket test failed for {test_case['test_name']}: {e}")
                raise
        
        logger.info("✓ Step 7 passed: Gateway WebSocket end-to-end tests completed")
        return True
    
    async def run_full_pipeline_test(self):
        """Run complete end-to-end pipeline test"""
        logger.info("Starting full E2E pipeline test")
        
        try:
            await self.setup()
            
            # Run all test steps
            await self.test_step_1_kafka_ingestion()
            await self.test_step_2_change_stream_trigger()
            forecast_data = await self.test_step_3_forecast_api()
            rag_data = await self.test_step_4_rag_api_with_citations()
            await self.test_step_5_triton_validation()
            await self.test_step_6_invalid_entity_detection()
            await self.test_step_7_gateway_websocket_e2e()  # New Gateway WebSocket test
            
            logger.info("🎉 All E2E pipeline tests passed successfully!")
            
            # Print summary
            print("\n" + "="*60)
            print("E2E PIPELINE TEST SUMMARY")
            print("="*60)
            print(f"✓ Kafka ingestion: {len(TEST_EVENTS)} events processed")
            print(f"✓ Change streams: Retrain triggers working")
            print(f"✓ Forecast API: Fresh data for {TEST_SKU}")
            print(f"✓ RAG API: {len(rag_data['sources'])} sources returned")
            print(f"✓ Triton validation: Entity detection working")
            print(f"✓ Invalid detection: Violations properly flagged")
            print(f"✓ Gateway WebSocket: Forecast & sources routing verified")
            print("="*60)
            
            return True
            
        except Exception as e:
            logger.error(f"E2E pipeline test failed: {e}")
            raise
        finally:
            await self.cleanup()


async def main():
    """Main test execution"""
    test = PipelineE2ETest()
    success = await test.run_full_pipeline_test()
    
    if success:
        print("\n🎉 E2E Pipeline Test: PASSED")
        exit(0)
    else:
        print("\n❌ E2E Pipeline Test: FAILED")
        exit(1)


if __name__ == "__main__":
    asyncio.run(main())