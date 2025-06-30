import asyncio
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta

# Use SQLite instead of MongoDB for simplicity
import sqlite3
from ..config import settings
from ..models import TrainingData

logger = logging.getLogger(__name__)


class DataLoader:
    """Service for loading training data using SQLite database"""
    
    def __init__(self):
        self.db_path = "../data/demandbot.db"  # Relative to forecast_service directory
        self._connected = False
    
    async def connect(self):
        """Connect to SQLite database"""
        try:
            # Test connection
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                # Try enhanced table first, fall back to basic sales table
                try:
                    cursor.execute("SELECT COUNT(*) FROM sales_enhanced")
                    logger.info("DataLoader connected to SQLite with enhanced data")
                except:
                    cursor.execute("SELECT COUNT(*) FROM sales")
                    logger.info("DataLoader connected to SQLite with basic data")
                self._connected = True
        except Exception as e:
            logger.error(f"Failed to connect DataLoader to SQLite: {e}")
            self._connected = False
            raise
    
    async def disconnect(self):
        """Disconnect from SQLite"""
        self._connected = False
        logger.info("DataLoader disconnected from SQLite")
    
    async def is_connected(self) -> bool:
        """Check if SQLite is connected"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                return True
        except Exception:
            self._connected = False
            return False
    
    async def get_training_data(self, sku: str, days_back: int = 365) -> List[TrainingData]:
        """Get training data for a specific SKU"""
        if not self._connected:
            raise RuntimeError("Database not connected")
        
        # Calculate date range
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days_back)
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Check which table exists and use appropriate query
                try:
                    cursor.execute("SELECT COUNT(*) FROM sales_enhanced WHERE sku = ? LIMIT 1", (sku,))
                    # Use enhanced table
                    cursor.execute('''
                        SELECT sku, invoice_date, quantity, price
                        FROM sales_enhanced
                        WHERE sku = ? AND invoice_date BETWEEN ? AND ?
                        ORDER BY invoice_date
                    ''', (sku, start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')))
                except:
                    # Fall back to basic sales table
                    cursor.execute('''
                        SELECT sku, DATE(timestamp), units_sold, revenue/units_sold as price
                        FROM sales
                        WHERE sku = ? AND timestamp BETWEEN ? AND ?
                        ORDER BY timestamp
                    ''', (sku, start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')))
                
                rows = cursor.fetchall()
                
                # Convert to TrainingData objects
                training_data = []
                for row in rows:
                    try:
                        training_data.append(TrainingData(
                            sku=row[0],
                            timestamp=datetime.strptime(row[1], '%Y-%m-%d'),
                            units_sold=int(row[2]),
                            price=float(row[3]) if row[3] else 0.0
                        ))
                    except Exception as e:
                        logger.warning(f"Skipping invalid row: {e}")
                        continue
                
                logger.info(f"Loaded {len(training_data)} training samples for SKU {sku}")
                return training_data
                
        except Exception as e:
            logger.error(f"Error loading training data: {e}")
            return []
    
    async def get_available_skus(self) -> List[str]:
        """Get list of all available SKUs with sufficient data"""
        if not self._connected:
            raise RuntimeError("Database not connected")
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Try enhanced table first, then basic table
                try:
                    cursor.execute('''
                        SELECT sku, COUNT(*) as count
                        FROM sales_enhanced
                        GROUP BY sku
                        HAVING count >= ?
                    ''', (settings.min_training_samples,))
                except:
                    cursor.execute('''
                        SELECT sku, COUNT(*) as count
                        FROM sales
                        GROUP BY sku
                        HAVING count >= ?
                    ''', (settings.min_training_samples,))
                
                rows = cursor.fetchall()
                valid_skus = [row[0] for row in rows]
                
                logger.info(f"Found {len(valid_skus)} SKUs with sufficient training data")
                return valid_skus
                
        except Exception as e:
            logger.error(f"Error getting available SKUs: {e}")
            return []
    
    async def sku_exists(self, sku: str) -> bool:
        """Check if SKU exists in the database"""
        if not self._connected:
            raise RuntimeError("Database not connected")
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Try enhanced table first, then basic table
                try:
                    cursor.execute("SELECT COUNT(*) FROM sales_enhanced WHERE sku = ?", (sku,))
                except:
                    cursor.execute("SELECT COUNT(*) FROM sales WHERE sku = ?", (sku,))
                
                count = cursor.fetchone()[0]
                return count > 0
        except Exception as e:
            logger.error(f"Error checking SKU existence: {e}")
            return False
    
    async def get_data_summary(self) -> Dict[str, Any]:
        """Get summary statistics of the data"""
        if not self._connected:
            raise RuntimeError("Database not connected")
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Try enhanced table first, then basic table
                try:
                    cursor.execute('''
                        SELECT 
                            COUNT(DISTINCT sku) as total_skus,
                            COUNT(*) as total_records,
                            AVG(quantity) as avg_qty,
                            AVG(price) as avg_price,
                            MIN(invoice_date) as min_date,
                            MAX(invoice_date) as max_date
                        FROM sales_enhanced
                    ''')
                except:
                    cursor.execute('''
                        SELECT 
                            COUNT(DISTINCT sku) as total_skus,
                            COUNT(*) as total_records,
                            AVG(units_sold) as avg_qty,
                            AVG(revenue/units_sold) as avg_price,
                            MIN(timestamp) as min_date,
                            MAX(timestamp) as max_date
                        FROM sales
                    ''')
                
                row = cursor.fetchone()
                if row:
                    return {
                        "total_skus": row[0],
                        "total_records": row[1],
                        "avg_records_per_sku": row[1] / row[0] if row[0] > 0 else 0,
                        "avg_qty": row[2],
                        "avg_price": row[3],
                        "min_date": row[4],
                        "max_date": row[5]
                    }
                else:
                    return {
                        "total_skus": 0,
                        "total_records": 0,
                        "avg_records_per_sku": 0
                    }
                    
        except Exception as e:
            logger.error(f"Error getting data summary: {e}")
            return {
                "total_skus": 0,
                "total_records": 0,
                "avg_records_per_sku": 0
            }