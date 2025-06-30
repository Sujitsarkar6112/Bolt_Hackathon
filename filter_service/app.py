from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import re
from typing import List, Dict
import logging

app = FastAPI(title="DemandBot Safety Filter", version="1.0.0")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ValidationRequest(BaseModel):
    text: str

class ValidationResponse(BaseModel):
    is_safe: bool
    entities: List[str]
    validated_text: str
    warnings: List[str] = []

# Mock product catalog - in production this would come from MongoDB
VALID_ENTITIES = {
    "SKU-ABC", "SKU-XYZ", "SKU-ABC-V2", "Product-X", "Product-Y",
    "CAMPAIGN-2024-VAL", "PROMO-WINTER-23", "Q1-LAUNCH", "Q4-CLEARANCE"
}

def extract_entities(text: str) -> List[str]:
    """Extract potential SKUs and product references from text"""
    patterns = [
        r'SKU-[A-Z0-9-]+',
        r'Product-[A-Z0-9-]+',
        r'CAMPAIGN-[A-Z0-9-]+',
        r'PROMO-[A-Z0-9-]+',
        r'Q[1-4]-[A-Z0-9-]+'
    ]
    
    entities = []
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        entities.extend(matches)
    
    return list(set(entities))  # Remove duplicates

def validate_entities(entities: List[str]) -> tuple[List[str], List[str]]:
    """Validate entities against known catalog"""
    valid_entities = []
    invalid_entities = []
    
    for entity in entities:
        if entity.upper() in {e.upper() for e in VALID_ENTITIES}:
            valid_entities.append(entity)
        else:
            invalid_entities.append(entity)
    
    return valid_entities, invalid_entities

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "safety-filter"}

@app.post("/validate", response_model=ValidationResponse)
async def validate_text(request: ValidationRequest):
    """Validate entities in generated text"""
    try:
        # Extract entities from text
        extracted_entities = extract_entities(request.text)
        
        if not extracted_entities:
            return ValidationResponse(
                is_safe=True,
                entities=[],
                validated_text=request.text,
                warnings=["No entities detected in text"]
            )
        
        # Validate entities
        valid_entities, invalid_entities = validate_entities(extracted_entities)
        
        # Check for negative quantities (new validation)
        negative_qty_detected = check_negative_quantities(request.text)
        if negative_qty_detected:
            raise HTTPException(status_code=422, detail="Negative quantity detected in forecast")
        
        warnings = []
        if invalid_entities:
            warnings.append(f"Invalid entities detected: {', '.join(invalid_entities)}")
        
        # Consider text safe if all entities are valid
        is_safe = len(invalid_entities) == 0
        
        # If unsafe, create sanitized version
        validated_text = request.text
        if not is_safe:
            for invalid_entity in invalid_entities:
                validated_text = validated_text.replace(invalid_entity, "[INVALID_ENTITY]")
            warnings.append("Text has been sanitized by replacing invalid entities")
        
        logger.info(f"Validation result: {len(valid_entities)} valid, {len(invalid_entities)} invalid entities")
        
        return ValidationResponse(
            is_safe=is_safe,
            entities=valid_entities,
            validated_text=validated_text,
            warnings=warnings
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions (like 422)
        raise
    except Exception as e:
        logger.error(f"Validation error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

def check_negative_quantities(text: str) -> bool:
    """Check if text contains negative quantities in forecasts"""
    import re
    
    # Look for negative numbers associated with quantity/units/forecast
    negative_patterns = [
        r'-\d+\s*(units?|qty|quantity|forecast|demand)',
        r'(units?|qty|quantity|forecast|demand)\s*:\s*-\d+',
        r'predicted[_\s]*units?\s*:\s*-\d+',
        r'forecast[_\s]*units?\s*:\s*-\d+'
    ]
    
    text_lower = text.lower()
    for pattern in negative_patterns:
        if re.search(pattern, text_lower):
            logger.warning(f"Negative quantity detected with pattern: {pattern}")
            return True
    
    return False

@app.get("/catalog")
async def get_entity_catalog():
    """Get list of valid entities"""
    return {"entities": list(VALID_ENTITIES)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)