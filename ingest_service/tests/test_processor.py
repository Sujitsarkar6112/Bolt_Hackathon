import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from app.processor import SalesEventProcessor
from app.proto import sales_event_pb2


class TestSalesEventProcessor:
    """Test cases for SalesEventProcessor"""
    
    @pytest.fixture
    def processor(self):
        """Create processor instance for testing"""
        return SalesEventProcessor()
    
    @pytest.fixture
    def mock_dependencies(self):
        """Mock external dependencies"""
        with patch('app.processor.mongodb_client') as mock_mongo, \
             patch('app.processor.kafka_consumer') as mock_kafka, \
             patch('app.processor.metrics') as mock_metrics:
            
            mock_mongo.connect = AsyncMock()
            mock_mongo.disconnect = AsyncMock()
            mock_mongo.insert_sales_events_batch = AsyncMock(return_value=1)
            
            mock_kafka.connect = AsyncMock()
            mock_kafka.disconnect = AsyncMock()
            mock_kafka.get_lag_ms = MagicMock(return_value=100.0)
            
            mock_metrics.start_metrics_server = MagicMock()
            mock_metrics.record_event_processed = MagicMock()
            mock_metrics.record_mongodb_write = MagicMock()
            mock_metrics.update_kafka_lag = MagicMock()
            mock_metrics.update_uptime = MagicMock()
            
            yield {
                'mongodb': mock_mongo,
                'kafka': mock_kafka,
                'metrics': mock_metrics
            }
    
    async def test_process_single_event_success(self, processor, sample_sales_event, mock_dependencies):
        """Test successful processing of a single event"""
        await processor._process_single_event(sample_sales_event)
        
        # Verify event was added to batch buffer
        assert len(processor.batch_buffer) == 1
        
        # Verify event data
        event_data = processor.batch_buffer[0]
        assert event_data['sku'] == 'TEST-SKU-001'
        assert event_data['qty'] == 10
        assert event_data['price'] == 99.99
        assert event_data['ts'] == '2024-01-15T10:30:00Z'
        
        # Verify metrics were recorded
        mock_dependencies['metrics'].record_event_processed.assert_called_with('success')
    
    async def test_process_single_event_validation_error(self, processor, invalid_sales_event, mock_dependencies):
        """Test processing of invalid event"""
        await processor._process_single_event(invalid_sales_event)
        
        # Verify event was not added to batch buffer
        assert len(processor.batch_buffer) == 0
        
        # Verify error metrics were recorded
        mock_dependencies['metrics'].record_event_processed.assert_called_with('error')
    
    async def test_flush_batch_success(self, processor, mock_dependencies):
        """Test successful batch flushing"""
        # Add events to batch buffer
        processor.batch_buffer = [
            {
                'sku': 'TEST-SKU-001',
                'qty': 5,
                'price': 29.99,
                'ts': '2024-01-15T10:30:00Z'
            },
            {
                'sku': 'TEST-SKU-002',
                'qty': 3,
                'price': 19.99,
                'ts': '2024-01-15T10:31:00Z'
            }
        ]
        
        await processor._flush_batch()
        
        # Verify MongoDB insert was called
        mock_dependencies['mongodb'].insert_sales_events_batch.assert_called_once()
        
        # Verify batch buffer was cleared
        assert len(processor.batch_buffer) == 0
        
        # Verify metrics were recorded
        mock_dependencies['metrics'].record_mongodb_write.assert_called_with('success')
    
    async def test_flush_empty_batch(self, processor, mock_dependencies):
        """Test flushing empty batch"""
        await processor._flush_batch()
        
        # Verify MongoDB insert was not called
        mock_dependencies['mongodb'].insert_sales_events_batch.assert_not_called()
    
    async def test_flush_batch_error(self, processor, mock_dependencies):
        """Test batch flushing with MongoDB error"""
        # Setup MongoDB to raise exception
        mock_dependencies['mongodb'].insert_sales_events_batch.side_effect = Exception("MongoDB error")
        
        # Add event to batch buffer
        processor.batch_buffer = [
            {
                'sku': 'TEST-SKU-001',
                'qty': 5,
                'price': 29.99,
                'ts': '2024-01-15T10:30:00Z'
            }
        ]
        
        with pytest.raises(Exception):
            await processor._flush_batch()
        
        # Verify error metrics were recorded
        mock_dependencies['metrics'].record_mongodb_write.assert_called_with('error')
        
        # Verify batch buffer was not cleared (for retry)
        assert len(processor.batch_buffer) == 1
    
    async def test_batch_size_trigger(self, processor, mock_dependencies):
        """Test that batch is flushed when size limit is reached"""
        # Set small batch size for testing
        with patch('app.processor.settings') as mock_settings:
            mock_settings.batch_size = 2
            mock_settings.flush_interval = 60.0  # Long interval
            
            # Process events to fill batch
            for i in range(3):
                event = sales_event_pb2.SalesEvent()
                event.sku = f"TEST-SKU-{i:03d}"
                event.qty = 1
                event.price = 10.0
                event.ts = "2024-01-15T10:30:00Z"
                
                await processor._process_single_event(event)
            
            # Verify batch was processed (should have been flushed after 2 events)
            assert len(processor.batch_buffer) == 1  # Only the 3rd event remains
    
    @pytest.mark.asyncio
    async def test_processor_lifecycle(self, processor, mock_dependencies):
        """Test processor start and stop lifecycle"""
        # Mock the event processing loop to avoid infinite loop
        with patch.object(processor, '_process_events', new_callable=AsyncMock) as mock_process:
            # Start processor
            start_task = asyncio.create_task(processor.start())
            
            # Give it a moment to start
            await asyncio.sleep(0.1)
            
            # Stop processor
            await processor.stop()
            
            # Cancel the start task
            start_task.cancel()
            try:
                await start_task
            except asyncio.CancelledError:
                pass
            
            # Verify connections were established and closed
            mock_dependencies['mongodb'].connect.assert_called_once()
            mock_dependencies['kafka'].connect.assert_called_once()
            mock_dependencies['mongodb'].disconnect.assert_called_once()
            mock_dependencies['kafka'].disconnect.assert_called_once()