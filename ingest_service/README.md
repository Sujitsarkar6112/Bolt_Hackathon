# Sales Ingest Service

A production-grade FastAPI microservice for ingesting Protobuf-encoded sales events from Kafka and storing them in MongoDB with comprehensive monitoring and testing.

## 🚀 Features

- **High-Performance Ingestion**: Async processing of Kafka messages with configurable batching
- **Protobuf Schema Validation**: Strict validation of sales events using Pydantic models
- **MongoDB Integration**: Efficient batch writes with duplicate detection and indexing
- **Prometheus Metrics**: Comprehensive metrics for monitoring and alerting
- **Production Ready**: Docker containerization, health checks, and graceful shutdown
- **Comprehensive Testing**: Unit and integration tests with testcontainers

## 📋 Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Kafka/        │    │   Ingest        │    │   MongoDB       │
│   Redpanda      │───▶│   Service       │───▶│   Database      │
│   (sales_txn)   │    │   (FastAPI)     │    │   (raw_sales)   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                              │
                              ▼
                       ┌─────────────────┐
                       │   Prometheus    │
                       │   Metrics       │
                       │   (Port 8001)   │
                       └─────────────────┘
```

## 🛠️ Technology Stack

- **Framework**: FastAPI with async/await
- **Message Queue**: Kafka (Redpanda for development)
- **Database**: MongoDB 7.0 with Motor async driver
- **Serialization**: Protocol Buffers (protobuf)
- **Monitoring**: Prometheus metrics
- **Testing**: pytest with testcontainers
- **Containerization**: Docker & Docker Compose

## 🚀 Quick Start

### Prerequisites

- Docker and Docker Compose
- Python 3.11+ (for local development)
- Make (optional, for convenience commands)

### Development Setup

1. **Start Infrastructure**:
```bash
make dev
# or
docker-compose -f docker-compose.override.yml up -d
```

2. **Install Dependencies** (for local development):
```bash
make build
# or
pip install -r requirements.txt
python -m grpc_tools.protoc --python_out=app/proto --proto_path=proto proto/sales_event.proto
```

3. **Run Tests**:
```bash
make test
# or
pytest tests/ -v
```

4. **Run Service Locally**:
```bash
make run
# or
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Production Deployment

```bash
# Build and run with Docker Compose
make docker-build
make docker-run

# View logs
make docker-logs

# Stop services
make docker-stop
```

## 📊 API Endpoints

### Health Check
```bash
GET /health
```
Returns service health status and connectivity to dependencies.

### Metrics
```bash
GET /metrics
```
Returns Prometheus-style metrics for monitoring.

### Statistics
```bash
GET /stats
```
Returns detailed service statistics including Kafka and MongoDB status.

### Graceful Shutdown
```bash
POST /shutdown
```
Initiates graceful service shutdown.

## 📈 Monitoring & Metrics

The service exposes Prometheus metrics on port 8001:

- `sales_events_processed_total`: Total events processed (with status labels)
- `sales_events_per_second`: Current processing rate
- `kafka_consumer_lag_milliseconds`: Kafka consumer lag
- `mongodb_writes_total`: Total MongoDB operations (with status labels)
- `event_processing_duration_seconds`: Processing time histogram
- `service_uptime_seconds`: Service uptime

## 🔧 Configuration

Environment variables (see `.env.example`):

```bash
# Kafka Configuration
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
KAFKA_TOPIC=sales_txn
KAFKA_GROUP_ID=ingest_service

# MongoDB Configuration
MONGODB_URL=mongodb://admin:password@localhost:27017/sales_db?authSource=admin
MONGODB_DATABASE=sales_db
MONGODB_COLLECTION=raw_sales

# Performance Tuning
BATCH_SIZE=100
FLUSH_INTERVAL=5.0
MAX_RETRIES=3
```

## 📝 Data Schema

### Sales Event (Protobuf)
```protobuf
message SalesEvent {
  string sku = 1;        // Product SKU
  int32 qty = 2;         // Quantity sold
  double price = 3;      // Unit price
  string ts = 4;         // ISO8601 timestamp
  string event_id = 5;   // Optional unique identifier
}
```

### MongoDB Document
```json
{
  "sku": "SKU-ABC-123",
  "qty": 5,
  "price": 29.99,
  "ts": "2024-01-15T10:30:00Z",
  "event_id": "event-001",
  "processed_at": 1705320600.123
}
```

## 🧪 Testing

### Run All Tests
```bash
make test
```

### Unit Tests Only
```bash
make test-unit
```

### Integration Tests Only
```bash
make test-integration
```

### Test Coverage
```bash
make test-coverage
```

The test suite includes:
- **Unit Tests**: Models, database operations, processing logic
- **Integration Tests**: End-to-end testing with real Kafka and MongoDB
- **API Tests**: FastAPI endpoint testing
- **Testcontainers**: Isolated testing with real services

## 🔍 Development

### Code Quality
```bash
make lint      # Check code quality
make format    # Format code
```

### Generate Protobuf Files
```bash
make proto
```

### View Logs
```bash
make docker-logs
```

## 📦 Project Structure

```
ingest_service/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI application
│   ├── config.py            # Configuration management
│   ├── models.py            # Pydantic models
│   ├── database.py          # MongoDB client
│   ├── kafka_consumer.py    # Kafka consumer
│   ├── processor.py         # Main processing logic
│   ├── metrics.py           # Prometheus metrics
│   └── proto/
│       ├── __init__.py
│       └── sales_event_pb2.py
├── tests/
│   ├── __init__.py
│   ├── conftest.py          # Test configuration
│   ├── test_models.py       # Model validation tests
│   ├── test_database.py     # Database operation tests
│   ├── test_processor.py    # Processing logic tests
│   ├── test_api.py          # API endpoint tests
│   └── test_integration.py  # End-to-end tests
├── proto/
│   └── sales_event.proto    # Protobuf schema
├── docker/
│   └── mongo-init.js        # MongoDB initialization
├── Dockerfile
├── docker-compose.override.yml
├── requirements.txt
├── pytest.ini
├── Makefile
└── README.md
```

## 🚨 Production Considerations

### Performance Tuning
- Adjust `BATCH_SIZE` and `FLUSH_INTERVAL` based on throughput requirements
- Configure Kafka consumer settings for optimal performance
- Monitor MongoDB connection pool settings

### Monitoring & Alerting
- Set up Prometheus scraping of metrics endpoint
- Configure alerts for high error rates, lag, and downtime
- Monitor resource usage (CPU, memory, disk)

### Security
- Use authentication for MongoDB and Kafka in production
- Implement network security (VPC, security groups)
- Regular security updates for base images

### Scaling
- Horizontal scaling: Run multiple service instances
- Kafka partitioning for parallel processing
- MongoDB sharding for large datasets

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.