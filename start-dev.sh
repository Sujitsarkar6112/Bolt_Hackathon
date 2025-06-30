#!/bin/bash

echo "🚀 Starting development environment..."

# Check if Python is available
if command -v python3 &> /dev/null; then
    echo "✅ Python detected"
    
    # Install Python dependencies if requirements.txt exists
    for service in backend rag_service forecast_service gateway_service; do
        if [ -f "$service/requirements.txt" ]; then
            echo "📦 Installing dependencies for $service..."
            cd "$service" && python3 -m pip install -r requirements.txt --quiet && cd ..
        fi
    done
    
    # Start all services using the Node.js service manager
    npm run start:services
else
    echo "⚠️  Python not available, starting frontend only..."
    npm run dev
fi