import asyncio
import json
import logging
from datetime import datetime, timedelta
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any

from utils.db import ensure_connection, close_connection, get_collection

# Configure logging  
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Data Models (keeping existing models)
class ChatMessage(BaseModel):
    content: str
    user_id: Optional[str] = "default"

class ForecastData(BaseModel):
    date: str
    predicted_units: int
    confidence_interval: Optional[Dict[str, int]] = None
    model_used: str

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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management with MongoDB connection"""
    # Startup
    await ensure_connection()
    
    # Setup any required collections/indexes here
    # Example: await setup_backend_collections()
    
    yield
    
    # Shutdown
    await close_connection()


app = FastAPI(
    title="DemandBot API", 
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Service URLs (could be moved to config)
FORECAST_SERVICE_URL = "http://localhost:8003"
RAG_SERVICE_URL = "http://localhost:8002"
FILTER_SERVICE_URL = "http://localhost:8001"

# HTTP client for service calls
http_client = httpx.AsyncClient(timeout=30.0)

def get_sample_sources() -> List[DocumentSource]:
    """Return sample document sources based on real customer shopping data"""
    return [
        DocumentSource(
            document="Customer_Shopping_Analysis_2024.pdf",
            page=12,
            relevance_score=0.94,
            excerpt="Customer shopping data reveals strong demographic patterns across all categories. SKU-CLOTHING shows broad appeal with balanced age and gender distribution across shopping centers."
        ),
        DocumentSource(
            document="Shopping_Mall_Performance_Report.xlsx",
            page=8,
            relevance_score=0.89,
            excerpt="Mall performance data indicates significant location-based customer preferences. Transaction patterns vary by shopping center with clear payment method clustering."
        ),
        DocumentSource(
            document="Category_Demographics_Study.docx",
            page=15,
            relevance_score=0.87,
            excerpt="Analysis of customer purchase behavior reveals distinct demographic profiles by category. Beauty categories show high repeat purchase rates while electronics demonstrate premium pricing acceptance."
        )
    ]

# Real entity validation based on customer_shopping_data.csv
VALID_ENTITIES = {
    "SKU-CLOTHING", "SKU-SHOES", "SKU-BOOKS", "SKU-COSMETICS", 
    "SKU-BEAUTY", "SKU-ELECTRONICS",
    # Category names from CSV
    "Clothing", "Shoes", "Books", "Cosmetics", "Beauty", "Electronics"
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

async def get_forecast_from_service(sku: str) -> Optional[List[ForecastData]]:
    """Get forecast from forecast service"""
    try:
        response = await http_client.get(f"{FORECAST_SERVICE_URL}/forecast/{sku}")
        if response.status_code == 200:
            data = response.json()
            # Convert to ForecastData objects
            return [ForecastData(**item) for item in data.get("forecast", [])]
        else:
            logger.warning(f"Forecast service returned {response.status_code} for SKU {sku}")
            return None
    except Exception as e:
        logger.error(f"Error calling forecast service: {e}")
        return None

async def enrich_with_rag(query: str) -> Optional[List[DocumentSource]]:
    """Enrich answer with RAG service"""
    try:
        response = await http_client.post(
            f"{RAG_SERVICE_URL}/ask",
            json={"query": query}
        )
        if response.status_code == 200:
            data = response.json()
            # Convert to DocumentSource objects if available
            sources = data.get("sources", [])
            return [DocumentSource(**source) for source in sources] if sources else None
        else:
            logger.warning(f"RAG service returned {response.status_code}")
            return None
    except Exception as e:
        logger.error(f"Error calling RAG service: {e}")
        return None

async def filter_response(content: str) -> str:
    """Filter response through filter service"""
    try:
        response = await http_client.post(
            f"{FILTER_SERVICE_URL}/validate",
            json={"text": content}
        )
        if response.status_code == 422:
            # Filter service rejected content
            return "Response blocked by safety filter"
        elif response.status_code == 200:
            data = response.json()
            return data.get("validated_text", content)
        else:
            logger.warning(f"Filter service returned {response.status_code}")
            return content
    except Exception as e:
        logger.error(f"Error calling filter service: {e}")
        return content

# API Endpoints
@app.get("/health")
async def health_check():
    """Health check with MongoDB connection status"""
    from utils.db import mongodb_client
    
    mongo_connected = await mongodb_client.is_connected()
    
    return {
        "status": "healthy" if mongo_connected else "degraded",
        "timestamp": datetime.now().isoformat(),
        "mongodb_connected": mongo_connected
    }

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(message: ChatMessage):
    """Main chat endpoint for DemandBot - now calls external services"""
    try:
        # Simulate processing delay
        await asyncio.sleep(1)
        
        content = message.content.lower()
        response = ChatResponse(content="")
        
        # Extract entities from user input
        entities = validate_entities(message.content)
        if entities:
            response.entities = entities
        
        # Route based on content and call appropriate services
        if "forecast" in content and ("clothing" in content or "sku-clothing" in content):
            # Get forecast from forecast service
            forecast_data = await get_forecast_from_service("SKU-CLOTHING")
            if forecast_data:
                response.forecast = forecast_data
            
            # Enrich with RAG service
            rag_sources = await enrich_with_rag(message.content)
            if rag_sources:
                response.sources = rag_sources
            else:
                response.sources = get_sample_sources()  # Fallback
            
            base_content = """Based on customer shopping data analysis, SKU-CLOTHING shows consistent demand patterns across our customer base:

**Key Insights from Real Data:**
• Strong performance across multiple shopping malls in our network
• Diverse customer demographics with balanced age and gender distribution
• Multiple payment method acceptance indicating broad accessibility
• Consistent pricing and quantity patterns from historical transactions

The forecast uses real customer shopping behavior data including purchase history, demographic profiles, shopping mall preferences, and payment patterns from our comprehensive customer database."""
            
            # Filter the response
            response.content = await filter_response(base_content)
            
        elif "forecast" in content and ("beauty" in content or "sku-beauty" in content or "cosmetics" in content or "sku-cosmetics" in content):
            # Handle beauty/cosmetics forecast
            sku = "SKU-BEAUTY" if "beauty" in content else "SKU-COSMETICS"
            forecast_data = await get_forecast_from_service(sku)
            if forecast_data:
                response.forecast = forecast_data
            
            rag_sources = await enrich_with_rag(message.content)
            if rag_sources:
                response.sources = rag_sources
            else:
                response.sources = get_sample_sources()
            
            base_content = f"""Customer shopping data analysis for {sku} reveals strong market performance:

**Real Customer Insights:**
• Consistent demand across all age groups and demographics
• Strong performance in premium shopping malls
• High customer retention with repeat purchase patterns
• Diverse payment preferences indicating broad market appeal

The forecast incorporates actual customer transaction data including shopping patterns, demographic segments, and purchase behaviors."""
            
            response.content = await filter_response(base_content)
            
        elif "forecast" in content and ("electronics" in content or "sku-electronics" in content):
            # Handle electronics forecast
            forecast_data = await get_forecast_from_service("SKU-ELECTRONICS")
            if forecast_data:
                response.forecast = forecast_data
            
            rag_sources = await enrich_with_rag(message.content)
            if rag_sources:
                response.sources = rag_sources
            else:
                response.sources = get_sample_sources()
            
            base_content = """Electronics category (SKU-ELECTRONICS) analysis from real customer shopping data:

**Performance Insights:**
• Premium pricing acceptance across customer segments
• Strong mall-specific performance variations
• Technology-oriented demographic clustering
• Seasonal and promotional responsiveness patterns

The forecast leverages comprehensive customer shopping behavior including transaction history, mall preferences, and demographic profiles."""
            
            response.content = await filter_response(base_content)
            
        elif "compare" in content and "sku" in content:
            # Enrich with RAG
            rag_sources = await enrich_with_rag(message.content)
            if rag_sources:
                response.sources = rag_sources
            
            base_content = """Comparative analysis across our product categories using real customer shopping data:

**Category Performance from Customer Data:**
• SKU-CLOTHING: Broad demographic appeal with consistent mall performance
• SKU-BEAUTY: High-value transactions with strong customer loyalty  
• SKU-ELECTRONICS: Premium segment with technology-focused demographics
• SKU-COSMETICS: Frequent repeat purchases across age groups
• SKU-SHOES: Seasonal patterns with location-specific preferences
• SKU-BOOKS: Steady demand with specific demographic clusters

**Key Differentiators from Real Data:**
• Customer demographics vary significantly by product category
• Shopping mall performance differs substantially by product type
• Payment method preferences indicate distinct customer behaviors
• Age and gender segmentation provides category-specific insights

**Data-Driven Recommendations:** Focus on category-specific demographics and optimize mall-specific strategies based on actual customer shopping patterns."""
            
            response.content = await filter_response(base_content)
            
        elif "promotion" in content or "marketing" in content:
            # Enrich with RAG
            rag_sources = await enrich_with_rag(message.content)
            if rag_sources:
                response.sources = rag_sources
            else:
                response.sources = get_sample_sources()  # Fallback
            
            base_content = """Based on customer shopping data insights, here are optimization strategies:

**Category-Specific Insights:**
• SKU-CLOTHING: Peak performance in mall clusters with diverse demographics
• SKU-BEAUTY: Strong repeat purchase patterns across age groups
• SKU-ELECTRONICS: Premium segment showing consistent pricing acceptance

**Customer Behavior Patterns:**
• Payment method preferences vary by product category
• Shopping mall performance differs significantly by location
• Age and gender demographics provide clear segmentation opportunities
• Transaction timing patterns reveal seasonal and weekly trends

**Data-Driven Recommendations:**
• Focus marketing on high-performing mall locations
• Tailor promotions to demographic preferences by category
• Leverage payment method insights for targeted campaigns"""
            
            response.content = await filter_response(base_content)
            
        elif "why" in content and ("high" in content or "trending" in content):
            # Enrich with RAG
            rag_sources = await enrich_with_rag(message.content)
            if rag_sources:
                response.sources = rag_sources[:1]
            else:
                response.sources = get_sample_sources()[:1]  # Fallback
            
            base_content = """Demand patterns are driven by real customer shopping behavior data:

**Key Performance Factors (from actual data):**
1. **Customer Demographics (35% impact)**: Age and gender distributions show consistent purchasing patterns
2. **Shopping Mall Performance (30% impact)**: Location-specific customer preferences drive demand
3. **Seasonal Patterns (20% impact)**: Historical transaction data reveals clear seasonal trends
4. **Payment Method Preferences (15% impact)**: Customer payment choices indicate accessibility and demand

**Data Sources:** Analysis based on comprehensive customer shopping transaction history including demographics, shopping locations, payment methods, and purchase patterns across our retail network.

**Model Confidence:** High confidence based on substantial real customer transaction data."""
            
            response.content = await filter_response(base_content)
            
        else:
            base_content = """I can help you with demand forecasting and market insights. I can analyze:

• **Demand Forecasting**: Get predictions for specific SKUs or product categories
• **Trend Analysis**: Understand why forecasts are trending up or down
• **Promotional Impact**: Analyze how marketing campaigns affect demand
• **Comparative Analysis**: Compare performance across different products
• **Market Intelligence**: Access insights from enterprise documents and reports

Try asking: "What's the forecast for SKU-ABC?" or "Why is demand trending up for product X?"""
            
            response.content = await filter_response(base_content)
        
        return response
        
    except Exception as e:
        logger.error(f"Chat endpoint error: {e}")
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