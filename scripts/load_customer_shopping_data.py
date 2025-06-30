#!/usr/bin/env python3
"""
Customer Shopping Data Loader
Loads the rich customer_shopping_data.csv into the existing SQLite database
"""

import sqlite3
import pandas as pd
import logging
from datetime import datetime
from pathlib import Path
import sys

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def create_enhanced_tables(cursor):
    """Create enhanced database schema to support the rich customer data"""
    
    # Enhanced sales table with demographics and location
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sales_enhanced (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_no TEXT NOT NULL,
            customer_id TEXT NOT NULL,
            gender TEXT,
            age INTEGER,
            category TEXT NOT NULL,
            sku TEXT,  -- Mapped from category
            quantity INTEGER NOT NULL,
            price REAL NOT NULL,
            payment_method TEXT,
            invoice_date TEXT NOT NULL,
            shopping_mall TEXT,
            timestamp TEXT NOT NULL,
            units_sold INTEGER NOT NULL,
            revenue REAL NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Customer demographics table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS customers (
            customer_id TEXT PRIMARY KEY,
            gender TEXT,
            age INTEGER,
            first_transaction_date TEXT,
            last_transaction_date TEXT,
            total_transactions INTEGER DEFAULT 0,
            total_spent REAL DEFAULT 0.0,
            avg_transaction_value REAL DEFAULT 0.0,
            preferred_payment_method TEXT,
            preferred_mall TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Shopping mall performance table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS mall_performance (
            shopping_mall TEXT PRIMARY KEY,
            total_transactions INTEGER DEFAULT 0,
            total_revenue REAL DEFAULT 0.0,
            unique_customers INTEGER DEFAULT 0,
            avg_transaction_value REAL DEFAULT 0.0,
            most_popular_category TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Category mapping table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS category_mapping (
            original_category TEXT PRIMARY KEY,
            mapped_sku TEXT NOT NULL,
            category_group TEXT NOT NULL
        )
    ''')
    
    logger.info("Enhanced database schema created successfully")

def setup_category_mapping(cursor):
    """Setup mapping from new categories to existing SKU format"""
    
    category_mappings = [
        ('Clothing', 'SKU-CLOTHING', 'Apparel'),
        ('Shoes', 'SKU-SHOES', 'Footwear'),
        ('Books', 'SKU-BOOKS', 'Media'),
        ('Cosmetics', 'SKU-COSMETICS', 'Beauty'),
        # Add fallbacks for existing categories
        ('Beauty', 'SKU-BEAUTY', 'Beauty'),
        ('Electronics', 'SKU-ELECTRONICS', 'Electronics')
    ]
    
    cursor.execute('DELETE FROM category_mapping')  # Clear existing mappings
    
    for original, sku, group in category_mappings:
        cursor.execute('''
            INSERT INTO category_mapping (original_category, mapped_sku, category_group)
            VALUES (?, ?, ?)
        ''', (original, sku, group))
    
    logger.info(f"Category mappings created for {len(category_mappings)} categories")

def parse_date(date_str):
    """Parse date string to ISO format"""
    try:
        # Handle multiple date formats
        for fmt in ['%d/%m/%Y', '%m/%d/%Y', '%Y-%m-%d', '%d/%m/%y']:
            try:
                dt = datetime.strptime(date_str, fmt)
                return dt.strftime('%Y-%m-%d')
            except ValueError:
                continue
        
        # If no format matches, return as-is
        logger.warning(f"Could not parse date: {date_str}")
        return date_str
        
    except Exception as e:
        logger.warning(f"Date parsing error for '{date_str}': {e}")
        return date_str

def load_customer_shopping_data(csv_path, db_path):
    """Load customer shopping data from CSV into enhanced database"""
    
    if not Path(csv_path).exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")
    
    # Read CSV data
    logger.info(f"Reading CSV data from {csv_path}")
    df = pd.read_csv(csv_path)
    logger.info(f"Loaded {len(df)} rows from CSV")
    
    # Connect to database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Create enhanced schema
        create_enhanced_tables(cursor)
        setup_category_mapping(cursor)
        
        # Get category mappings
        cursor.execute('SELECT original_category, mapped_sku FROM category_mapping')
        category_map = dict(cursor.fetchall())
        
        # Process and insert data
        logger.info("Processing and inserting customer shopping data...")
        
        processed_count = 0
        error_count = 0
        
        for index, row in df.iterrows():
            try:
                # Parse and validate data
                invoice_no = str(row['invoice_no'])
                customer_id = str(row['customer_id'])
                gender = str(row['gender']).strip() if pd.notna(row['gender']) else None
                age = int(row['age']) if pd.notna(row['age']) else None
                category = str(row['category']).strip()
                quantity = int(row['quantity']) if pd.notna(row['quantity']) else 1
                price = float(row['price']) if pd.notna(row['price']) else 0.0
                payment_method = str(row['payment_method']).strip() if pd.notna(row['payment_method']) else None
                invoice_date = parse_date(str(row['invoice_date']))
                shopping_mall = str(row['shopping_mall']).strip() if pd.notna(row['shopping_mall']) else None
                
                # Map category to SKU
                sku = category_map.get(category, f'SKU-{category.upper()}')
                
                # Calculate derived fields
                revenue = price
                units_sold = quantity
                timestamp = f"{invoice_date} 12:00:00"  # Default time
                
                # Insert into sales_enhanced
                cursor.execute('''
                    INSERT INTO sales_enhanced (
                        invoice_no, customer_id, gender, age, category, sku,
                        quantity, price, payment_method, invoice_date, shopping_mall,
                        timestamp, units_sold, revenue
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    invoice_no, customer_id, gender, age, category, sku,
                    quantity, price, payment_method, invoice_date, shopping_mall,
                    timestamp, units_sold, revenue
                ))
                
                # Also insert into original sales table for backward compatibility
                cursor.execute('''
                    INSERT OR REPLACE INTO sales (
                        customer_id, timestamp, sku, units_sold, revenue
                    ) VALUES (?, ?, ?, ?, ?)
                ''', (customer_id, timestamp, sku, units_sold, revenue))
                
                processed_count += 1
                
                if processed_count % 10000 == 0:
                    logger.info(f"Processed {processed_count} records...")
                    conn.commit()  # Commit periodically
                
            except Exception as e:
                error_count += 1
                logger.warning(f"Error processing row {index}: {e}")
                if error_count > 100:  # Stop if too many errors
                    logger.error("Too many errors, stopping...")
                    break
        
        # Final commit
        conn.commit()
        
        # Update customer demographics
        logger.info("Updating customer demographics...")
        cursor.execute('''
            INSERT OR REPLACE INTO customers (
                customer_id, gender, age, first_transaction_date, last_transaction_date,
                total_transactions, total_spent, avg_transaction_value
            )
            SELECT 
                customer_id,
                gender,
                age,
                MIN(invoice_date) as first_transaction_date,
                MAX(invoice_date) as last_transaction_date,
                COUNT(*) as total_transactions,
                SUM(revenue) as total_spent,
                AVG(revenue) as avg_transaction_value
            FROM sales_enhanced
            GROUP BY customer_id, gender, age
        ''')
        
        # Update mall performance
        logger.info("Updating mall performance...")
        cursor.execute('''
            INSERT OR REPLACE INTO mall_performance (
                shopping_mall, total_transactions, total_revenue, 
                unique_customers, avg_transaction_value
            )
            SELECT 
                shopping_mall,
                COUNT(*) as total_transactions,
                SUM(revenue) as total_revenue,
                COUNT(DISTINCT customer_id) as unique_customers,
                AVG(revenue) as avg_transaction_value
            FROM sales_enhanced
            WHERE shopping_mall IS NOT NULL
            GROUP BY shopping_mall
        ''')
        
        conn.commit()
        
        # Get final statistics
        cursor.execute('SELECT COUNT(*) FROM sales_enhanced')
        total_enhanced = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM sales')
        total_sales = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(DISTINCT customer_id) FROM customers')
        total_customers = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM mall_performance')
        total_malls = cursor.fetchone()[0]
        
        logger.info("🎉 Data loading completed successfully!")
        logger.info(f"📊 Statistics:")
        logger.info(f"   • Enhanced sales records: {total_enhanced:,}")
        logger.info(f"   • Total sales records: {total_sales:,}")
        logger.info(f"   • Unique customers: {total_customers:,}")
        logger.info(f"   • Shopping malls: {total_malls}")
        logger.info(f"   • Processed: {processed_count:,} records")
        logger.info(f"   • Errors: {error_count}")
        
        return True
        
    except Exception as e:
        logger.error(f"Error loading data: {e}")
        conn.rollback()
        return False
        
    finally:
        conn.close()

def main():
    """Main function"""
    csv_path = "data/customer_shopping_data.csv"
    db_path = "data/demandbot.db"
    
    logger.info("🚀 Starting customer shopping data load...")
    
    success = load_customer_shopping_data(csv_path, db_path)
    
    if success:
        logger.info("✅ Customer shopping data loaded successfully!")
        logger.info("🔄 You can now restart your backend to use the enhanced dataset.")
    else:
        logger.error("❌ Failed to load customer shopping data")
        sys.exit(1)

if __name__ == "__main__":
    main() 