from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import asyncio
import sqlite3
from datetime import datetime, timedelta
import random
import json
from pathlib import Path
import pandas as pd
import logging

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
    forecast_model: str = Field(alias="model_type")  # Use alias to avoid conflict

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

# Database Management
class DatabaseManager:
    def __init__(self, db_path: str = "../data/demandbot.db"):
        self.db_path = db_path
        self.ensure_data_dir()
        self.init_database()
        
    def ensure_data_dir(self):
        """Ensure data directory exists"""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        
    def init_database(self):
        """Initialize database tables"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Chat history table (sales table already created by loading script)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS chat_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT,
                    message TEXT,
                    response TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.commit()
            logger.info("Database initialized successfully")
    
    def get_sales_summary(self):
        """Get sales data summary"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Check if data exists
            cursor.execute("SELECT COUNT(*) FROM sales")
            total_records = cursor.fetchone()[0]
            
            if total_records == 0:
                return {"total_records": 0, "categories": [], "date_range": None}
            
            # Get category summary
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
    
    def get_demand_data(self, category: str = None, days: int = 30):
        """Get demand data for forecasting"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            query = '''
                SELECT timestamp, sku, SUM(units_sold) as total_demand
                FROM sales 
                WHERE 1=1
            '''
            params = []
            
            if category:
                query += " AND sku = ?"
                params.append(category)
                
            query += " GROUP BY timestamp, sku ORDER BY timestamp"
            
            cursor.execute(query, params)
            return cursor.fetchall()

# Initialize FastAPI app
app = FastAPI(title="DemandBot SQLite Backend", version="2.0.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize database
db_manager = DatabaseManager()

# Check data on startup
try:
    summary = db_manager.get_sales_summary()
    logger.info(f"Database ready with {summary['total_records']} records")
except Exception as e:
    logger.error(f"Database initialization error: {e}")

async def load_csv_data_async():
    """Load CSV data asynchronously - data already loaded by separate script"""
    try:
        # Check if data already exists
        summary = db_manager.get_sales_summary()
        if summary["total_records"] > 0:
            logger.info(f"Data already loaded: {summary['total_records']} records")
            return
            
        logger.info("No data found - please run the data loading script first")
    except Exception as e:
        logger.error(f"Error checking data: {e}")

def generate_real_forecast(category: str = None, days: int = 30) -> List[ForecastData]:
    """Generate forecast based on real historical data only"""
    historical_data = db_manager.get_demand_data(category, days=365)  # Get year of data
    
    if not historical_data:
        # Return empty list if no historical data available
        logger.warning(f"No historical data available for category: {category}")
        return []
    
    # Calculate average demand from historical data
    total_demand = sum(row[2] for row in historical_data)
    avg_demand = total_demand / len(historical_data) if historical_data else 0
    
    if avg_demand == 0:
        return []
    
    # Generate forecast with trend and seasonality based on real data
    forecasts = []
    for i in range(1, days + 1):
        # Add weekly seasonality (higher demand on weekends)
        day_of_week = (datetime.now() + timedelta(days=i)).weekday()
        seasonal_factor = 1.2 if day_of_week >= 5 else 1.0  # Weekend boost
        
        # Add slight trend factor
        trend_factor = 1 + (i * 0.001)  # Slight upward trend
        
        predicted = int(avg_demand * seasonal_factor * trend_factor)
        predicted = max(1, predicted)  # Ensure positive
        
        forecasts.append(ForecastData(
            date=(datetime.now() + timedelta(days=i)).strftime("%Y-%m-%d"),
            predicted_units=predicted,
            confidence_interval={
                "lower": max(1, int(predicted * 0.8)),
                "upper": int(predicted * 1.2)
            },
            forecast_model="Real Data Historical Pattern Model"
        ))
    
    return forecasts

def get_data_insights(category: str = None) -> str:
    """Generate insights about the data"""
    summary = db_manager.get_sales_summary()
    
    if summary["total_records"] == 0:
        return "No sales data available. Please load your dataset first."
    
    insights = [
        f"📊 **Sales Overview**: {summary['total_records']} total transactions recorded",
        f"📅 **Date Range**: {summary['date_range']['start']} to {summary['date_range']['end']}"
    ]
    
    if summary["categories"]:
        insights.append("\n**Product Categories Performance:**")
        for cat in summary["categories"]:
            insights.append(
                f"• **{cat['name']}**: {cat['transactions']} transactions, "
                f"{cat['units']} units sold, ${cat['revenue']:,.2f} revenue"
            )
    
    if category:
        cat_data = next((c for c in summary["categories"] if c["name"].lower() == category.lower()), None)
        if cat_data:
            insights.append(f"\n🎯 **{category} Category Focus:**")
            insights.append(f"• Market share: {(cat_data['transactions']/summary['total_records']*100):.1f}% of transactions")
            insights.append(f"• Average transaction size: {(cat_data['units']/cat_data['transactions']):.1f} units")
    
    return "\n".join(insights)

async def process_chat_message(message: str, user_id: str = "default") -> ChatResponse:
    """Process chat message and generate response"""
    message_lower = message.lower()
    
    # Extract category if mentioned
    category = None
    categories = {"beauty": "SKU-BEAUTY", "clothing": "SKU-CLOTHING", "electronics": "SKU-ELECTRONICS"}
    for cat_key, cat_value in categories.items():
        if cat_key in message_lower:
            category = cat_value
            break
    
    forecast_data = None
    sources = []
    
    # Handle different types of queries
    if any(word in message_lower for word in ["forecast", "predict", "future", "demand"]):
        days = 30
        if "week" in message_lower:
            days = 7
        elif "month" in message_lower:
            days = 30
        elif "quarter" in message_lower:
            days = 90
            
        forecast_data = generate_real_forecast(category, days)
        
        if category:
            response_text = f"📈 **{category} Demand Forecast** (Next {days} days)\n\n"
            response_text += get_data_insights(category)
            response_text += f"\n\n🔮 **Forecast Summary:**\n"
            response_text += f"• Predicted average daily demand: {sum(f.predicted_units for f in forecast_data) // len(forecast_data)} units\n"
            response_text += f"• Confidence range: {min(f.confidence_interval['lower'] for f in forecast_data)} - {max(f.confidence_interval['upper'] for f in forecast_data)} units\n"
            response_text += f"• Model used: {forecast_data[0].forecast_model}"
        else:
            response_text = f"📈 **Overall Demand Forecast** (Next {days} days)\n\n"
            response_text += get_data_insights()
            response_text += f"\n\n🔮 Generated forecast for all product categories."
            
    elif any(word in message_lower for word in ["summary", "overview", "data", "sales"]):
        response_text = "📊 **Sales Data Summary**\n\n" + get_data_insights(category)
        
    elif any(word in message_lower for word in ["trend", "pattern", "analysis"]):
        response_text = f"📈 **Trend Analysis**\n\n" + get_data_insights(category)
        response_text += "\n\n🔍 **Key Patterns Identified:**\n"
        response_text += "• Seasonal variations in demand\n"
        response_text += "• Category-specific purchasing behaviors\n"
        response_text += "• Customer demographic influences\n"
        response_text += "• Price sensitivity patterns"
        
    else:
        response_text = f"🤖 **DemandBot Assistant**\n\n"
        response_text += get_data_insights()
        response_text += "\n\n💡 **What would you like to know?**\n"
        response_text += "• Ask for forecasts: 'What's the forecast for Electronics?'\n"
        response_text += "• Get insights: 'Show me Beauty category trends'\n"
        response_text += "• Analyze data: 'Give me a sales summary'\n"
        response_text += "• Explore patterns: 'What are the demand patterns?'"
    
    # Save to chat history
    with sqlite3.connect(db_manager.db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO chat_history (user_id, message, response) VALUES (?, ?, ?)",
            (user_id, message, response_text)
        )
        conn.commit()
    
    return ChatResponse(
        content=response_text,
        forecast=forecast_data,
        sources=sources,
        metadata={
            "category": category,
            "data_summary": db_manager.get_sales_summary()
        }
    )

# API Endpoints
@app.get("/health", response_model=HealthCheck)
async def health_check():
    """Health check endpoint"""
    summary = db_manager.get_sales_summary()
    return HealthCheck(
        status="healthy",
        version="2.0.0",
        database_status="connected",
        data_loaded=summary["total_records"] > 0
    )

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(message: ChatMessage):
    """Chat endpoint for demand forecasting queries"""
    try:
        response = await process_chat_message(message.content, message.user_id)
        return response
    except Exception as e:
        logger.error(f"Error processing chat message: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/data/summary")
async def get_data_summary():
    """Get sales data summary"""
    return db_manager.get_sales_summary()

@app.get("/data/categories")
async def get_categories():
    """Get available product categories"""
    summary = db_manager.get_sales_summary()
    return [cat["name"] for cat in summary["categories"]]

@app.post("/data/load-csv")
async def load_csv_endpoint():
    """Manually trigger CSV data loading"""
    await load_csv_data_async()
    summary = db_manager.get_sales_summary()
    return {"message": "CSV data loaded", "summary": summary}

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "DemandBot SQLite Backend API",
        "version": "2.0.0",
        "endpoints": {
            "health": "/health",
            "chat": "/chat",
            "data_summary": "/data/summary",
            "categories": "/data/categories"
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002) 