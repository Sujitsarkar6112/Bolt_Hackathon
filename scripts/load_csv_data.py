#!/usr/bin/env python3
"""
CSV Data Loader for DemandBot
Transforms retail sales data into the format expected by the forecasting system
"""

import pandas as pd
import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
import logging
from typing import Dict, List, Any

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CSVDataLoader:
    def __init__(self, csv_path: str, db_path: str = "data/demandbot.db"):
        self.csv_path = csv_path
        self.db_path = db_path
        self.ensure_data_dir()
        
    def ensure_data_dir(self):
        """Ensure data directory exists"""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        
    def load_csv(self) -> pd.DataFrame:
        """Load and validate CSV data"""
        logger.info(f"Loading CSV data from {self.csv_path}")
        df = pd.read_csv(self.csv_path)
        
        # Validate required columns
        required_cols = ['Transaction ID', 'Date', 'Customer ID', 'Product Category', 'Quantity', 'Price per Unit']
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            raise ValueError(f"Missing required columns: {missing_cols}")
            
        logger.info(f"Loaded {len(df)} transactions from CSV")
        return df
        
    def transform_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Transform CSV data to DemandBot format"""
        logger.info("Transforming data to DemandBot format")
        
        # Create SKU mapping from Product Category
        category_sku_map = {
            'Beauty': 'SKU-BEAUTY',
            'Clothing': 'SKU-CLOTHING', 
            'Electronics': 'SKU-ELECTRONICS'
        }
        
        # Transform the data
        transformed = df.copy()
        transformed['sku'] = df['Product Category'].map(category_sku_map)
        transformed['timestamp'] = pd.to_datetime(df['Date'])
        transformed['units_sold'] = df['Quantity']
        transformed['price'] = df['Price per Unit']
        transformed['customer_id'] = df['Customer ID']
        transformed['transaction_id'] = df['Transaction ID']
        
        # Add some derived fields for better forecasting
        transformed['revenue'] = transformed['units_sold'] * transformed['price']
        transformed['year'] = transformed['timestamp'].dt.year
        transformed['month'] = transformed['timestamp'].dt.month
        transformed['day_of_week'] = transformed['timestamp'].dt.dayofweek
        transformed['is_weekend'] = transformed['day_of_week'].isin([5, 6])
        
        # Select final columns
        final_cols = [
            'transaction_id', 'sku', 'timestamp', 'units_sold', 'price', 
            'revenue', 'customer_id', 'year', 'month', 'day_of_week', 'is_weekend'
        ]
        
        result = transformed[final_cols].copy()
        logger.info(f"Transformed data shape: {result.shape}")
        return result
        
    def create_sqlite_db(self, df: pd.DataFrame):
        """Create SQLite database with sales data"""
        logger.info(f"Creating SQLite database at {self.db_path}")
        
        conn = sqlite3.connect(self.db_path)
        
        # Create sales table
        df.to_sql('sales', conn, if_exists='replace', index=False)
        
        # Create indexes for better performance
        conn.execute('CREATE INDEX IF NOT EXISTS idx_sku ON sales(sku)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_timestamp ON sales(timestamp)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_sku_timestamp ON sales(sku, timestamp)')
        
        # Create aggregated views for forecasting
        conn.execute('''
            CREATE VIEW IF NOT EXISTS daily_sales AS
            SELECT 
                sku,
                DATE(timestamp) as date,
                SUM(units_sold) as total_units,
                SUM(revenue) as total_revenue,
                COUNT(*) as transaction_count,
                AVG(price) as avg_price
            FROM sales 
            GROUP BY sku, DATE(timestamp)
            ORDER BY sku, date
        ''')
        
        conn.execute('''
            CREATE VIEW IF NOT EXISTS weekly_sales AS
            SELECT 
                sku,
                strftime('%Y-%W', timestamp) as week,
                SUM(units_sold) as total_units,
                SUM(revenue) as total_revenue,
                COUNT(*) as transaction_count,
                AVG(price) as avg_price
            FROM sales 
            GROUP BY sku, strftime('%Y-%W', timestamp)
            ORDER BY sku, week
        ''')
        
        conn.commit()
        conn.close()
        
        logger.info("SQLite database created successfully")
        
    def generate_summary_stats(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Generate summary statistics"""
        stats = {
            'total_transactions': len(df),
            'date_range': {
                'start': df['timestamp'].min().isoformat(),
                'end': df['timestamp'].max().isoformat()
            },
            'skus': df['sku'].unique().tolist(),
            'sku_stats': {}
        }
        
        for sku in df['sku'].unique():
            sku_data = df[df['sku'] == sku]
            stats['sku_stats'][sku] = {
                'transaction_count': len(sku_data),
                'total_units': int(sku_data['units_sold'].sum()),
                'total_revenue': float(sku_data['revenue'].sum()),
                'avg_price': float(sku_data['price'].mean()),
                'price_range': {
                    'min': float(sku_data['price'].min()),
                    'max': float(sku_data['price'].max())
                }
            }
            
        return stats
        
    def run(self):
        """Run the complete data loading process"""
        try:
            # Load and transform data
            df = self.load_csv()
            transformed_df = self.transform_data(df)
            
            # Create database
            self.create_sqlite_db(transformed_df)
            
            # Generate statistics
            stats = self.generate_summary_stats(transformed_df)
            
            # Save stats to JSON
            stats_path = Path(self.db_path).parent / "data_stats.json"
            with open(stats_path, 'w') as f:
                json.dump(stats, f, indent=2)
                
            logger.info("Data loading completed successfully!")
            logger.info(f"Database: {self.db_path}")
            logger.info(f"Stats: {stats_path}")
            
            # Print summary
            print("\n" + "="*50)
            print("📊 DATA LOADING SUMMARY")
            print("="*50)
            print(f"✅ Total Transactions: {stats['total_transactions']:,}")
            print(f"📅 Date Range: {stats['date_range']['start']} to {stats['date_range']['end']}")
            print(f"🏷️  SKUs Available: {', '.join(stats['skus'])}")
            print("\n📈 SKU Breakdown:")
            for sku, sku_stats in stats['sku_stats'].items():
                print(f"  {sku}: {sku_stats['transaction_count']:,} transactions, "
                      f"{sku_stats['total_units']:,} units, "
                      f"${sku_stats['total_revenue']:,.2f} revenue")
            print("="*50)
            
            return True
            
        except Exception as e:
            logger.error(f"Data loading failed: {e}")
            return False

def main():
    """Main entry point"""
    csv_path = "retail_sales_dataset.csv"
    
    if not Path(csv_path).exists():
        print(f"❌ CSV file not found: {csv_path}")
        print("Please ensure the retail_sales_dataset.csv file is in the project root.")
        return False
        
    loader = CSVDataLoader(csv_path)
    success = loader.run()
    
    if success:
        print("\n🎉 Ready to start DemandBot with your data!")
        print("💡 The SQLite database is ready for the forecasting service.")
    else:
        print("\n❌ Data loading failed. Check the logs above.")
        
    return success

if __name__ == "__main__":
    main() 