#!/usr/bin/env python3
"""
Integration tests for Triton Guardrails Service
"""

import pytest
import requests
import json
import time
from typing import Dict, Any

# Test configuration
TRITON_URL = "http://localhost:8000"
MODEL_NAME = "ensemble_guardrail"


class TestGuardrailsService:
    """Test suite for guardrails service"""
    
    @classmethod
    def setup_class(cls):
        """Wait for Triton to be ready"""
        max_retries = 30
        for i in range(max_retries):
            try:
                response = requests.get(f"{TRITON_URL}/v2/health/ready", timeout=5)
                if response.status_code == 200:
                    print("✅ Triton server is ready")
                    return
            except Exception:
                pass
            
            if i < max_retries - 1:
                print(f"⏳ Waiting for Triton server... ({i+1}/{max_retries})")
                time.sleep(2)
        
        pytest.fail("Triton server not ready after 60 seconds")
    
    def _validate_text(self, text: str) -> Dict[str, Any]:
        """Helper method to validate text"""
        payload = {
            "inputs": [
                {
                    "name": "TEXT",
                    "shape": [1, 1],
                    "datatype": "BYTES",
                    "data": [text]
                }
            ],
            "outputs": [
                {"name": "STATUS_CODE"},
                {"name": "RESULT"}
            ]
        }
        
        response = requests.post(f"{TRITON_URL}/v2/models/{MODEL_NAME}/infer", json=payload)
        assert response.status_code == 200
        
        triton_response = response.json()
        outputs = triton_response.get("outputs", [])
        
        status_code = None
        result_json = None
        
        for output in outputs:
            if output["name"] == "STATUS_CODE":
                status_code = output["data"][0]
            elif output["name"] == "RESULT":
                result_json = output["data"][0]
        
        result = json.loads(result_json)
        result["http_status"] = status_code
        
        return result
    
    def test_valid_text_with_entities(self):
        """Test validation of valid text with known entities"""
        text = "SKU-ABC has sold 100 units at price $29.99 in Q1-LAUNCH campaign"
        result = self._validate_text(text)
        
        assert result["is_safe"] is True
        assert result["http_status"] == 200
        assert "SKU-ABC" in result["entities_found"]
        assert "Q1-LAUNCH" in result["entities_found"]
        assert len(result["violations"]) == 0
        assert result["confidence_score"] > 0.9
    
    def test_negative_quantity_violation(self):
        """Test detection of negative quantities"""
        text = "SKU-ABC has quantity: -50 units sold"
        result = self._validate_text(text)
        
        assert result["is_safe"] is False
        assert result["http_status"] == 400
        assert any("negative quantity" in v.lower() for v in result["violations"])
        assert "[INVALID_QUANTITY]" in result["sanitized_text"]
    
    def test_negative_price_violation(self):
        """Test detection of negative prices"""
        text = "Product price: -$25.99 for SKU-XYZ"
        result = self._validate_text(text)
        
        assert result["is_safe"] is False
        assert result["http_status"] == 400
        assert any("negative price" in v.lower() for v in result["violations"])
        assert "[INVALID_PRICE]" in result["sanitized_text"]
    
    def test_invalid_entity_violation(self):
        """Test detection of invalid/hallucinated entities"""
        text = "SKU-FAKE-123 and SKU-INVALID-456 are new products"
        result = self._validate_text(text)
        
        assert result["is_safe"] is False
        assert result["http_status"] == 400
        assert any("invalid entity" in v.lower() for v in result["violations"])
        assert "[INVALID_ENTITY]" in result["sanitized_text"]
    
    def test_multiple_violations(self):
        """Test text with multiple violations"""
        text = "SKU-FAKE has quantity: -100 units at price: -$50.00"
        result = self._validate_text(text)
        
        assert result["is_safe"] is False
        assert result["http_status"] == 400
        assert len(result["violations"]) >= 3  # Invalid entity, negative qty, negative price
        assert result["confidence_score"] < 0.5
    
    def test_clean_text_no_entities(self):
        """Test clean text without entities"""
        text = "This is a general business report about market trends and analysis."
        result = self._validate_text(text)
        
        assert result["is_safe"] is True
        assert result["http_status"] == 200
        assert len(result["entities_found"]) == 0
        assert len(result["violations"]) == 0
    
    def test_mixed_valid_invalid_entities(self):
        """Test text with both valid and invalid entities"""
        text = "SKU-ABC and SKU-INVALID are compared in this analysis"
        result = self._validate_text(text)
        
        assert result["is_safe"] is False
        assert result["http_status"] == 400
        assert "SKU-ABC" in result["entities_found"]
        assert any("invalid entity" in v.lower() for v in result["violations"])
    
    def test_edge_case_empty_text(self):
        """Test edge case with empty text"""
        text = ""
        result = self._validate_text(text)
        
        # Should handle gracefully
        assert "http_status" in result
        assert "is_safe" in result
    
    def test_edge_case_very_long_text(self):
        """Test edge case with very long text"""
        text = "SKU-ABC " * 1000 + "has normal quantities and prices"
        result = self._validate_text(text)
        
        assert result["is_safe"] is True
        assert result["http_status"] == 200
        assert "SKU-ABC" in result["entities_found"]
    
    def test_confidence_scoring(self):
        """Test confidence scoring accuracy"""
        # Perfect text should have high confidence
        perfect_text = "SKU-ABC sold 100 units at $29.99"
        perfect_result = self._validate_text(perfect_text)
        
        # Problematic text should have low confidence
        bad_text = "SKU-FAKE sold -100 units at -$29.99"
        bad_result = self._validate_text(bad_text)
        
        assert perfect_result["confidence_score"] > bad_result["confidence_score"]
        assert perfect_result["confidence_score"] > 0.8
        assert bad_result["confidence_score"] < 0.5


class TestTritonHealth:
    """Test Triton server health and model availability"""
    
    def test_server_health(self):
        """Test server health endpoints"""
        # Live check
        response = requests.get(f"{TRITON_URL}/v2/health/live")
        assert response.status_code == 200
        
        # Ready check
        response = requests.get(f"{TRITON_URL}/v2/health/ready")
        assert response.status_code == 200
    
    def test_model_availability(self):
        """Test that required models are loaded"""
        response = requests.get(f"{TRITON_URL}/v2/models")
        assert response.status_code == 200
        
        models = response.json()
        model_names = [model["name"] for model in models.get("models", [])]
        
        assert "guardrail" in model_names
        assert "ensemble_guardrail" in model_names
    
    def test_model_metadata(self):
        """Test model metadata endpoints"""
        # Test guardrail model
        response = requests.get(f"{TRITON_URL}/v2/models/guardrail")
        assert response.status_code == 200
        
        metadata = response.json()
        assert metadata["name"] == "guardrail"
        assert metadata["backend"] == "python"
        
        # Test ensemble model
        response = requests.get(f"{TRITON_URL}/v2/models/ensemble_guardrail")
        assert response.status_code == 200
        
        metadata = response.json()
        assert metadata["name"] == "ensemble_guardrail"
        assert metadata["platform"] == "ensemble"


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v", "--tb=short"])