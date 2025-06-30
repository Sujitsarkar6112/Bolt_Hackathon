#!/usr/bin/env python3
"""
Test database access from different service directories
"""

import sqlite3
import os
from pathlib import Path

def test_database_access():
    """Test if database can be accessed from different locations"""
    
    print("🔍 Testing database access from different locations...")
    print(f"Current working directory: {os.getcwd()}")
    
    # Test paths to try
    test_paths = [
        "data/demandbot.db",
        "../data/demandbot.db", 
        "./data/demandbot.db",
        Path("data") / "demandbot.db",
        Path("..") / "data" / "demandbot.db"
    ]
    
    for path in test_paths:
        print(f"\n📁 Trying path: {path}")
        
        if Path(path).exists():
            print(f"   ✅ File exists at {path}")
            
            try:
                with sqlite3.connect(str(path)) as conn:
                    cursor = conn.cursor()
                    
                    # Check what tables exist
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                    tables = [row[0] for row in cursor.fetchall()]
                    print(f"   📊 Tables found: {tables}")
                    
                    # Check sales table
                    if 'sales' in tables:
                        cursor.execute("SELECT COUNT(*) FROM sales")
                        count = cursor.fetchone()[0]
                        print(f"   📈 Sales table: {count} records")
                        
                        cursor.execute("SELECT DISTINCT sku FROM sales LIMIT 5")
                        skus = [row[0] for row in cursor.fetchall()]
                        print(f"   🏷️  Sample SKUs: {skus}")
                    
                    # Check enhanced table
                    if 'sales_enhanced' in tables:
                        cursor.execute("SELECT COUNT(*) FROM sales_enhanced")
                        count = cursor.fetchone()[0]
                        print(f"   🔥 Enhanced table: {count} records")
                        
            except Exception as e:
                print(f"   ❌ Database error: {e}")
        else:
            print(f"   ❌ File not found at {path}")

def test_from_backend():
    """Test access from backend directory"""
    print("\n" + "="*50)
    print("🏢 TESTING FROM BACKEND DIRECTORY")
    print("="*50)
    
    original_dir = os.getcwd()
    try:
        backend_dir = Path("backend")
        if backend_dir.exists():
            os.chdir(backend_dir)
            test_database_access()
        else:
            print("❌ Backend directory not found")
    finally:
        os.chdir(original_dir)

def test_from_forecast_service():
    """Test access from forecast service directory"""
    print("\n" + "="*50) 
    print("📊 TESTING FROM FORECAST SERVICE DIRECTORY")
    print("="*50)
    
    original_dir = os.getcwd()
    try:
        forecast_dir = Path("forecast_service")
        if forecast_dir.exists():
            os.chdir(forecast_dir)
            test_database_access()
        else:
            print("❌ Forecast service directory not found")
    finally:
        os.chdir(original_dir)

if __name__ == "__main__":
    print("🧪 DATABASE ACCESS TEST")
    print("="*50)
    
    # Test from project root
    print("🏠 TESTING FROM PROJECT ROOT")
    print("="*50)
    test_database_access()
    
    # Test from backend
    test_from_backend()
    
    # Test from forecast service
    test_from_forecast_service()
    
    print("\n✅ Database access test completed!") 