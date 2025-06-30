import pytest
from pydantic import ValidationError
from app.models import SalesEventModel


class TestSalesEventModel:
    """Test cases for SalesEventModel validation"""
    
    def test_valid_sales_event(self):
        """Test valid sales event creation"""
        event_data = {
            "sku": "SKU-CLOTHING",
            "qty": 5,
            "price": 29.99,
            "ts": "2024-01-15T10:30:00Z",
            "event_id": "event-001"
        }
        
        event = SalesEventModel(**event_data)
        assert event.sku == "SKU-CLOTHING"
        assert event.qty == 5
        assert event.price == 29.99
        assert event.ts == "2024-01-15T10:30:00Z"
        assert event.event_id == "event-001"
    
    def test_sku_validation(self):
        """Test SKU validation rules"""
        # Valid SKUs
        valid_skus = ["SKU-123", "PRODUCT_ABC", "ITEM-XYZ-001"]
        for sku in valid_skus:
            event = SalesEventModel(
                sku=sku, qty=1, price=10.0, ts="2024-01-15T10:30:00Z"
            )
            assert event.sku == sku.upper()
        
        # Invalid SKUs
        with pytest.raises(ValidationError):
            SalesEventModel(
                sku="", qty=1, price=10.0, ts="2024-01-15T10:30:00Z"
            )
        
        with pytest.raises(ValidationError):
            SalesEventModel(
                sku="invalid@sku", qty=1, price=10.0, ts="2024-01-15T10:30:00Z"
            )
    
    def test_quantity_validation(self):
        """Test quantity validation rules"""
        # Valid quantities
        event = SalesEventModel(
            sku="SKU-123", qty=1, price=10.0, ts="2024-01-15T10:30:00Z"
        )
        assert event.qty == 1
        
        # Invalid quantities
        with pytest.raises(ValidationError):
            SalesEventModel(
                sku="SKU-123", qty=0, price=10.0, ts="2024-01-15T10:30:00Z"
            )
        
        with pytest.raises(ValidationError):
            SalesEventModel(
                sku="SKU-123", qty=-5, price=10.0, ts="2024-01-15T10:30:00Z"
            )
    
    def test_price_validation(self):
        """Test price validation rules"""
        # Valid prices
        event = SalesEventModel(
            sku="SKU-123", qty=1, price=29.99, ts="2024-01-15T10:30:00Z"
        )
        assert event.price == 29.99
        
        # Invalid prices
        with pytest.raises(ValidationError):
            SalesEventModel(
                sku="SKU-123", qty=1, price=0.0, ts="2024-01-15T10:30:00Z"
            )
        
        with pytest.raises(ValidationError):
            SalesEventModel(
                sku="SKU-123", qty=1, price=-10.0, ts="2024-01-15T10:30:00Z"
            )
        
        # Price with too many decimal places
        with pytest.raises(ValidationError):
            SalesEventModel(
                sku="SKU-123", qty=1, price=29.999, ts="2024-01-15T10:30:00Z"
            )
    
    def test_timestamp_validation(self):
        """Test timestamp validation rules"""
        # Valid timestamps
        valid_timestamps = [
            "2024-01-15T10:30:00Z",
            "2024-01-15T10:30:00+00:00",
            "2024-01-15T10:30:00.123Z"
        ]
        
        for ts in valid_timestamps:
            event = SalesEventModel(
                sku="SKU-123", qty=1, price=10.0, ts=ts
            )
            assert event.ts == ts
        
        # Invalid timestamps
        invalid_timestamps = [
            "2024-01-15",
            "invalid-timestamp",
            "2024/01/15 10:30:00"
        ]
        
        for ts in invalid_timestamps:
            with pytest.raises(ValidationError):
                SalesEventModel(
                    sku="SKU-123", qty=1, price=10.0, ts=ts
                )