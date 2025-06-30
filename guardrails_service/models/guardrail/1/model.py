import json
import numpy as np
import triton_python_backend_utils as pb_utils
from pydantic import BaseModel, ValidationError, Field
from typing import List, Optional, Dict, Any
import re
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class EntityValidation(BaseModel):
    """Pydantic model for entity validation"""
    sku: str = Field(..., pattern=r'^[A-Z0-9\-_]+$', description="Valid SKU format")
    quantity: int = Field(..., gt=0, description="Quantity must be positive")
    price: Optional[float] = Field(None, gt=0, description="Price must be positive if provided")
    date: Optional[str] = Field(None, description="ISO8601 date format")
    
    class Config:
        str_strip_whitespace = True


class ValidationRequest(BaseModel):
    """Request model for validation"""
    text: str = Field(..., min_length=1, description="Text to validate")
    entities: Optional[List[str]] = Field(default=[], description="Known valid entities")


class ValidationResponse(BaseModel):
    """Response model for validation"""
    is_safe: bool = Field(..., description="Whether text passes validation")
    violations: List[str] = Field(default=[], description="List of validation violations")
    sanitized_text: str = Field(..., description="Text with violations removed/replaced")
    entities_found: List[str] = Field(default=[], description="Valid entities found")
    confidence_score: float = Field(..., ge=0, le=1, description="Confidence in validation")


class GuardrailValidator:
    """Core validation logic for guardrails"""
    
    def __init__(self):
        # Known valid entities (in production, this would come from database)
        self.valid_entities = {
            "SKU-ABC", "SKU-XYZ", "SKU-ABC-V2", "Product-X", "Product-Y",
            "CAMPAIGN-2024-VAL", "PROMO-WINTER-23", "Q1-LAUNCH", "Q4-CLEARANCE"
        }
        
        # Patterns for entity extraction
        self.entity_patterns = [
            r'SKU-[A-Z0-9\-]+',
            r'Product-[A-Z0-9\-]+',
            r'CAMPAIGN-[A-Z0-9\-]+',
            r'PROMO-[A-Z0-9\-]+',
            r'Q[1-4]-[A-Z0-9\-]+'
        ]
        
        # Violation patterns
        self.violation_patterns = {
            'negative_quantity': r'(?:quantity|qty|units?|sold)\s*:?\s*-\d+',
            'negative_price': r'(?:price|cost|value)\s*:?\s*-\$?\d+(?:\.\d+)?',
            'invalid_date': r'\d{4}[-/]\d{1,2}[-/]\d{1,2}(?!\d)',  # Basic date pattern
            'hallucinated_entity': r'(?:SKU|Product|Campaign)-[A-Z0-9\-]+(?:-FAKE|-INVALID|-TEST)?'
        }
    
    def extract_entities(self, text: str) -> List[str]:
        """Extract potential entities from text"""
        entities = []
        for pattern in self.entity_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            entities.extend([match.upper() for match in matches])
        return list(set(entities))  # Remove duplicates
    
    def validate_entities(self, entities: List[str]) -> tuple[List[str], List[str]]:
        """Validate entities against known catalog"""
        valid = []
        invalid = []
        
        for entity in entities:
            if entity.upper() in {e.upper() for e in self.valid_entities}:
                valid.append(entity)
            else:
                invalid.append(entity)
        
        return valid, invalid
    
    def check_violations(self, text: str) -> List[str]:
        """Check for various types of violations"""
        violations = []
        
        # Check for negative quantities
        if re.search(self.violation_patterns['negative_quantity'], text, re.IGNORECASE):
            violations.append("Negative quantity detected")
        
        # Check for negative prices
        if re.search(self.violation_patterns['negative_price'], text, re.IGNORECASE):
            violations.append("Negative price detected")
        
        # Check for potentially invalid dates (basic check)
        date_matches = re.findall(r'\d{4}[-/]\d{1,2}[-/]\d{1,2}', text)
        for date_str in date_matches:
            try:
                # Try to parse as ISO date
                datetime.fromisoformat(date_str.replace('/', '-'))
            except ValueError:
                violations.append(f"Invalid date format: {date_str}")
        
        return violations
    
    def sanitize_text(self, text: str, violations: List[str], invalid_entities: List[str]) -> str:
        """Sanitize text by removing/replacing violations"""
        sanitized = text
        
        # Replace invalid entities
        for entity in invalid_entities:
            sanitized = sanitized.replace(entity, "[INVALID_ENTITY]")
        
        # Replace negative quantities
        sanitized = re.sub(
            self.violation_patterns['negative_quantity'],
            "[INVALID_QUANTITY]",
            sanitized,
            flags=re.IGNORECASE
        )
        
        # Replace negative prices
        sanitized = re.sub(
            self.violation_patterns['negative_price'],
            "[INVALID_PRICE]",
            sanitized,
            flags=re.IGNORECASE
        )
        
        return sanitized
    
    def validate_text(self, text: str) -> ValidationResponse:
        """Main validation function"""
        try:
            # Extract entities
            entities_found = self.extract_entities(text)
            valid_entities, invalid_entities = self.validate_entities(entities_found)
            
            # Check for violations
            violations = self.check_violations(text)
            
            # Add entity violations
            if invalid_entities:
                violations.extend([f"Invalid entity: {entity}" for entity in invalid_entities])
            
            # Determine if text is safe
            is_safe = len(violations) == 0
            
            # Sanitize text if needed
            sanitized_text = text if is_safe else self.sanitize_text(text, violations, invalid_entities)
            
            # Calculate confidence score
            confidence_score = 1.0 if is_safe else max(0.1, 1.0 - (len(violations) * 0.2))
            
            return ValidationResponse(
                is_safe=is_safe,
                violations=violations,
                sanitized_text=sanitized_text,
                entities_found=valid_entities,
                confidence_score=confidence_score
            )
            
        except Exception as e:
            logger.error(f"Validation error: {str(e)}")
            return ValidationResponse(
                is_safe=False,
                violations=[f"Validation error: {str(e)}"],
                sanitized_text="[VALIDATION_ERROR]",
                entities_found=[],
                confidence_score=0.0
            )


class TritonPythonModel:
    """Triton Python backend model for guardrail validation"""
    
    def initialize(self, args):
        """Initialize the model"""
        self.validator = GuardrailValidator()
        logger.info("Guardrail validation model initialized")
    
    def execute(self, requests):
        """Execute validation requests"""
        responses = []
        
        for request in requests:
            try:
                # Get input text
                input_tensor = pb_utils.get_input_tensor_by_name(request, "TEXT")
                input_text = input_tensor.as_numpy()[0].decode('utf-8')
                
                logger.info(f"Validating text: {input_text[:100]}...")
                
                # Perform validation
                validation_result = self.validator.validate_text(input_text)
                
                # Prepare response
                response_dict = {
                    "is_safe": validation_result.is_safe,
                    "violations": validation_result.violations,
                    "sanitized_text": validation_result.sanitized_text,
                    "entities_found": validation_result.entities_found,
                    "confidence_score": validation_result.confidence_score
                }
                
                # Convert to JSON string
                response_json = json.dumps(response_dict)
                
                # Create output tensor
                output_tensor = pb_utils.Tensor(
                    "VALIDATION_RESULT",
                    np.array([response_json.encode('utf-8')], dtype=object)
                )
                
                # Create inference response
                inference_response = pb_utils.InferenceResponse(
                    output_tensors=[output_tensor]
                )
                
                responses.append(inference_response)
                
                logger.info(f"Validation completed. Safe: {validation_result.is_safe}")
                
            except Exception as e:
                logger.error(f"Error processing request: {str(e)}")
                
                # Return error response
                error_response = {
                    "is_safe": False,
                    "violations": [f"Processing error: {str(e)}"],
                    "sanitized_text": "[ERROR]",
                    "entities_found": [],
                    "confidence_score": 0.0
                }
                
                error_json = json.dumps(error_response)
                error_tensor = pb_utils.Tensor(
                    "VALIDATION_RESULT",
                    np.array([error_json.encode('utf-8')], dtype=object)
                )
                
                error_inference_response = pb_utils.InferenceResponse(
                    output_tensors=[error_tensor]
                )
                
                responses.append(error_inference_response)
        
        return responses
    
    def finalize(self):
        """Clean up resources"""
        logger.info("Guardrail validation model finalized")