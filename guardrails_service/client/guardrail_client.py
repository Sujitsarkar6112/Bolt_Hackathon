#!/usr/bin/env python3
"""
Client library for interacting with Triton Guardrails Service
"""

import json
import requests
import numpy as np
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class GuardrailClient:
    """Client for Triton Guardrails Service"""
    
    def __init__(self, triton_url: str = "http://localhost:8000"):
        """
        Initialize guardrail client
        
        Args:
            triton_url: Base URL for Triton server
        """
        self.triton_url = triton_url.rstrip('/')
        self.session = requests.Session()
        
    def validate_text(self, text: str, model_name: str = "ensemble_guardrail") -> Dict[str, Any]:
        """
        Validate text using Triton guardrail model
        
        Args:
            text: Text to validate
            model_name: Name of the model to use
            
        Returns:
            Dictionary with validation results
        """
        try:
            # Prepare request payload
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
            
            # Send request to Triton
            url = f"{self.triton_url}/v2/models/{model_name}/infer"
            response = self.session.post(url, json=payload)
            
            if response.status_code != 200:
                raise Exception(f"Triton request failed: {response.status_code} - {response.text}")
            
            # Parse response
            triton_response = response.json()
            
            # Extract outputs
            outputs = triton_response.get("outputs", [])
            status_code = None
            result_json = None
            
            for output in outputs:
                if output["name"] == "STATUS_CODE":
                    status_code = output["data"][0]
                elif output["name"] == "RESULT":
                    result_json = output["data"][0]
            
            if result_json is None:
                raise Exception("No result data in Triton response")
            
            # Parse result JSON
            result = json.loads(result_json)
            
            logger.info(f"Validation completed. Status: {status_code}, Safe: {result.get('is_safe', False)}")
            
            return result
            
        except Exception as e:
            logger.error(f"Validation failed: {str(e)}")
            return {
                "status_code": 500,
                "status_message": "CLIENT_ERROR",
                "is_safe": False,
                "violations": [f"Client error: {str(e)}"],
                "sanitized_text": "[ERROR]",
                "entities_found": [],
                "confidence_score": 0.0,
                "original_text": text
            }
    
    def health_check(self) -> bool:
        """
        Check if Triton server is healthy
        
        Returns:
            True if healthy, False otherwise
        """
        try:
            url = f"{self.triton_url}/v2/health/ready"
            response = self.session.get(url, timeout=5)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Health check failed: {str(e)}")
            return False
    
    def list_models(self) -> Dict[str, Any]:
        """
        List available models
        
        Returns:
            Dictionary with model information
        """
        try:
            url = f"{self.triton_url}/v2/models"
            response = self.session.get(url)
            
            if response.status_code != 200:
                raise Exception(f"Failed to list models: {response.status_code}")
            
            return response.json()
            
        except Exception as e:
            logger.error(f"Failed to list models: {str(e)}")
            return {"models": []}


# Example usage and testing
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Test Guardrail Client")
    parser.add_argument("--url", default="http://localhost:8000", help="Triton server URL")
    parser.add_argument("--text", required=True, help="Text to validate")
    parser.add_argument("--model", default="ensemble_guardrail", help="Model name")
    
    args = parser.parse_args()
    
    # Configure logging
    logging.basicConfig(level=logging.INFO)
    
    # Create client
    client = GuardrailClient(args.url)
    
    # Check health
    if not client.health_check():
        print("❌ Triton server is not healthy")
        exit(1)
    
    print("✅ Triton server is healthy")
    
    # Validate text
    result = client.validate_text(args.text, args.model)
    
    # Print results
    print(f"\n📝 Original Text: {args.text}")
    print(f"🔒 Is Safe: {result['is_safe']}")
    print(f"📊 Confidence: {result['confidence_score']:.2f}")
    
    if result['violations']:
        print(f"⚠️  Violations: {', '.join(result['violations'])}")
    
    if result['entities_found']:
        print(f"🏷️  Valid Entities: {', '.join(result['entities_found'])}")
    
    if not result['is_safe']:
        print(f"🧹 Sanitized: {result['sanitized_text']}")
    
    print(f"🌐 HTTP Status: {result.get('status_code', 'N/A')}")