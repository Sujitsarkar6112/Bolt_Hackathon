#!/usr/bin/env python3
"""
Full Application Startup Script for DemandBot
This script starts all services with proper configurations and MongoDB setup
"""

import os
import sys
import time
import subprocess
import threading
import sqlite3
from pathlib import Path

def set_environment_variables():
    """Set environment variables for all services"""
    os.environ['OPENAI_API_KEY'] = os.getenv('OPENAI_API_KEY', 'sk-your-openai-api-key-placeholder')
    os.environ['MONGODB_URL'] = 'mongodb://localhost:27017/demandbot'
    os.environ['MONGODB_DATABASE'] = 'demandbot'
    os.environ['ENVIRONMENT'] = 'development'
    os.environ['LOG_LEVEL'] = 'INFO'
    
    print("✅ Environment variables set")

def check_sqlite_data():
    """Check if SQLite data exists"""
    db_path = Path("data/demandbot.db")
    if db_path.exists():
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM sales")
        count = cursor.fetchone()[0]
        conn.close()
        print(f"✅ SQLite database found with {count} sales records")
        return True
    else:
        print("❌ SQLite database not found")
        return False

def start_service(service_name, command, cwd=None, background=True):
    """Start a service"""
    print(f"🚀 Starting {service_name}...")
    
    if background:
        # Start service in background
        process = subprocess.Popen(
            command,
            shell=True,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == 'nt' else 0
        )
        print(f"✅ {service_name} started (PID: {process.pid})")
        return process
    else:
        # Start service in foreground
        subprocess.run(command, shell=True, cwd=cwd)

def check_service_health(url, service_name, timeout=30):
    """Check if a service is healthy"""
    import requests
    
    for i in range(timeout):
        try:
            response = requests.get(url, timeout=2)
            if response.status_code == 200:
                print(f"✅ {service_name} is healthy")
                return True
        except:
            pass
        
        if i < timeout - 1:
            time.sleep(1)
    
    print(f"❌ {service_name} health check failed")
    return False

def main():
    """Main startup function"""
    print("🚀 Starting Full DemandBot Application")
    print("=" * 50)
    
    # Set environment variables
    set_environment_variables()
    
    # Check data
    if not check_sqlite_data():
        return False
    
    # Start services
    services = []
    
    # 1. Enhanced Backend (already running)
    print("📋 Enhanced Backend should already be running on port 8005")
    if not check_service_health("http://localhost:8005/health", "Enhanced Backend", 5):
        print("❌ Enhanced Backend not running. Please start it with:")
        print("   cd backend && python app/enhanced_main.py")
        return False
    
    # 2. Gateway Service (already running) 
    print("📋 Gateway Service should already be running on port 8004")
    if not check_service_health("http://localhost:8004/health", "Gateway Service", 5):
        print("❌ Gateway Service not running. Please start it with:")
        print("   cd gateway_service && python -m uvicorn app.main:app --host 0.0.0.0 --port 8004")
        return False
    
    # 3. Try to start RAG Service (modified to work without MongoDB)
    print("🔄 Starting RAG Service...")
    rag_process = start_service(
        "RAG Service",
        "python -c \"import os; os.environ['MONGODB_URL']='sqlite:///data/demandbot.db'; exec(open('app/main.py').read())\"",
        cwd="rag_service"
    )
    services.append(rag_process)
    time.sleep(3)
    
    # 4. Try to start Forecast Service
    print("🔄 Starting Forecast Service...")
    forecast_process = start_service(
        "Forecast Service", 
        "python -c \"import os; os.environ['MONGODB_URL']='sqlite:///data/demandbot.db'; exec(open('app/main.py').read())\"",
        cwd="forecast_service"
    )
    services.append(forecast_process)
    time.sleep(3)
    
    # 5. Frontend (already running)
    print("📋 Frontend should already be running on port 5173")
    if not check_service_health("http://localhost:5173", "Frontend", 5):
        print("❌ Frontend not running. Please start it with:")
        print("   npm run dev")
        return False
    
    # Final health checks
    print("\n🔍 Performing final health checks...")
    time.sleep(5)
    
    health_results = {
        "Enhanced Backend": check_service_health("http://localhost:8005/health", "Enhanced Backend", 5),
        "Gateway Service": check_service_health("http://localhost:8004/health", "Gateway Service", 5), 
        "Frontend": check_service_health("http://localhost:5173", "Frontend", 5),
        "RAG Service": check_service_health("http://localhost:8002/health", "RAG Service", 5),
        "Forecast Service": check_service_health("http://localhost:8003/health", "Forecast Service", 5)
    }
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 FULL APPLICATION STATUS")
    print("=" * 50)
    
    running_services = 0
    for service, healthy in health_results.items():
        status = "✅ RUNNING" if healthy else "❌ STOPPED"
        print(f"{service:<20} {status}")
        if healthy:
            running_services += 1
    
    print(f"\n🎯 Services Running: {running_services}/5")
    
    if running_services >= 3:
        print("\n🎉 APPLICATION IS READY!")
        print("🌐 Main Interface: http://localhost:5173")
        print("🔗 Enhanced Backend: http://localhost:8005")
        print("🚪 Gateway Service: http://localhost:8004")
        
        if health_results["RAG Service"]:
            print("📚 RAG Service: http://localhost:8002")
        if health_results["Forecast Service"]:
            print("📈 Forecast Service: http://localhost:8003")
        
        print("\n💡 Try these queries in the chat:")
        print("   • 'What strategic insights do you have for Electronics?'")
        print("   • 'Give me AI-powered recommendations for Beauty products'")
        print("   • 'How can I improve my business performance?'")
        
    else:
        print(f"\n⚠️  Only {running_services}/5 services running")
        print("The core application should still work with Enhanced Backend + Frontend + Gateway")
    
    return True

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n🛑 Startup interrupted")
    except Exception as e:
        print(f"❌ Error: {e}") 