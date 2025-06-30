from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import asyncio
from datetime import datetime, timedelta
import random
import json

# Data Models
class ChatMessage(BaseModel):
    content: str
    user_id: Optional[str] = "default"

class ForecastData(BaseModel):
    date: str
    predicted_units: int
    confidence_interval: Optional[Dict[str, int]] = None
    model_type: str  # Changed from model_used to avoid Pydantic warning

class DocumentSource(BaseModel):
    document: str
    page: Optional[int] = None
    relevance_score: float
    excerpt: str

class ChatResponse(BaseModel):
    content: str
    forecast: Optional[List[ForecastData]] = None
    sources: Optional[List[DocumentSource]] = None
    entities: Optional[List[str]] = None

app = FastAPI(
    title="DemandBot API", 
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Sample data generators
def generate_forecast_data(sku: str) -> List[ForecastData]:
    """Generate realistic forecast data for a given SKU"""
    base_demand = random.randint(1000, 2000)
    data = []
    
    for i in range(6):  # 6 weeks forecast
        date = (datetime.now() + timedelta(weeks=i)).strftime("%Y-%m-%d")
        predicted = int(base_demand * (1 + i * 0.1) * random.uniform(0.9, 1.2))
        
        data.append(ForecastData(
            date=date,
            predicted_units=predicted,
            confidence_interval={
                "lower": int(predicted * 0.85),
                "upper": int(predicted * 1.15)
            },
            model_type="Hybrid_Prophet_TFT"
        ))
    
    return data

def get_sample_sources() -> List[DocumentSource]:
    """Return sample document sources"""
    return [
        DocumentSource(
            document="Q4_Marketing_Strategy.pdf",
            page=12,
            relevance_score=0.92,
            excerpt="Valentine's Day promotional campaign scheduled with 25% discount and influencer partnerships."
        ),
        DocumentSource(
            document="Product_Launch_Calendar_2024.md",
            page=3,
            relevance_score=0.85,
            excerpt="New product variant expected to drive 15-20% incremental sales during launch window."
        )
    ]

# Mock entity validation
VALID_ENTITIES = {
    "SKU-ABC", "SKU-XYZ", "SKU-ABC-V2", "Product-X", "Product-Y", 
    "CAMPAIGN-2024-VAL", "PROMO-WINTER-23"
}

def validate_entities(text: str) -> List[str]:
    """Extract and validate entities from text"""
    import re
    sku_pattern = r'SKU-[A-Z0-9-]+'
    product_pattern = r'Product-[A-Z0-9-]+'
    
    found_entities = []
    found_entities.extend(re.findall(sku_pattern, text))
    found_entities.extend(re.findall(product_pattern, text))
    
    valid_found = [entity for entity in found_entities if entity in VALID_ENTITIES]
    return list(set(valid_found))

# API Endpoints
@app.get("/health")
async def health_check():
    """Simple health check without MongoDB dependency"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "mongodb_connected": False,
        "message": "Running in simple mode (no database)"
    }

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(message: ChatMessage):
    """Main chat endpoint for DemandBot"""
    try:
        # Simulate processing delay
        await asyncio.sleep(1)
        
        content = message.content.lower()
        response = ChatResponse(content="")
        
        # Extract entities from user input
        entities = validate_entities(message.content)
        if entities:
            response.entities = entities
        
        # Route based on content
        if "forecast" in content and ("sku-abc" in content or "abc" in content):
            response.content = """Based on our hybrid Prophet-TFT model analysis, SKU-ABC shows strong positive momentum for the next 6 weeks. The forecast indicates a 48% increase from current baseline, driven by several key factors:

**Key Drivers:**
• Valentine's Day promotional campaign (25% discount) launching February 1st
• New product variant SKU-ABC-V2 creating market buzz
• Seasonal uplift typical for this product category
• Strong inventory position supporting demand fulfillment

The model combines historical sales patterns with promotional calendar data and market intelligence from our enterprise knowledge base."""
            
            response.forecast = generate_forecast_data("SKU-ABC")
            response.sources = get_sample_sources()
            
        elif "compare" in content and "sku" in content:
            response.content = """I've analyzed the comparative forecast performance for the requested SKUs. Here's what the data reveals:

**SKU-ABC vs SKU-XYZ Performance:**
• SKU-ABC: Expected 48% growth over next 6 weeks (strong promotional support)
• SKU-XYZ: Projected 12% decline (end-of-lifecycle, inventory clearance)

**Key Differentiators:**
• Marketing investment: SKU-ABC receiving 3x more promotional budget
• Product lifecycle: ABC in growth phase, XYZ in decline
• Seasonal patterns: ABC benefits from Q1 seasonal uplift

**Recommendation:** Focus inventory allocation and marketing spend on SKU-ABC for Q1 optimization."""
            
        elif "promotion" in content or "marketing" in content:
            response.content = """Based on our enterprise knowledge base, here are the active promotions:

**Active Campaigns:**
• Valentine's Day Promotion (SKU-ABC): 25% discount + influencer partnerships
• Winter Clearance (SKU-XYZ): 40% discount, inventory optimization focus
• New Product Launch (SKU-ABC-V2): Sampling campaign + PR outreach

**Performance Insights:**
• Valentine's campaign showing 2.3x baseline engagement in pre-launch testing
• Clearance promotions effectively reducing excess inventory by 35%
• Launch campaign generating 15K+ social media impressions daily"""
            
            response.sources = get_sample_sources()
            
        else:
            response.content = """I can help you with demand forecasting and market insights. I can analyze:

• **Demand Forecasting**: Get predictions for specific SKUs or product categories
• **Trend Analysis**: Understand why forecasts are trending up or down
• **Promotional Impact**: Analyze how marketing campaigns affect demand
• **Comparative Analysis**: Compare performance across different products
• **Market Intelligence**: Access insights from enterprise documents and reports

Try asking: "What's the forecast for SKU-ABC?" or "Why is demand trending up for product X?"""
        
        return response
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/products")
async def get_products():
    """Get list of valid products/SKUs"""
    return {"products": list(VALID_ENTITIES)}

@app.post("/validate")
async def validate_text(data: dict):
    """Validate entities in generated text"""
    text = data.get("text", "")
    entities = validate_entities(text)
    
    return {
        "is_safe": len(entities) > 0,
        "entities": entities,
        "validated_text": text
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 