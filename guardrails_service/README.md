# Guardrails Service - Triton Inference Server

A production-grade guardrails service using NVIDIA Triton Inference Server with Pydantic validation models for enterprise AI safety.

## 🚀 Features

### Core Capabilities
- **Entity Validation**: Validates SKUs, product names, and campaign IDs against enterprise catalog
- **Negative Value Detection**: Rejects responses with negative quantities or prices
- **Date Format Validation**: Ensures ISO8601 compliance for temporal data
- **HTTP Status Codes**: Returns appropriate HTTP status codes (200/400/500)
- **Confidence Scoring**: Provides confidence metrics for validation decisions

### Triton Integration
- **Python Backend**: Custom Pydantic validation models
- **Ensemble Models**: Orchestrates validation pipeline with HTTP-like responses
- **Dynamic Batching**: Optimized for high-throughput validation
- **Health Monitoring**: Comprehensive health checks and metrics

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   UI/Client     │───▶│ Ensemble Model  │───▶│ Guardrail Model │
│   (HTTP/gRPC)   │    │ (Orchestrator)  │    │ (Validator)     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                              │
                              ▼
                       ┌─────────────────┐
                       │ HTTP Response   │
                       │ 200/400/500     │
                       └─────────────────┘
```

## 🛠️ Technology Stack

- **Inference Server**: NVIDIA Triton Inference Server 23.10
- **Backend**: Python with Pydantic validation
- **Deployment**: Docker, Kubernetes with Helm
- **Monitoring**: Built-in Triton metrics and health checks

## 🚀 Quick Start

### Docker Deployment

```bash
# Build and start services
docker-compose up -d

# Check health
curl http://localhost:8000/v2/health/ready

# Test validation
python client/guardrail_client.py \
  --url http://localhost:8000 \
  --text "SKU-ABC has quantity: 100 units at price: $29.99"
```

### Kubernetes Deployment

```bash
# Install with Helm
helm install triton-guardrails ./helm/triton-guardrails

# Check status
kubectl get pods -l app.kubernetes.io/name=triton-guardrails

# Port forward for testing
kubectl port-forward svc/triton-guardrails 8000:8000
```

## 📊 API Usage

### Validation Request

```bash
curl -X POST http://localhost:8000/v2/models/ensemble_guardrail/infer \
  -H "Content-Type: application/json" \
  -d '{
    "inputs": [
      {
        "name": "TEXT",
        "shape": [1, 1],
        "datatype": "BYTES",
        "data": ["SKU-ABC sold 100 units at $29.99"]
      }
    ],
    "outputs": [
      {"name": "STATUS_CODE"},
      {"name": "RESULT"}
    ]
  }'
```

### Response Format

```json
{
  "outputs": [
    {
      "name": "STATUS_CODE",
      "data": [200]
    },
    {
      "name": "RESULT",
      "data": ["{\"status_code\": 200, \"is_safe\": true, \"violations\": [], \"sanitized_text\": \"SKU-ABC sold 100 units at $29.99\", \"entities_found\": [\"SKU-ABC\"], \"confidence_score\": 1.0}"]
    }
  ]
}
```

## 🔒 Validation Rules

### Entity Validation
- **Valid Entities**: SKU-ABC, SKU-XYZ, Product-X, CAMPAIGN-2024-VAL, etc.
- **Pattern Matching**: Regex-based extraction of entity references
- **Catalog Verification**: Cross-reference against enterprise entity catalog

### Value Validation
- **Negative Quantities**: Rejects any negative quantity references
- **Negative Prices**: Detects and flags negative pricing information
- **Date Formats**: Validates ISO8601 date format compliance

### Response Codes
- **200 (OK)**: Text passes all validation checks
- **400 (Bad Request)**: Validation violations detected
- **500 (Internal Error)**: Processing or system errors

## 🧪 Testing

### Integration Tests

```bash
# Run comprehensive test suite
python -m pytest tests/test_guardrails.py -v

# Test specific scenarios
python tests/test_guardrails.py::TestGuardrailsService::test_negative_quantity_violation
```

### Manual Testing

```bash
# Test valid text
python client/guardrail_client.py \
  --text "SKU-ABC has 100 units available"

# Test invalid entities
python client/guardrail_client.py \
  --text "SKU-FAKE-123 is a new product"

# Test negative values
python client/guardrail_client.py \
  --text "Product has quantity: -50 units"
```

## 🎯 UI Integration Flow

### How UI Calls Triton Before Displaying Answers

```javascript
// 1. Generate AI response
const aiResponse = await generateAIResponse(userQuery);

// 2. Validate with Triton guardrails
const validationResult = await validateWithTriton(aiResponse);

// 3. Handle validation result
if (validationResult.status_code === 200) {
  // Safe to display
  displayResponse(aiResponse);
} else if (validationResult.status_code === 400) {
  // Show sanitized version or error
  displayResponse(validationResult.sanitized_text);
  showWarning("Response contained invalid information");
} else {
  // System error
  displayError("Unable to validate response safety");
}
```

### Client Integration Example

```python
from client.guardrail_client import GuardrailClient

# Initialize client
guardrail = GuardrailClient("http://triton-guardrails:8000")

# Validate AI response before showing to user
def safe_display_response(ai_response: str) -> str:
    validation = guardrail.validate_text(ai_response)
    
    if validation["is_safe"]:
        return ai_response
    elif validation["status_code"] == 400:
        # Show sanitized version with warning
        return f"⚠️ {validation['sanitized_text']}"
    else:
        return "❌ Response validation failed"
```

## ⚙️ Configuration

### Model Configuration

**Guardrail Model** (`models/guardrail/config.pbtxt`):
- Backend: Python with Pydantic validation
- Batch Size: Up to 8 requests
- Instance Count: 2 for redundancy

**Ensemble Model** (`models/ensemble_guardrail/config.pbtxt`):
- Platform: Ensemble orchestration
- HTTP Status Code generation
- Error handling and fallbacks

### Helm Configuration

**Key Values** (`helm/triton-guardrails/values.yaml`):
- Replica Count: 2 (high availability)
- Auto-scaling: CPU/Memory based (2-10 replicas)
- Resource Limits: 2 CPU, 4Gi memory
- Health Checks: Comprehensive liveness/readiness probes

## 📈 Monitoring & Observability

### Health Endpoints
- `/v2/health/live` - Server liveness
- `/v2/health/ready` - Model readiness
- `/v2/models` - Model availability

### Metrics
- Request throughput and latency
- Validation success/failure rates
- Entity detection accuracy
- Resource utilization

### Logging
- Structured JSON logging
- Validation decision audit trail
- Performance metrics
- Error tracking and alerting

## 🔧 Production Considerations

### Scaling
- **Horizontal**: Multiple Triton replicas with load balancing
- **Vertical**: GPU acceleration for larger models
- **Auto-scaling**: Kubernetes HPA based on CPU/memory/custom metrics

### Security
- **Network Policies**: Restrict access to validation endpoints
- **RBAC**: Kubernetes role-based access control
- **TLS**: Encrypted communication in production

### Performance
- **Batching**: Dynamic batching for optimal throughput
- **Caching**: Model artifact caching for faster startup
- **Resource Limits**: Proper CPU/memory allocation

## 🤝 Contributing

1. Fork the repository
2. Create feature branch with descriptive name
3. Add comprehensive tests for new validation rules
4. Update documentation and examples
5. Submit pull request with detailed description

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

---

**Guardrails Service**: Enterprise-grade AI safety with Triton Inference Server.