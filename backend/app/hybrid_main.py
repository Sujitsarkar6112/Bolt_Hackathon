from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import sqlite3
from datetime import datetime, timedelta
import logging
import json
import aiohttp
import asyncio
from contextlib import asynccontextmanager

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Data Models
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
    metadata: Optional[Dict[str, Any]] = None

class HealthCheck(BaseModel):
    status: str
    version: str
    database_status: str
    data_loaded: bool
    rag_service_status: str
    llm_connected: bool

# RAG Service Integration
class RAGClient:
    def __init__(self, rag_url: str = "http://localhost:8001"):
        self.rag_url = rag_url
        self.session = None
        
    async def initialize(self):
        """Initialize HTTP session"""
        self.session = aiohttp.ClientSession()
        
    async def close(self):
        """Close HTTP session"""
        if self.session:
            await self.session.close()
            
    async def ask_question(self, query: str, sku: Optional[str] = None) -> Optional[Dict]:
        """Ask a question to the RAG service"""
        if not self.session:
            return None
            
        try:
            payload = {
                "query": query,
                "top_k": 4
            }
            if sku:
                payload["sku"] = sku
                
            async with self.session.post(
                f"{self.rag_url}/ask",
                json=payload,
                timeout=30
            ) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.error(f"RAG service error: {response.status}")
                    return None
        except Exception as e:
            logger.error(f"RAG service request failed: {e}")
            return None
            
    async def health_check(self) -> bool:
        """Check RAG service health"""
        if not self.session:
            return False
            
        try:
            async with self.session.get(
                f"{self.rag_url}/health",
                timeout=5
            ) as response:
                return response.status == 200
        except Exception:
            return False

# Database helper functions (same as before)
def get_database_summary():
    """Get summary of the real sales data"""
    try:
        with sqlite3.connect("../data/demandbot.db") as conn:
            cursor = conn.cursor()
            
            # Get total records
            cursor.execute("SELECT COUNT(*) FROM sales")
            total_records = cursor.fetchone()[0]
            
            # Get SKU breakdown
            cursor.execute('''
                SELECT sku, 
                       COUNT(*) as transactions,
                       SUM(units_sold) as total_units,
                       SUM(revenue) as total_revenue
                FROM sales 
                GROUP BY sku
            ''')
            categories = cursor.fetchall()
            
            # Get date range
            cursor.execute("SELECT MIN(timestamp), MAX(timestamp) FROM sales")
            date_range = cursor.fetchone()
            
            return {
                "total_records": total_records,
                "categories": [{"name": cat[0], "transactions": cat[1], 
                              "units": cat[2], "revenue": cat[3]} for cat in categories],
                "date_range": {"start": date_range[0], "end": date_range[1]}
            }
    except Exception as e:
        logger.error(f"Database error: {e}")
        return {"total_records": 0, "categories": [], "date_range": None}

def get_historical_demand(sku: str = None):
    """Get historical demand data for a specific SKU"""
    try:
        with sqlite3.connect("../data/demandbot.db") as conn:
            cursor = conn.cursor()
            
            if sku:
                cursor.execute('''
                    SELECT timestamp, SUM(units_sold) as daily_demand
                    FROM sales 
                    WHERE sku = ?
                    GROUP BY timestamp
                    ORDER BY timestamp
                ''', (sku,))
            else:
                cursor.execute('''
                    SELECT timestamp, SUM(units_sold) as daily_demand
                    FROM sales 
                    GROUP BY timestamp
                    ORDER BY timestamp
                ''')
            
            return cursor.fetchall()
    except Exception as e:
        logger.error(f"Error getting historical data: {e}")
        return []

def generate_forecast_from_data(sku: str = None, days: int = 30) -> List[ForecastData]:
    """Generate forecast based on real historical data"""
    historical_data = get_historical_demand(sku)
    
    if not historical_data:
        # Return empty forecast if no data available
        logger.warning(f"No historical data available for SKU: {sku}")
        return []
    
    # Calculate statistics from real data
    demands = [row[1] for row in historical_data]
    avg_demand = sum(demands) / len(demands)
    
    # Simple forecasting based on recent trend
    recent_data = demands[-7:] if len(demands) >= 7 else demands  # Last week or all data
    recent_avg = sum(recent_data) / len(recent_data)
    trend = (recent_avg - avg_demand) / avg_demand if avg_demand > 0 else 0
    
    forecasts = []
    for i in range(1, days + 1):
        # Apply trend and seasonal factors
        seasonal_factor = 1.2 if (i % 7) in [5, 6] else 1.0  # Weekend boost
        trend_factor = 1 + (trend * (i / 30))  # Apply trend over time
        
        base_prediction = recent_avg * seasonal_factor * trend_factor
        predicted = max(1, int(base_prediction))
        
        forecasts.append(ForecastData(
            date=(datetime.now() + timedelta(days=i)).strftime("%Y-%m-%d"),
            predicted_units=predicted,
            confidence_interval={
                "lower": max(1, int(predicted * 0.8)),
                "upper": int(predicted * 1.2)
            },
            model_used="Historical Pattern Analysis + LLM Enhanced"
        ))
    
    return forecasts

def generate_insights(sku: str = None) -> str:
    """Generate insights based on real data"""
    summary = get_database_summary()
    
    if summary["total_records"] == 0:
        return "⚠️ No sales data available. Please ensure the database is loaded with your retail data."
    
    insights = [
        f"📊 **Real Sales Data Analysis**",
        f"📈 **Total Transactions**: {summary['total_records']:,}",
        f"📅 **Period**: {summary['date_range']['start'][:10]} to {summary['date_range']['end'][:10]}"
    ]
    
    if summary["categories"]:
        insights.append("\n**📦 Product Performance:**")
        for cat in summary["categories"]:
            category_name = cat['name'].replace('SKU-', '')
            insights.append(
                f"• **{category_name}**: {cat['transactions']} transactions, "
                f"{cat['units']} units, ${cat['revenue']:,.0f} revenue"
            )
            
            if sku and cat['name'] == sku:
                avg_units = cat['units'] / cat['transactions']
                avg_revenue = cat['revenue'] / cat['transactions']
                insights.append(f"  - Average per transaction: {avg_units:.1f} units, ${avg_revenue:.0f}")
    
    if sku:
        historical = get_historical_demand(sku)
        if historical:
            total_days = len(historical)
            total_demand = sum(row[1] for row in historical)
            avg_daily = total_demand / total_days
            
            insights.append(f"\n🎯 **{sku.replace('SKU-', '')} Category Focus:**")
            insights.append(f"• Average daily demand: {avg_daily:.1f} units")
            insights.append(f"• Historical data points: {total_days} days")
            
            # Find peak day
            peak_day = max(historical, key=lambda x: x[1])
            insights.append(f"• Peak demand: {peak_day[1]} units on {peak_day[0][:10]}")
    
    return "\n".join(insights)

# WebSocket Connection Manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket connected. Total connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        logger.info(f"WebSocket disconnected. Total connections: {len(self.active_connections)}")

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

# Initialize services
rag_client = RAGClient()
manager = ConnectionManager()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management"""
    # Startup
    await rag_client.initialize()
    logger.info("🚀 Hybrid backend started with RAG integration")
    
    # Check database and RAG service on startup
    try:
        summary = get_database_summary()
        logger.info(f"🎉 Connected to database with {summary['total_records']} sales transactions")
        
        rag_healthy = await rag_client.health_check()
        logger.info(f"🤖 RAG service status: {'Connected' if rag_healthy else 'Disconnected'}")
    except Exception as e:
        logger.error(f"❌ Startup check failed: {e}")
    
    yield
    
    # Shutdown
    await rag_client.close()
    logger.info("🛑 Hybrid backend shutdown complete")

# Initialize FastAPI app with lifespan
app = FastAPI(
    title="DemandBot Hybrid Backend", 
    version="2.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

async def process_chat_message(message: str, user_id: str = "default") -> ChatResponse:
    """Process chat message with hybrid real data + LLM analysis"""
    message_lower = message.lower()
    
    # Extract SKU if mentioned
    sku = None
    sku_mapping = {"beauty": "SKU-BEAUTY", "clothing": "SKU-CLOTHING", "electronics": "SKU-ELECTRONICS"}
    for keyword, sku_code in sku_mapping.items():
        if keyword in message_lower:
            sku = sku_code
            break
    
    forecast_data = None
    sources = []
    
    # Get real data insights
    data_insights = generate_insights(sku)
    
    # Try to get LLM insights from RAG service
    llm_response = None
    try:
        # Enhance the query with context from real data
        enhanced_query = f"""
        Based on the following real sales data context, please provide additional insights:
        
        Real Data Summary: {data_insights[:500]}...
        
        User Question: {message}
        
        Please provide strategic insights, recommendations, or analysis that complements this data.
        """
        
        llm_response = await rag_client.ask_question(enhanced_query, sku)
    except Exception as e:
        logger.error(f"LLM request failed: {e}")
    
    # Handle different query types
    if any(word in message_lower for word in ["forecast", "predict", "future", "demand"]):
        days = 30
        if "week" in message_lower:
            days = 7
        elif "month" in message_lower:
            days = 30
        elif "quarter" in message_lower:
            days = 90
            
        forecast_data = generate_forecast_from_data(sku, days)
        
        if sku:
            category_name = sku.replace('SKU-', '')
            response_text = f"📈 **{category_name} Demand Forecast** (Hybrid Analysis)\n\n"
        else:
            response_text = f"📈 **Overall Demand Forecast** (Hybrid Analysis)\n\n"
            
        # Add real data insights
        response_text += "## 📊 Real Data Analysis\n" + data_insights + "\n\n"
        
        # Add forecast summary
        if forecast_data:
            response_text += f"## 🔮 Forecast Summary ({days} days)\n"
            avg_prediction = sum(f.predicted_units for f in forecast_data) // len(forecast_data)
            response_text += f"• Predicted average daily demand: {avg_prediction} units\n"
            response_text += f"• Range: {min(f.confidence_interval['lower'] for f in forecast_data)} - {max(f.confidence_interval['upper'] for f in forecast_data)} units\n"
            response_text += f"• Model: {forecast_data[0].model_used}\n\n"
        
        # Add LLM insights if available
        if llm_response and llm_response.get('answer'):
            response_text += "## 🤖 AI Strategic Insights\n" + llm_response['answer']
            if llm_response.get('sources'):
                sources = [
                    DocumentSource(
                        document=source['document'],
                        page=source.get('page'),
                        relevance_score=source['relevance_score'],
                        excerpt=source['content'][:200] + "..."
                    )
                    for source in llm_response['sources']
                ]
        else:
            response_text += "## 🤖 AI Insights\n*LLM analysis temporarily unavailable - showing data-driven insights only*"
            
    elif any(word in message_lower for word in ["summary", "overview", "data", "sales"]):
        response_text = "## 📊 **Hybrid Sales Analysis**\n\n"
        response_text += "### Real Data Summary\n" + data_insights + "\n\n"
        
        if llm_response and llm_response.get('answer'):
            response_text += "### 🤖 AI-Powered Insights\n" + llm_response['answer']
            if llm_response.get('sources'):
                sources = [
                    DocumentSource(
                        document=source['document'],
                        page=source.get('page'),
                        relevance_score=source['relevance_score'],
                        excerpt=source['content'][:200] + "..."
                    )
                    for source in llm_response['sources']
                ]
        else:
            response_text += "### 🤖 AI Insights\n*AI analysis will be added when RAG service is available*"
        
    elif any(word in message_lower for word in ["trend", "pattern", "analysis"]):
        response_text = f"## 📈 **Hybrid Trend Analysis**\n\n"
        response_text += "### Real Data Patterns\n" + data_insights + "\n\n"
        
        if llm_response and llm_response.get('answer'):
            response_text += "### 🤖 Advanced Pattern Recognition\n" + llm_response['answer']
            if llm_response.get('sources'):
                sources = [
                    DocumentSource(
                        document=source['document'],
                        page=source.get('page'),
                        relevance_score=source['relevance_score'],
                        excerpt=source['content'][:200] + "..."
                    )
                    for source in llm_response['sources']
                ]
        else:
            response_text += "### 🤖 AI Analysis\n*Advanced pattern recognition will be enhanced with LLM when available*"
            
        response_text += "\n\n### 🔍 **Key Insights:**\n"
        response_text += "• Analysis combines real transaction data with AI intelligence\n"
        response_text += "• Seasonal patterns identified from historical sales\n"
        response_text += "• Category-specific performance tracking\n"
        response_text += "• Strategic recommendations based on data + domain knowledge"
        
    else:
        response_text = f"## 🤖 **DemandBot - Hybrid Analytics Platform**\n\n"
        response_text += "### Your Current Data\n" + data_insights + "\n\n"
        
        if llm_response and llm_response.get('answer'):
            response_text += "### 🤖 AI Assistant Response\n" + llm_response['answer'] + "\n\n"
            if llm_response.get('sources'):
                sources = [
                    DocumentSource(
                        document=source['document'],
                        page=source.get('page'),
                        relevance_score=source['relevance_score'],
                        excerpt=source['content'][:200] + "..."
                    )
                    for source in llm_response['sources']
                ]
        
        response_text += "### 💡 **Available Commands:**\n"
        response_text += "• 'Forecast Electronics demand' - Get AI-enhanced predictions\n"
        response_text += "• 'Analyze Beauty trends' - Hybrid data + AI insights\n"
        response_text += "• 'Give me a sales summary' - Complete overview\n"
        response_text += "• Ask any business question - AI will analyze your data"
    
    return ChatResponse(
        content=response_text,
        forecast=forecast_data,
        sources=sources,
        metadata={
            "sku": sku,
            "data_summary": get_database_summary(),
            "based_on_real_data": True,
            "llm_enhanced": llm_response is not None,
            "rag_service_used": llm_response is not None,
            "model_used": llm_response.get('model_used', 'Data Analysis Only') if llm_response else 'Data Analysis Only'
        }
    )

# API Endpoints
@app.get("/health", response_model=HealthCheck)
async def health_check():
    """Health check with real data and RAG service status"""
    summary = get_database_summary()
    rag_healthy = await rag_client.health_check()
    
    return HealthCheck(
        status="healthy",
        version="2.0.0",
        database_status="connected" if summary["total_records"] > 0 else "no_data",
        data_loaded=summary["total_records"] > 0,
        rag_service_status="connected" if rag_healthy else "disconnected",
        llm_connected=rag_healthy
    )

@app.websocket("/chat")
async def websocket_chat_endpoint(websocket: WebSocket):
    """WebSocket chat endpoint with hybrid functionality"""
    await manager.connect(websocket)
    try:
        while True:
            # Receive message from WebSocket
            data = await websocket.receive_text()
            
            try:
                # Parse incoming message
                message_data = json.loads(data)
                content = message_data.get("content", "")
                user_id = message_data.get("user_id", "default")
                
                logger.info(f"WebSocket hybrid message from {user_id}: {content}")
                
                # Process the message with hybrid functionality
                response = await process_chat_message(content, user_id)
                
                # Send response back in the expected WebSocket format
                response_data = {
                    "content": response.content,
                    "forecast": [f.dict() for f in response.forecast] if response.forecast else None,
                    "sources": [s.dict() for s in response.sources] if response.sources else None,
                    "metadata": response.metadata
                }
                
                ws_message = {
                    "type": "chat_response",
                    "data": response_data,
                    "id": user_id,
                    "timestamp": datetime.now().isoformat()
                }
                
                await manager.send_personal_message(json.dumps(ws_message), websocket)
                
            except json.JSONDecodeError:
                # Handle plain text messages
                logger.info(f"WebSocket plain text: {data}")
                response = await process_chat_message(data, "websocket_user")
                
                response_data = {
                    "content": response.content,
                    "forecast": [f.dict() for f in response.forecast] if response.forecast else None,
                    "sources": [s.dict() for s in response.sources] if response.sources else None,
                    "metadata": response.metadata
                }
                
                ws_message = {
                    "type": "chat_response",
                    "data": response_data,
                    "id": "websocket_user",
                    "timestamp": datetime.now().isoformat()
                }
                
                await manager.send_personal_message(json.dumps(ws_message), websocket)
                
            except Exception as e:
                logger.error(f"Error processing WebSocket message: {e}")
                error_data = {
                    "error": f"Error processing your message: {str(e)}",
                    "code": "PROCESSING_ERROR",
                    "details": {"original_message": data}
                }
                
                ws_error = {
                    "type": "error",
                    "data": error_data,
                    "timestamp": datetime.now().isoformat()
                }
                await manager.send_personal_message(json.dumps(ws_error), websocket)
                
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        logger.info("WebSocket client disconnected")

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(message: ChatMessage):
    """HTTP POST chat endpoint with hybrid functionality"""
    try:
        response = await process_chat_message(message.content, message.user_id)
        return response
    except Exception as e:
        logger.error(f"Error processing chat message: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/data/summary")
async def get_data_summary():
    """Get real sales data summary"""
    return get_database_summary()

@app.get("/data/categories")
async def get_categories():
    """Get available SKUs"""
    summary = get_database_summary()
    return [cat["name"] for cat in summary["categories"]]

@app.get("/rag/status")
async def get_rag_status():
    """Get RAG service status"""
    healthy = await rag_client.health_check()
    return {
        "rag_service_connected": healthy,
        "rag_url": rag_client.rag_url,
        "status": "connected" if healthy else "disconnected"
    }

@app.get("/")
async def root():
    """Root endpoint"""
    summary = get_database_summary()
    rag_healthy = await rag_client.health_check()
    
    return {
        "message": "DemandBot Hybrid Analytics API - Real Data + LLM Intelligence",
        "version": "2.0.0",
        "data_loaded": summary["total_records"] > 0,
        "total_transactions": summary["total_records"],
        "llm_connected": rag_healthy,
        "capabilities": [
            "Real sales data analysis",
            "AI-powered insights",
            "Hybrid forecasting",
            "Document-grounded responses"
        ],
        "endpoints": {
            "health": "/health",
            "chat": "/chat (WebSocket + HTTP)",
            "data_summary": "/data/summary",
            "categories": "/data/categories",
            "rag_status": "/rag/status"
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8004) 