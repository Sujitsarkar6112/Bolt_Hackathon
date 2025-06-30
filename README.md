# DemandBot - AI-Powered Demand Forecasting Platform

A comprehensive enterprise-grade conversational AI platform for demand forecasting that combines time-series models with Retrieval-Augmented Generation (RAG) capabilities and safety guardrails.

[![CI/CD Pipeline](https://github.com/your-org/demandbot/workflows/CI%2FCD%20Pipeline/badge.svg)](https://github.com/your-org/demandbot/actions)
[![Python Services](https://github.com/your-org/demandbot/workflows/Python%20Services/badge.svg)](https://github.com/your-org/demandbot/actions)
[![Frontend](https://github.com/your-org/demandbot/workflows/Frontend/badge.svg)](https://github.com/your-org/demandbot/actions)
[![codecov](https://codecov.io/gh/your-org/demandbot/branch/main/graph/badge.svg)](https://codecov.io/gh/your-org/demandbot)
[![Quality Gate Status](https://sonarcloud.io/api/project_badges/measure?project=your-org_demandbot&metric=alert_status)](https://sonarcloud.io/dashboard?id=your-org_demandbot)
[![Security Rating](https://sonarcloud.io/api/project_badges/measure?project=your-org_demandbot&metric=security_rating)](https://sonarcloud.io/dashboard?id=your-org_demandbot)

## 🚀 Features

### Core Capabilities
- **Event-Driven Architecture**: Exactly-once Kafka processing with MongoDB change streams
- **Hybrid Forecasting Engine**: Combines Prophet and Temporal Fusion Transformer (TFT) models
- **RAG-Powered Chat**: Natural language interface with enterprise document integration
- **Universal Guardrails**: NGINX + Triton validation for all API responses
- **Real-time Analytics**: WebSocket/SSE streaming with exponential backoff reconnection
- **Auto-Retraining**: Change stream triggers for incremental model updates

### User Interface
- **Three-Panel Design**: Chat history, main conversation, and contextual information
- **Interactive Charts**: Real-time forecast visualization with confidence intervals
- **Source Attribution**: Document references and relevance scoring
- **Entity Verification**: Visual confirmation of validated business entities

## 🏗️ Event-Driven Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Kafka         │    │   Change        │    │   Triton        │
│   (Exactly-Once)│───▶│   Streams       │───▶│   Guardrails    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   MongoDB       │    │   Auto-Retrain  │    │   NGINX         │
│   Ingestion     │    │   Pipeline      │    │   Gateway       │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   WebSocket/SSE │    │   ML Models     │    │   Frontend      │
│   Gateway       │    │   (Prophet/TFT) │    │   (React)       │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 🔄 Data Flow Pipeline

### 1. **Kafka Exactly-Once Ingestion**
- Idempotent producer with transactional commits
- Success events published to `sales_ingested` topic
- Automatic retry with exponential backoff

### 2. **MongoDB Change Streams**
- Real-time monitoring of sales data changes
- Automatic retrain triggers for SKU data updates
- Publishes to `model_retrain` queue

### 3. **Auto-Retraining Pipeline**
- Incremental model updates based on data volume
- Prophet for short-term, TFT for long-term forecasts
- MLflow tracking with model versioning

### 4. **Document Re-indexing**
- Filesystem and S3 event watchers
- Automatic PDF processing and vector embedding
- Real-time RAG knowledge base updates

### 5. **Universal Guardrails**
- NGINX sidecar routes all responses through Triton
- Entity validation against enterprise catalog
- Response sanitization and confidence scoring

### 6. **WebSocket/SSE Gateway**
- Real-time streaming with exponential backoff
- Connection pooling and health monitoring
- Graceful degradation and reconnection

## 🛠️ Technology Stack

- **Frontend**: React 18, TypeScript, Tailwind CSS, Recharts
- **Backend**: Python 3.12, FastAPI, Pydantic
- **Event Streaming**: Apache Kafka with exactly-once semantics
- **Database**: MongoDB 7.0 with change streams
- **ML Models**: Prophet, PyTorch Forecasting (TFT), MLflow
- **RAG System**: LangChain, OpenAI Embeddings, MongoDB Atlas Vector Search
- **Guardrails**: NVIDIA Triton Inference Server
- **Gateway**: NGINX with custom validation routing
- **Deployment**: Docker Compose, Kubernetes with Helm

## 🚀 Quick Start

### Prerequisites
- Docker and Docker Compose v2
- Node.js 18+ (for local development)
- Python 3.12+ (for local development)

### Production Deployment

```bash
# Clone repository
git clone https://github.com/your-org/demandbot.git
cd demandbot

# Set environment variables
cp .env.example .env
# Edit .env with your configuration

# Start complete pipeline
docker-compose -f docker-compose.prod.yml up -d

# Verify deployment
curl http://localhost/health
curl http://localhost:8080/api/health
```

### Development Setup

```bash
# Frontend
npm install
npm run dev

# Backend services
cd backend && pip install -r requirements.txt && uvicorn app.main:app --reload
cd ingest_service && python -m app.main
cd forecast_service && python -m app.main
cd rag_service && python -m app.main
cd gateway_service && python -m app.main
```

## 📊 API Endpoints

### Core APIs (via NGINX Gateway)
- `POST /api/chat` - Chat with DemandBot (Triton validated)
- `GET /api/forecast/{sku}` - Get demand forecast (Triton validated)
- `POST /api/ask` - RAG-powered Q&A (Triton validated)
- `GET /ws` - WebSocket connection for real-time chat
- `GET /stream` - Server-Sent Events for streaming responses

### Service Health
- `GET /api/health` - Overall system health
- `GET /api/forecast/health` - Forecast service status
- `GET /api/ask/health` - RAG service status

## 🧪 Testing & Quality Gates

### Automated Testing
- **80%+ Code Coverage** across all services
- **Unit Tests**: pytest with comprehensive mocking
- **Integration Tests**: Real service interactions
- **E2E Tests**: Complete pipeline validation
- **Load Tests**: K6 performance testing
- **Security Scans**: Trivy container scanning

### CI/CD Pipeline
```bash
# Run quality checks locally
pytest --cov=. --cov-report=html --cov-fail-under=80
npm run test:coverage
npm run lint && npm run type-check

# E2E pipeline test
python tests/e2e/test_pipeline.py
k6 run tests/e2e/load_test.js
```

### Quality Metrics
- **Response Time**: <2s for 95% of requests
- **Availability**: 99.9% uptime target
- **Forecast Accuracy**: 85-92% within confidence intervals
- **Entity Validation**: 99.9% accuracy against catalog

## 🔒 Security & Guardrails

### Entity Validation
- All product SKUs validated against enterprise catalog
- Invalid entities flagged and sanitized in real-time
- Confidence scoring for validation decisions

### Response Safety
- Universal Triton validation for all API responses
- Automatic sanitization of hallucinated content
- Source attribution for all document-based insights

### Infrastructure Security
- Container vulnerability scanning with Triton
- Dependency security checks with Safety/Bandit
- Network policies and service mesh security

## 📈 Monitoring & Observability

### Metrics & Dashboards
- **Prometheus**: Service metrics and alerting
- **Grafana**: Real-time dashboards
- **MLflow**: Model performance tracking
- **Codecov**: Test coverage trending

### Health Checks
- **Service Health**: All endpoints monitored
- **Data Quality**: Automated validation pipelines
- **Model Drift**: Continuous accuracy monitoring
- **Performance**: Response time and throughput tracking

## 🚀 Production Considerations

### Scaling
- **Horizontal**: Multiple service replicas with load balancing
- **Vertical**: GPU acceleration for ML model training
- **Auto-scaling**: Kubernetes HPA based on CPU/memory/custom metrics

### High Availability
- **Database**: MongoDB replica sets with automatic failover
- **Message Queue**: Kafka cluster with replication
- **Load Balancing**: NGINX with health checks and circuit breakers
- **Graceful Degradation**: Fallback responses when services unavailable

### Performance Optimization
- **Caching**: Redis for frequently accessed data
- **Connection Pooling**: Optimized database connections
- **Batch Processing**: Efficient data ingestion and processing
- **CDN**: Static asset delivery optimization

## 🤝 Contributing

1. Fork the repository
2. Create feature branch with descriptive name
3. Implement changes with comprehensive tests (80%+ coverage required)
4. Update documentation and examples
5. Submit pull request with detailed description

### Development Workflow
```bash
# Setup development environment
make setup-dev

# Run quality checks
make test-all
make lint-all
make security-scan

# Run E2E tests
make test-e2e
```

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

---

**DemandBot**: Enterprise-grade AI-powered demand forecasting with event-driven architecture and universal safety guardrails.