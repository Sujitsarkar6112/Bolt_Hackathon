#!/usr/bin/env python3
"""
MongoDB Setup Script for DemandBot
This script sets up an in-memory MongoDB instance and loads data from SQLite
"""

import asyncio
import sqlite3
import json
from datetime import datetime
from pymongo_inmemory import MongoClient as InMemoryMongoClient
import pymongo
from motor.motor_asyncio import AsyncIOMotorClient
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MongoDBSetup:
    def __init__(self):
        self.client = None
        self.db = None
        self.port = 27017
        
    async def start_mongodb(self):
        """Start in-memory MongoDB instance"""
        try:
            # Start in-memory MongoDB
            self.client = InMemoryMongoClient()
            self.db = self.client.demandbot
            
            logger.info("✅ In-memory MongoDB started successfully")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to start MongoDB: {e}")
            return False
            
    async def load_sqlite_data(self):
        """Load data from SQLite into MongoDB"""
        try:
            # Connect to SQLite
            sqlite_conn = sqlite3.connect("data/demandbot.db")
            cursor = sqlite_conn.cursor()
            
            # Get sales data
            cursor.execute("SELECT * FROM sales")
            sales_data = cursor.fetchall()
            
            # Get column names
            cursor.execute("PRAGMA table_info(sales)")
            columns = [row[1] for row in cursor.fetchall()]
            
            # Convert to dictionaries
            sales_documents = []
            for row in sales_data:
                doc = dict(zip(columns, row))
                # Convert timestamp if needed
                if 'timestamp' in doc and isinstance(doc['timestamp'], str):
                    try:
                        doc['timestamp'] = datetime.fromisoformat(doc['timestamp'])
                    except:
                        pass
                sales_documents.append(doc)
            
            # Insert into MongoDB
            if sales_documents:
                await self.db.raw_sales.insert_many(sales_documents)
                logger.info(f"✅ Loaded {len(sales_documents)} sales records into MongoDB")
            
            # Load other tables if they exist
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = cursor.fetchall()
            
            for table in tables:
                table_name = table[0]
                if table_name != 'sales':
                    cursor.execute(f"SELECT * FROM {table_name}")
                    table_data = cursor.fetchall()
                    
                    cursor.execute(f"PRAGMA table_info({table_name})")
                    table_columns = [row[1] for row in cursor.fetchall()]
                    
                    documents = [dict(zip(table_columns, row)) for row in table_data]
                    if documents:
                        await self.db[table_name].insert_many(documents)
                        logger.info(f"✅ Loaded {len(documents)} records from {table_name} table")
            
            sqlite_conn.close()
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to load SQLite data: {e}")
            return False
    
    async def setup_indexes(self):
        """Create indexes for better performance"""
        try:
            # Create indexes for sales data
            await self.db.raw_sales.create_index("sku")
            await self.db.raw_sales.create_index("timestamp")
            await self.db.raw_sales.create_index([("sku", 1), ("timestamp", 1)])
            
            logger.info("✅ Created database indexes")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to create indexes: {e}")
            return False
    
    async def verify_setup(self):
        """Verify MongoDB setup"""
        try:
            # Check sales collection
            sales_count = await self.db.raw_sales.count_documents({})
            logger.info(f"📊 Sales documents: {sales_count}")
            
            # Check distinct SKUs
            skus = await self.db.raw_sales.distinct("sku")
            logger.info(f"📦 Unique SKUs: {len(skus)}")
            
            # Check date range
            pipeline = [
                {"$group": {
                    "_id": None,
                    "min_date": {"$min": "$timestamp"},
                    "max_date": {"$max": "$timestamp"}
                }}
            ]
            
            async for result in self.db.raw_sales.aggregate(pipeline):
                logger.info(f"📅 Date range: {result['min_date']} to {result['max_date']}")
            
            return True
        except Exception as e:
            logger.error(f"❌ Verification failed: {e}")
            return False

async def main():
    """Main setup function"""
    logger.info("🚀 Starting MongoDB setup for DemandBot")
    
    setup = MongoDBSetup()
    
    # Start MongoDB
    if not await setup.start_mongodb():
        return False
    
    # Load data
    if not await setup.load_sqlite_data():
        return False
    
    # Setup indexes
    if not await setup.setup_indexes():
        return False
    
    # Verify setup
    if not await setup.verify_setup():
        return False
    
    logger.info("🎉 MongoDB setup completed successfully!")
    logger.info("📡 MongoDB running in-memory at: mongodb://localhost:27017")
    logger.info("💾 Database: demandbot")
    logger.info("📋 Collections: raw_sales, and other tables from SQLite")
    
    # Keep running
    logger.info("⏳ Keeping MongoDB running... Press Ctrl+C to stop")
    try:
        while True:
            await asyncio.sleep(10)
    except KeyboardInterrupt:
        logger.info("🛑 MongoDB setup stopped")
    
    return True

if __name__ == "__main__":
    asyncio.run(main()) 