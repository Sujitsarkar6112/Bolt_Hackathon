# Forecast Service

A production-grade MLOps service for demand forecasting using Prophet and Temporal Fusion Transformer (TFT) models with MLflow tracking and automated retraining.

## 🚀 Features

### Core Capabilities
- **Hybrid Forecasting**: Prophet for short-term (≤30 days), TFT for long-term (≤180 days)
- **Automated Retraining**: Nightly cron jobs with MLflow experiment tracking
- **REST API**: FastAPI endpoints for forecast generation and model management
- **Production Ready**: Docker containerization, health checks, and monitoring
- **GPU Support**: Optional GPU acceleration for TFT training

### Model Architecture
- **Prophet**: Facebook's time series forecasting tool for baseline predictions
- **TFT**: Temporal Fusion Transformer for complex covariate integration
- **Ensemble Logic**: Automatic model selection based on forecast horizon
- **MLflow Integration**: Comprehensive experiment tracking and model registry

## 📊 API Endpoints

### Forecast Generation
```bash
GET /forecast/{sku}?horizon=30&confidence_level=0.8
```
Returns JSON with median, p10, p90 predictions and model metadata.

### Health & Status
```bash
GET /health                 # Service health check
GET /models/status         # Model availability and metadata
GET /skus                  # List available SKUs
```

### Model Management
```bash
POST /retrain              # Trigger manual retraining
```

## 🛠️ Technology Stack

- **Framework**: FastAPI with async/await
- **ML Models**: Prophet, PyTorch Forecasting (TFT)
- **Experiment Tracking**: MLflow
- **Database**: MongoDB with Motor async driver
- **Containerization**: Docker & Docker Compose
- **Environment**: Conda for dependency management

## 🚀 Quick Start

### Prerequisites
- Docker and Docker Compose
- Conda (for local development)

### Launch with Docker Compose
```bash
# Start all services (MLflow, MongoDB, Forecast Service)
docker-compose up -d

# View logs
docker-compose logs -f forecast-service

# Setup MLflow experiment
docker-compose exec forecast-service python scripts/setup_mlflow.py
```

### Local Development
```bash
# Create conda environment
conda env create -f environment.yml
conda activate forecast_service

# Setup MLflow
python scripts/setup_mlflow.py

# Run service
python -m app.main
```

## 📈 Model Training & Deployment

### Automated Retraining
- **Schedule**: Daily at 2 AM (configurable via cron)
- **Trigger**: Automatic via cron or manual via API
- **Tracking**: All experiments logged to MLflow
- **Validation**: Automated model validation with MAE/MAPE metrics

### Training Process
1. **Data Loading**: Fetch latest sales data from MongoDB
2. **Prophet Training**: Baseline model with seasonality detection
3. **TFT Training**: Advanced model with covariate integration
4. **Validation**: Time-series cross-validation
5. **Registration**: Model artifacts saved to MLflow registry

### Model Selection Logic
```python
if horizon <= 30 days:
    use Prophet  # Fast, reliable for short-term
else:
    use TFT      # Complex patterns for long-term
```

## 🔧 Configuration

### Environment Variables
```bash
# Service Configuration
MONGODB_URL=mongodb://localhost:27017/sales_db
MLFLOW_TRACKING_URI=http://localhost:5000
LOG_LEVEL=INFO

# Model Configuration
PROPHET_SEASONALITY_MODE=multiplicative
TFT_MAX_EPOCHS=100
TFT_BATCH_SIZE=64
MIN_TRAINING_SAMPLES=90

# GPU Configuration
USE_GPU=false
GPU_DEVICE=0
```

### Model Hyperparameters
- **Prophet**: Seasonality modes, holiday effects, growth curves
- **TFT**: Hidden size, attention heads, dropout, learning rate
- **Training**: Validation split, early stopping, batch size

## 📊 Data Requirements

### Input Schema (MongoDB)
```json
{
  "sku": "SKU-ABC-123",
  "ts": "2024-01-15T10:30:00Z",
  "qty": 125,
  "price": 29.99,
  "processed_at": 1705320600.123
}
```

### Output Schema (API Response)
```json
{
  "sku": "SKU-ABC-123",
  "forecast_date": "2024-01-15T10:30:00Z",
  "horizon_days": 30,
  "model_used": "prophet",
  "confidence_level": 0.8,
  "forecast": [
    {
      "date": "2024-01-16T00:00:00Z",
      "median": 120.5,
      "p10": 95.2,
      "p90": 145.8
    }
  ]
}
```

## 🧪 Testing

### Run Integration Tests
```bash
# Start test environment
docker-compose up -d

# Run tests
conda activate forecast_service
pytest tests/ -v

# Test specific functionality
pytest tests/test_integration.py::test_forecast_short_term -v
```

### Test Coverage
- **Unit Tests**: Model components, data loading, API endpoints
- **Integration Tests**: End-to-end forecast generation with real data
- **Performance Tests**: Response times and throughput validation

## 📈 Monitoring & Observability

### Health Checks
- **Database Connectivity**: MongoDB connection status
- **Model Availability**: Prophet and TFT model loading status
- **MLflow Integration**: Experiment tracking connectivity

### Metrics & Logging
- **Structured Logging**: JSON format with correlation IDs
- **Model Metrics**: MAE, MAPE, training time, data quality
- **API Metrics**: Response times, error rates, throughput

### MLflow Tracking
- **Experiments**: Organized by model type and training date
- **Artifacts**: Model binaries, training plots, validation results
- **Model Registry**: Versioned models with staging/production tags

## 🔄 Deployment Pipeline

### Development Workflow
1. **Local Development**: Conda environment with hot reload
2. **Testing**: Automated tests with testcontainers
3. **Staging**: Docker deployment with test data
4. **Production**: Orchestrated deployment with monitoring

### Production Considerations
- **Scaling**: Horizontal scaling for API, vertical for training
- **Data Pipeline**: Real-time ingestion from sales systems
- **Model Governance**: A/B testing, shadow deployments
- **Monitoring**: Alerting on model drift and performance degradation

## 📄 API Documentation

### Interactive Documentation
- **Swagger UI**: http://localhost:8002/docs
- **ReDoc**: http://localhost:8002/redoc

### Example Usage
```python
import httpx

# Get forecast
async with httpx.AsyncClient() as client:
    response = await client.get(
        "http://localhost:8002/forecast/SKU-ABC-123?horizon=30"
    )
    forecast = response.json()
    
    print(f"30-day forecast for {forecast['sku']}")
    for point in forecast['forecast'][:7]:  # First week
        print(f"{point['date']}: {point['median']:.0f} units")
```

## 🤝 Contributing

1. Fork the repository
2. Create feature branch with descriptive name
3. Implement changes with comprehensive tests
4. Update documentation and examples
5. Submit pull request with detailed description

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

---

**Forecast Service**: Production MLOps for intelligent demand forecasting.