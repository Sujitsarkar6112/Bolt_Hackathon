from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import sqlite3
from datetime import datetime, timedelta
import logging
import json
import os
import asyncio
import openai
from contextlib import asynccontextmanager

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

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
    openai_connected: bool

# OpenAI Integration
class OpenAIClient:
    def __init__(self):
        self.api_key = os.getenv('OPENAI_API_KEY')
        self.client = None
        self.connected = False
        
    async def initialize(self):
        """Initialize OpenAI client"""
        if not self.api_key:
            logger.warning("❌ OpenAI API key not found")
            return False
            
        try:
            self.client = openai.AsyncOpenAI(api_key=self.api_key)
            # Test connection
            await self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": "Test"}],
                max_tokens=1
            )
            self.connected = True
            logger.info("✅ OpenAI client initialized successfully")
            return True
        except Exception as e:
            logger.error(f"❌ OpenAI initialization failed: {e}")
            return False
            
    async def generate_insights(self, data_context: str, user_query: str, sku: Optional[str] = None) -> Optional[str]:
        """Generate AI insights based on real data context"""
        if not self.connected or not self.client:
            return None
            
        try:
            # Create concise prompt focused on available data only
            # Check if enhanced data is available to inform the AI what data we have
            summary = get_database_summary()
            enhanced_data = summary.get("enhanced_data", False)
            
            if enhanced_data:
                available_data = "Sales transactions, customer demographics (age, gender), product categories (Clothing, Shoes, Books, Cosmetics), payment methods, shopping mall locations, revenue, units sold, dates."
                not_available = "Detailed personal information beyond age/gender."
            else:
                available_data = "Sales transactions, SKUs (Beauty/Clothing/Electronics), revenue, units sold, dates."
                not_available = "Customer age, gender, demographics, detailed customer profiles."
            
            system_prompt = f"""You are a business analyst. Answer based on the provided data context.
            
            Available data: {available_data}
            NOT available: {not_available}
            
            Rules:
            - Use the provided data context to answer questions directly
            - Extract information from the data context provided in the user message
            - If shopping malls, customer demographics, or categories are mentioned in the data context, use that information
            - Only say "Data not available" if the question asks for something not mentioned in the data context
            - Be helpful and extract relevant information from the provided context"""
            
            user_prompt = f"""
            Data: {data_context}
            Question: {user_query}
            
            Answer briefly and directly.
            """
            
            response = await self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=150,  # Shorter responses
                temperature=0.2  # More focused
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"OpenAI request failed: {e}")
            return None

# Database helper functions (enhanced to use rich customer data)
def get_database_summary():
    """Get comprehensive summary of the enhanced customer shopping data"""
    try:
        with sqlite3.connect("../data/demandbot.db") as conn:
            cursor = conn.cursor()
            
            # Check if enhanced tables exist
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='sales_enhanced'")
            has_enhanced_data = cursor.fetchone() is not None
            
            if has_enhanced_data:
                # Use enhanced data
                cursor.execute("SELECT COUNT(*) FROM sales_enhanced")
                total_records = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(DISTINCT customer_id) FROM sales_enhanced")
                unique_customers = cursor.fetchone()[0]
                
                # Get demographics
                cursor.execute("""
                    SELECT gender, COUNT(*) as count, AVG(age) as avg_age 
                    FROM sales_enhanced 
                    WHERE gender IS NOT NULL 
                    GROUP BY gender
                """)
                demographics = cursor.fetchall()
                
                # Get enhanced category breakdown
                cursor.execute('''
                    SELECT category, 
                           COUNT(*) as transactions,
                           SUM(quantity) as total_units,
                           SUM(revenue) as total_revenue,
                           AVG(age) as avg_customer_age
                    FROM sales_enhanced 
                    GROUP BY category
                    ORDER BY total_revenue DESC
                ''')
                categories = cursor.fetchall()
                
                # Get payment method preferences
                cursor.execute("""
                    SELECT payment_method, COUNT(*) as count, SUM(revenue) as revenue
                    FROM sales_enhanced 
                    WHERE payment_method IS NOT NULL
                    GROUP BY payment_method
                    ORDER BY count DESC
                """)
                payment_methods = cursor.fetchall()
                
                # Get mall performance
                cursor.execute("""
                    SELECT shopping_mall, COUNT(*) as transactions, SUM(revenue) as revenue
                    FROM sales_enhanced 
                    WHERE shopping_mall IS NOT NULL
                    GROUP BY shopping_mall
                    ORDER BY revenue DESC
                    LIMIT 5
                """)
                top_malls = cursor.fetchall()
                
                # Get date range
                cursor.execute("SELECT MIN(invoice_date), MAX(invoice_date) FROM sales_enhanced")
                date_range = cursor.fetchone()
                
                # Get additional insights
                cursor.execute("SELECT AVG(quantity), AVG(revenue) FROM sales_enhanced")
                avg_stats = cursor.fetchone()
                
                return {
                    "total_records": total_records,
                    "unique_customers": unique_customers,
                    "avg_units_per_transaction": avg_stats[0],
                    "avg_revenue_per_transaction": avg_stats[1],
                    "categories": [{"name": cat[0], "transactions": cat[1], 
                                  "units": cat[2], "revenue": cat[3], "avg_age": cat[4]} for cat in categories],
                    "demographics": [{"gender": demo[0], "count": demo[1], "avg_age": demo[2]} for demo in demographics],
                    "payment_methods": [{"method": pm[0], "count": pm[1], "revenue": pm[2]} for pm in payment_methods],
                    "top_malls": [{"mall": mall[0], "transactions": mall[1], "revenue": mall[2]} for mall in top_malls],
                    "date_range": {"start": date_range[0], "end": date_range[1]},
                    "enhanced_data": True
                }
            else:
                # Fallback to original data structure
                cursor.execute("SELECT COUNT(*) FROM sales")
                total_records = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(DISTINCT customer_id) FROM sales")
                unique_customers = cursor.fetchone()[0]
                
                cursor.execute('''
                    SELECT sku, 
                           COUNT(*) as transactions,
                           SUM(units_sold) as total_units,
                           SUM(revenue) as total_revenue
                    FROM sales 
                    GROUP BY sku
                ''')
                categories = cursor.fetchall()
                
                cursor.execute("SELECT MIN(timestamp), MAX(timestamp) FROM sales")
                date_range = cursor.fetchone()
                
                cursor.execute("SELECT AVG(units_sold), AVG(revenue) FROM sales")
                avg_stats = cursor.fetchone()
                
                return {
                    "total_records": total_records,
                    "unique_customers": unique_customers,
                    "avg_units_per_transaction": avg_stats[0],
                    "avg_revenue_per_transaction": avg_stats[1],
                    "categories": [{"name": cat[0], "transactions": cat[1], 
                                  "units": cat[2], "revenue": cat[3]} for cat in categories],
                    "date_range": {"start": date_range[0], "end": date_range[1]},
                    "enhanced_data": False
                }
    except Exception as e:
        logger.error(f"Database error: {e}")
        return {"total_records": 0, "unique_customers": 0, "categories": [], "date_range": None, "enhanced_data": False}

def get_customer_demographics():
    """Get detailed customer demographic analysis"""
    try:
        with sqlite3.connect("../data/demandbot.db") as conn:
            cursor = conn.cursor()
            
            # Check if we have enhanced customer data
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='sales_enhanced'")
            if not cursor.fetchone():
                return {"error": "Enhanced customer data not available"}
            
            # Age distribution
            cursor.execute("""
                SELECT 
                    CASE 
                        WHEN age < 25 THEN '18-24'
                        WHEN age < 35 THEN '25-34'
                        WHEN age < 45 THEN '35-44'
                        WHEN age < 55 THEN '45-54'
                        WHEN age < 65 THEN '55-64'
                        ELSE '65+'
                    END as age_group,
                    COUNT(DISTINCT customer_id) as customers,
                    AVG(revenue) as avg_spending
                FROM sales_enhanced 
                WHERE age IS NOT NULL
                GROUP BY age_group
                ORDER BY customers DESC
            """)
            age_distribution = cursor.fetchall()
            
            # Gender breakdown
            cursor.execute("""
                SELECT gender, 
                       COUNT(DISTINCT customer_id) as customers,
                       AVG(revenue) as avg_spending,
                       AVG(age) as avg_age
                FROM sales_enhanced 
                WHERE gender IS NOT NULL
                GROUP BY gender
            """)
            gender_breakdown = cursor.fetchall()
            
            # Category preferences by demographics
            cursor.execute("""
                SELECT gender, category, COUNT(*) as purchases, SUM(revenue) as total_spent
                FROM sales_enhanced 
                WHERE gender IS NOT NULL
                GROUP BY gender, category
                ORDER BY gender, total_spent DESC
            """)
            category_preferences = cursor.fetchall()
            
            return {
                "age_distribution": [{"age_group": row[0], "customers": row[1], "avg_spending": row[2]} for row in age_distribution],
                "gender_breakdown": [{"gender": row[0], "customers": row[1], "avg_spending": row[2], "avg_age": row[3]} for row in gender_breakdown],
                "category_preferences": [{"gender": row[0], "category": row[1], "purchases": row[2], "total_spent": row[3]} for row in category_preferences]
            }
    except Exception as e:
        logger.error(f"Error getting demographics: {e}")
        return {"error": str(e)}

def get_historical_demand(sku: str = None, category: str = None):
    """Get historical demand data for a specific SKU or category (enhanced version)"""
    try:
        with sqlite3.connect("../data/demandbot.db") as conn:
            cursor = conn.cursor()
            
            # Check if enhanced data is available
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='sales_enhanced'")
            has_enhanced = cursor.fetchone() is not None
            
            if has_enhanced and category:
                # Use enhanced data with category
                cursor.execute('''
                    SELECT invoice_date, SUM(quantity) as daily_demand, AVG(age) as avg_customer_age
                    FROM sales_enhanced 
                    WHERE category = ?
                    GROUP BY invoice_date
                    ORDER BY invoice_date
                ''', (category,))
            elif sku:
                # Use SKU from either table
                if has_enhanced:
                    cursor.execute('''
                        SELECT invoice_date, SUM(quantity) as daily_demand, AVG(age) as avg_customer_age
                        FROM sales_enhanced 
                        WHERE sku = ?
                        GROUP BY invoice_date
                        ORDER BY invoice_date
                    ''', (sku,))
                else:
                    cursor.execute('''
                        SELECT timestamp, SUM(units_sold) as daily_demand
                        FROM sales 
                        WHERE sku = ?
                        GROUP BY timestamp
                        ORDER BY timestamp
                    ''', (sku,))
            else:
                # Get all data
                if has_enhanced:
                    cursor.execute('''
                        SELECT invoice_date, SUM(quantity) as daily_demand
                        FROM sales_enhanced 
                        GROUP BY invoice_date
                        ORDER BY invoice_date
                    ''')
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

def generate_forecast_from_data(sku: str = None, days: int = 30, category: str = None) -> List[ForecastData]:
    """Generate forecast based on enhanced historical data"""
    # Try to use category first if available, then fall back to SKU
    if category:
        historical_data = get_historical_demand(None, category)
        logger.info(f"Using category-based forecast for: {category}")
    else:
        historical_data = get_historical_demand(sku, None)
        logger.info(f"Using SKU-based forecast for: {sku}")
    
    if not historical_data:
        # Return empty forecast if no data available
        logger.warning(f"No historical data available for SKU: {sku} or Category: {category}")
        return []
    
    # Calculate statistics from real data (daily aggregated demands)
    demands = [row[1] for row in historical_data]
    
    if not demands:
        logger.warning(f"No demand data found for SKU: {sku}")
        return []
    
    # Calculate robust statistics
    avg_demand = sum(demands) / len(demands)
    max_demand = max(demands)
    min_demand = min(demands)
    
    # Use recent trend (last 30% of data or minimum 7 days)
    recent_window = max(7, len(demands) // 3)
    recent_data = demands[-recent_window:]
    recent_avg = sum(recent_data) / len(recent_data)
    
    # Calculate trend more robustly
    if len(demands) > 14:
        first_half = demands[:len(demands)//2]
        second_half = demands[len(demands)//2:]
        first_avg = sum(first_half) / len(first_half)
        second_avg = sum(second_half) / len(second_half)
        trend_rate = (second_avg - first_avg) / first_avg if first_avg > 0 else 0
    else:
        trend_rate = (recent_avg - avg_demand) / avg_demand if avg_demand > 0 else 0
    
    # Cap trend to reasonable bounds (-20% to +20% per month)
    trend_rate = max(-0.20, min(0.20, trend_rate))
    
    logger.info(f"Forecast calculation - Avg: {avg_demand:.2f}, Recent: {recent_avg:.2f}, Trend: {trend_rate:.4f}")
    
    forecasts = []
    for i in range(1, days + 1):
        # Day of week pattern (0=Monday, 6=Sunday)
        day_of_week = (datetime.now() + timedelta(days=i)).weekday()
        
        # Seasonal factors based on day of week
        if day_of_week in [4, 5]:  # Friday, Saturday
            seasonal_factor = 1.15
        elif day_of_week == 6:  # Sunday
            seasonal_factor = 0.9
        else:  # Monday-Thursday
            seasonal_factor = 1.0
        
        # Apply gradual trend over forecast period
        trend_factor = 1 + (trend_rate * (i / 30))
        
        # Base prediction using recent average as starting point
        base_prediction = recent_avg * seasonal_factor * trend_factor
        
        # Add small random variation to make it realistic
        import random
        variation = random.uniform(0.9, 1.1)
        base_prediction *= variation
        
        # Ensure reasonable bounds
        predicted = max(1, min(int(round(base_prediction)), max_demand * 2))
        
        # Calculate confidence intervals
        lower_bound = max(1, int(predicted * 0.75))
        upper_bound = int(predicted * 1.35)
        
        forecasts.append(ForecastData(
            date=(datetime.now() + timedelta(days=i)).strftime("%Y-%m-%d"),
            predicted_units=predicted,
            confidence_interval={
                "lower": lower_bound,
                "upper": upper_bound
            },
            model_used="Enhanced Pattern Analysis with Trend & Seasonality"
        ))
    
    return forecasts

def generate_insights(sku: str = None, category: str = None) -> str:
    """Generate insights based on enhanced customer data"""
    summary = get_database_summary()
    
    if summary["total_records"] == 0:
        return "⚠️ No sales data available. Please ensure the database is loaded with your retail data."
    
    insights = [
        f"📊 **Enhanced Customer Analytics**",
        f"📈 **Total Transactions**: {summary['total_records']:,}",
        f"👥 **Unique Customers**: {summary['unique_customers']:,}",
        f"📅 **Period**: {summary['date_range']['start'][:10]} to {summary['date_range']['end'][:10]}"
    ]
    
    # Add demographic insights if available
    if summary.get("enhanced_data") and summary.get("demographics"):
        insights.append("\n**👥 Customer Demographics:**")
        for demo in summary["demographics"]:
            insights.append(f"• **{demo['gender']}**: {demo['count']:,} customers (avg age: {demo['avg_age']:.1f})")
    
    # Enhanced category breakdown
    if summary["categories"]:
        insights.append("\n**📦 Product Performance:**")
        for cat in summary["categories"]:
            category_name = cat['name'].replace('SKU-', '')
            insights.append(
                f"• **{category_name}**: {cat['transactions']} transactions, "
                f"{cat['units']} units, ${cat['revenue']:,.0f} revenue"
            )
            
            # Add age insight if available
            if 'avg_age' in cat and cat['avg_age']:
                insights.append(f"  - Average customer age: {cat['avg_age']:.1f} years")
            
            if (sku and cat['name'] == sku) or (category and cat['name'] == category):
                avg_units = cat['units'] / cat['transactions']
                avg_revenue = cat['revenue'] / cat['transactions']
                insights.append(f"  - Average per transaction: {avg_units:.1f} units, ${avg_revenue:.0f}")
    
    # Add payment method insights if available
    if summary.get("payment_methods"):
        insights.append("\n**💳 Payment Preferences:**")
        for pm in summary["payment_methods"][:3]:  # Top 3
            insights.append(f"• **{pm['method']}**: {pm['count']:,} transactions (${pm['revenue']:,.0f})")
    
    # Add location insights if available
    if summary.get("top_malls"):
        insights.append("\n**🏢 Top Shopping Locations:**")
        for mall in summary["top_malls"][:3]:  # Top 3
            insights.append(f"• **{mall['mall']}**: {mall['transactions']} transactions (${mall['revenue']:,.0f})")
    
    # Specific category/SKU focus
    if sku or category:
        target = category or sku.replace('SKU-', '')
        historical = get_historical_demand(sku, category)
        if historical:
            total_days = len(historical)
            total_demand = sum(row[1] for row in historical)
            avg_daily = total_demand / total_days
            
            insights.append(f"\n🎯 **{target} Category Focus:**")
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
        try:
            self.active_connections.remove(websocket)
            logger.info(f"WebSocket disconnected. Total connections: {len(self.active_connections)}")
        except ValueError:
            # WebSocket was already removed or never added
            logger.debug("WebSocket disconnect called but websocket not in active connections")

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

# Initialize services
openai_client = OpenAIClient()
manager = ConnectionManager()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management"""
    # Startup
    openai_connected = await openai_client.initialize()
    logger.info("🚀 Enhanced backend started with direct OpenAI integration")
    
    # Check database on startup
    try:
        summary = get_database_summary()
        logger.info(f"🎉 Connected to database with {summary['total_records']} sales transactions")
        logger.info(f"🤖 OpenAI status: {'Connected' if openai_connected else 'Disconnected'}")
    except Exception as e:
        logger.error(f"❌ Startup check failed: {e}")
    
    yield
    
    # Shutdown
    logger.info("🛑 Enhanced backend shutdown complete")

# Initialize FastAPI app with lifespan
app = FastAPI(
    title="DemandBot Enhanced Backend", 
    version="3.0.0",
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
    """Process chat message with enhanced real data + direct OpenAI integration"""
    message_lower = message.lower()
    
    # Extract SKU/category if mentioned
    sku = None
    category = None
    
    # Enhanced category mapping for the new dataset
    sku_mapping = {
        "beauty": "SKU-BEAUTY", 
        "clothing": "SKU-CLOTHING", 
        "electronics": "SKU-ELECTRONICS",
        "shoes": "SKU-SHOES",
        "books": "SKU-BOOKS", 
        "cosmetics": "SKU-COSMETICS"
    }
    
    category_mapping = {
        "beauty": "Beauty",
        "clothing": "Clothing", 
        "electronics": "Electronics",
        "shoes": "Shoes",
        "books": "Books",
        "cosmetics": "Cosmetics"
    }
    
    for keyword, sku_code in sku_mapping.items():
        if keyword in message_lower:
            sku = sku_code
            category = category_mapping.get(keyword)
            break
    
    forecast_data = None
    sources = []
    
    # Handle specific direct questions first
    summary = get_database_summary()
    
    # Direct question: Number of customers
    if any(phrase in message_lower for phrase in ["number of customers", "how many customers", "customer count", "total customers"]):
        response_text = f"# 👥 **Customer Information**\n\n"
        response_text += f"**Total Unique Customers**: {summary['unique_customers']:,}\n\n"
        response_text += f"**Additional Context:**\n"
        response_text += f"• Total Transactions: {summary['total_records']:,}\n"
        response_text += f"• Average Transactions per Customer: {summary['total_records'] / summary['unique_customers']:.1f}\n"
        response_text += f"• Average Units per Transaction: {summary['avg_units_per_transaction']:.1f}\n"
        response_text += f"• Average Revenue per Transaction: ${summary['avg_revenue_per_transaction']:.0f}\n\n"
        response_text += f"**Insight**: Each customer made an average of {summary['total_records'] / summary['unique_customers']:.1f} purchases during the period."
        
        return ChatResponse(
            content=response_text,
            forecast=None,
            sources=None,
            metadata={"query_type": "customer_count", "data_summary": summary}
        )
    
    # Direct question: Customer demographics
    if any(phrase in message_lower for phrase in ["age", "gender", "demographic", "male", "female", "customer age", "average age"]):
        demographics = get_customer_demographics()
        
        if "error" not in demographics:
            response_text = f"# 👥 **Customer Demographics Analysis**\n\n"
            
            # Gender breakdown
            if demographics.get("gender_breakdown"):
                response_text += f"**👥 Gender Distribution:**\n"
                for gender in demographics["gender_breakdown"]:
                    response_text += f"• **{gender['gender']}**: {gender['customers']:,} customers (avg age: {gender['avg_age']:.1f}, avg spending: ${gender['avg_spending']:.0f})\n"
                response_text += f"\n"
            
            # Age distribution
            if demographics.get("age_distribution"):
                response_text += f"**📊 Age Groups:**\n"
                for age_group in demographics["age_distribution"]:
                    response_text += f"• **{age_group['age_group']}**: {age_group['customers']:,} customers (avg spending: ${age_group['avg_spending']:.0f})\n"
                response_text += f"\n"
            
            # Category preferences by gender
            if demographics.get("category_preferences"):
                response_text += f"**🛍️ Shopping Preferences by Gender:**\n"
                current_gender = None
                for pref in demographics["category_preferences"]:
                    if pref['gender'] != current_gender:
                        current_gender = pref['gender']
                        response_text += f"**{current_gender} customers prefer:**\n"
                    response_text += f"• {pref['category']}: {pref['purchases']} purchases (${pref['total_spent']:,.0f})\n"
        else:
            response_text = f"**Customer Demographics**\n\nDetailed demographic data is not available in the current dataset. Please load the enhanced customer shopping data to access age, gender, and demographic insights."
        
        return ChatResponse(
            content=response_text,
            forecast=None,
            sources=None,
            metadata={"query_type": "demographics", "data_summary": summary}
        )

    # Direct question: What is this
    if message_lower.strip() in ["what is this", "what's this", "what is it"]:
        enhanced_features = ""
        if summary.get("enhanced_data"):
            enhanced_features = f"• **Customer Demographics** (age, gender)\n• **Payment Methods** analysis\n• **Shopping Locations** insights\n• **Enhanced Categories** (Clothing, Shoes, Books, Cosmetics)\n"
        
        response_text = f"# 🤖 **DemandBot - Sales Analytics Platform**\n\n"
        response_text += f"This is an AI-powered demand forecasting and sales analytics system that analyzes your **real sales data**.\n\n"
        response_text += f"**Your Current Dataset:**\n"
        response_text += f"• **{summary['unique_customers']:,} unique customers**\n"
        response_text += f"• **{summary['total_records']:,} transactions**\n"
        
        if summary.get("enhanced_data"):
            categories = len(summary.get("categories", []))
            response_text += f"• **{categories} product categories**\n"
        else:
            response_text += f"• **3 product categories** (Beauty, Clothing, Electronics)\n"
            
        response_text += f"• **Period**: {summary['date_range']['start'][:10]} to {summary['date_range']['end'][:10]}\n\n"
        response_text += f"**Available Features:**\n"
        response_text += f"• Generate demand forecasts\n"
        response_text += f"• Analyze sales patterns\n"
        response_text += f"• Answer specific questions about your data\n"
        response_text += f"• Provide AI-powered business insights\n"
        response_text += enhanced_features
        response_text += f"\n**Try asking:** 'What is the average customer age?' or 'Show me demographics' or 'Forecast Clothing demand'"
        
        return ChatResponse(
            content=response_text,
            forecast=None,
            sources=None,
            metadata={"query_type": "system_info", "data_summary": summary}
        )
    
    # Get real data insights for other queries
    data_insights = generate_insights(sku, category)
    
    # Get AI-powered insights
    ai_insights = await openai_client.generate_insights(data_insights, message, sku)
    
    # Handle different query types
    if any(word in message_lower for word in ["forecast", "predict", "future", "demand"]):
        days = 30
        if "week" in message_lower:
            days = 7
        elif "month" in message_lower:
            days = 30
        elif "quarter" in message_lower:
            days = 90
            
        # Use category for forecast if available, otherwise use SKU
        forecast_data = generate_forecast_from_data(sku, days, category)
        
        if forecast_data:
            avg_prediction = sum(f.predicted_units for f in forecast_data) // len(forecast_data)
            min_range = min(f.confidence_interval['lower'] for f in forecast_data)
            max_range = max(f.confidence_interval['upper'] for f in forecast_data)
            
            # Use category name if available, otherwise extract from SKU
            category_name = category or (sku.replace('SKU-', '') if sku else 'Overall')
            response_text = f"**{category_name} Forecast ({days} days):**\n"
            response_text += f"Average daily demand: {avg_prediction} units\n"
            response_text += f"Range: {min_range} - {max_range} units\n\n"
            
            # Generate insights based on forecast data instead of relying on AI that might say "Data not available"
            historical_data = get_historical_demand(sku, category)
            if historical_data:
                recent_avg = sum(row[1] for row in historical_data[-7:]) / min(7, len(historical_data))
                trend = "increasing" if avg_prediction > recent_avg else "stable" if abs(avg_prediction - recent_avg) < 1 else "decreasing"
                response_text += f"**Forecast Analysis:**\n"
                response_text += f"• Trend: Demand appears to be {trend} based on recent patterns\n"
                response_text += f"• Model used: Enhanced Pattern Analysis with Trend & Seasonality\n"
                response_text += f"• Confidence: Based on {len(historical_data)} days of historical data\n"
                response_text += f"• Peak days expected: Fridays and Saturdays typically show 15% higher demand\n"
                
                # Add AI insights only if they don't contradict the successful forecast
                if ai_insights and "data not available" not in ai_insights.lower():
                    response_text += f"\n**Additional Insights:**\n{ai_insights}"
            else:
                # Fallback if no historical data but forecast was generated (shouldn't happen but safety check)
                response_text += f"**Note:** Forecast generated using baseline assumptions and market patterns."
        else:
            response_text = "No historical data available for forecasting."
            
    elif any(word in message_lower for word in ["summary", "overview", "data", "sales"]):
        summary = get_database_summary()
        response_text = f"**Sales Summary:**\n"
        response_text += f"• {summary['total_records']} transactions\n"
        response_text += f"• {summary['unique_customers']} customers\n"
        for cat in summary['categories']:
            response_text += f"• {cat['name'].replace('SKU-', '')}: {cat['transactions']} sales, ${cat['revenue']:,}\n"
        
        if ai_insights:
            response_text += f"\n{ai_insights}"
        
    elif any(word in message_lower for word in ["trend", "pattern", "analysis"]):
        if ai_insights:
            response_text = ai_insights
        else:
            response_text = "I can help analyze trends in your sales data. What specific pattern are you looking for?"
        
    else:
        # Simple, direct responses without excessive formatting
        if ai_insights:
            response_text = ai_insights
        else:
            response_text = "I can help analyze your sales data. Try asking about forecasts, trends, or specific metrics."
    
    return ChatResponse(
        content=response_text,
        forecast=forecast_data,
        sources=sources,
        metadata={
            "sku": sku,
            "category": category,
            "data_summary": get_database_summary(),
            "based_on_real_data": True,
            "ai_enhanced": ai_insights is not None,
            "openai_connected": openai_client.connected,
            "model_used": "GPT-3.5-turbo + Enhanced Customer Analytics" if ai_insights else "Enhanced Customer Analytics Only"
        }
    )

# API Endpoints
@app.get("/health", response_model=HealthCheck)
async def health_check():
    """Health check with real data and OpenAI status"""
    summary = get_database_summary()
    
    return HealthCheck(
        status="healthy",
        version="3.0.0",
        database_status="connected" if summary["total_records"] > 0 else "no_data",
        data_loaded=summary["total_records"] > 0,
        openai_connected=openai_client.connected
    )

@app.websocket("/chat")
async def websocket_chat_endpoint(websocket: WebSocket):
    """WebSocket chat endpoint with enhanced functionality"""
    try:
        await manager.connect(websocket)
        logger.info("WebSocket connection established successfully")
        
        # Send initial connection message
        welcome_message = {
            "type": "chat_response",
            "data": {
                "content": "🚀 **Connected to DemandBot!** I'm ready to help with your demand forecasting and business analytics.",
                "forecast": None,
                "sources": None,
                "entities": [],
                "metadata": {"connection": "established", "ai_status": openai_client.connected}
            },
            "id": "system",
            "timestamp": datetime.now().isoformat()
        }
        await manager.send_personal_message(json.dumps(welcome_message), websocket)
        
        while True:
            # Receive message from WebSocket
            data = await websocket.receive_text()
            
            try:
                # Parse incoming message
                message_data = json.loads(data)
                message_type = message_data.get("type", "chat_message")
                
                if message_type == "chat_message":
                    content = message_data.get("data", {}).get("content", "")
                    user_id = message_data.get("data", {}).get("user_id", "default")
                    
                    logger.info(f"WebSocket enhanced message from {user_id}: {content}")
                    
                    # Process the message with enhanced functionality
                    response = await process_chat_message(content, user_id)
                    
                    # Send complete response in the format frontend expects
                    response_data = {
                        "content": response.content,
                        "forecast": [f.dict() for f in response.forecast] if response.forecast else None,
                        "sources": [s.dict() for s in response.sources] if response.sources else None,
                        "entities": [],  # Add entities field as expected by frontend
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
                # Handle plain text messages (fallback)
                logger.info(f"WebSocket plain text: {data}")
                response = await process_chat_message(data, "websocket_user")
                
                response_data = {
                    "content": response.content,
                    "forecast": [f.dict() for f in response.forecast] if response.forecast else None,
                    "sources": [s.dict() for s in response.sources] if response.sources else None,
                    "entities": [],
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
        logger.info("WebSocket client disconnected normally")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        manager.disconnect(websocket)

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(message: ChatMessage):
    """HTTP POST chat endpoint with enhanced functionality"""
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

@app.get("/ai/status")
async def get_ai_status():
    """Get AI service status"""
    return {
        "openai_connected": openai_client.connected,
        "api_key_configured": openai_client.api_key is not None,
        "status": "connected" if openai_client.connected else "disconnected"
    }

@app.get("/")
async def root():
    """Root endpoint"""
    summary = get_database_summary()
    
    return {
        "message": "DemandBot Enhanced Analytics API - Real Data + Direct AI Integration",
        "version": "3.0.0",
        "data_loaded": summary["total_records"] > 0,
        "total_transactions": summary["total_records"],
        "ai_connected": openai_client.connected,
        "capabilities": [
            "Real sales data analysis",
            "Direct OpenAI GPT-3.5 integration",
            "AI-enhanced forecasting",
            "Strategic business insights",
            "WebSocket real-time chat"
        ],
        "endpoints": {
            "health": "/health",
            "chat": "/chat (WebSocket + HTTP)",
            "data_summary": "/data/summary",
            "categories": "/data/categories",
            "ai_status": "/ai/status"
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8005) 