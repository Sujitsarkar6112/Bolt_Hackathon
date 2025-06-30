# RAG Service

A production-grade Retrieval-Augmented Generation service that processes local PDF documents, embeds them using OpenAI, stores vectors in a local FAISS index, and provides grounded answers with IEEE-style citations.

## 🚀 Features

### Core Capabilities
- **Local Document Processing**: Automatic PDF, TXT, and MD file processing with chunking
- **OpenAI Embeddings**: Uses `text-embedding-3-small` for high-quality vector representations
- **FAISS Vector Search**: Local, persistent vector storage with similarity search
- **LangChain Integration**: RetrievalQA pattern with customizable retrieval
- **IEEE Citations**: Properly formatted citations with source attribution
- **File Watching**: Automatic re-indexing when documents change

### Self-Host Mode
- **Fully Offline**: Zero cloud dependencies after initial setup
- **Local Storage**: Documents stored in `./docs` folder
- **Persistent Index**: FAISS index persisted to `./faiss_index`
- **Zero Cloud Cost**: No MongoDB Atlas or S3 charges

### API Endpoints
- `POST /ask` - Ask questions with grounded answers and sources
- `GET /search` - Search documents without generating answers
- `POST /ingest` - Trigger manual document ingestion
- `GET /documents` - List all indexed documents
- `DELETE /documents/{name}` - Remove specific documents

## 🛠️ Technology Stack

- **Framework**: FastAPI with async/await
- **Embeddings**: OpenAI text-embedding-3-small (1536 dimensions)
- **LLM**: OpenAI GPT-3.5-turbo for answer generation
- **Vector Store**: FAISS (Facebook AI Similarity Search)
- **Document Processing**: PyPDF2, LangChain text splitters
- **File Watching**: Watchdog for automatic re-indexing

## 🚀 Quick Start

### Prerequisites
- OpenAI API key
- Python 3.11+

### Local Setup

1. **Install dependencies**:
```bash
pip install -r requirements.txt
```

2. **Configure environment**:
```bash
cp .env.sample .env
# Edit .env with your OpenAI API key
```

3. **Create documents directory**:
```bash
mkdir -p docs
# Add your PDF/TXT/MD files to docs/
```

4. **Run initial document ingestion**:
```bash
python ingest_docs.py
```

5. **Start the service**:
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8003 --reload
```

### Docker Deployment

```bash
# Build image
docker build -t rag-service .

# Run container
docker run -d \
  -p 8003:8003 \
  -v $(pwd)/docs:/app/docs \
  -v $(pwd)/faiss_index:/app/faiss_index \
  -e OPENAI_API_KEY=your-key \
  rag-service
```

## 📊 API Usage

### Ask Questions
```bash
curl -X POST "http://localhost:8003/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What are the Q4 marketing strategies for SKU-ABC?",
    "sku": "SKU-ABC",
    "top_k": 4
  }'
```

**Response**:
```json
{
  "query": "What are the Q4 marketing strategies for SKU-ABC?",
  "answer": "Based on the Q4 Marketing Strategy document [1], SKU-ABC will have a comprehensive promotional campaign including a 25% discount during Valentine's Day and influencer partnerships [1].",
  "sources": [
    {
      "document": "Q4_Marketing_Strategy.pdf",
      "page": 12,
      "chunk_id": "q4_marketing_strategy_5_a1b2c3d4",
      "relevance_score": 0.89,
      "content": "SKU-ABC promotional campaign scheduled for Q4 with 25% discount...",
      "citation": "\"Q4_Marketing_Strategy.pdf\", p. 12, 2024."
    }
  ],
  "sku_filter": "SKU-ABC",
  "timestamp": "2024-01-15T10:30:00Z",
  "model_used": "gpt-3.5-turbo",
  "total_sources": 1
}
```

### Search Documents
```bash
curl "http://localhost:8003/search?query=marketing%20strategy&top_k=3"
```

### List Documents
```bash
curl "http://localhost:8003/documents"
```

## 📁 Document Management

### CLI Tool for Ingestion

```bash
# Ingest all documents
python ingest_docs.py

# Force re-ingestion (clears existing)
python ingest_docs.py --force

# Ingest single file
python ingest_docs.py --file ./docs/new_document.pdf

# List indexed documents
python ingest_docs.py --list
```

### Supported File Types
- **PDF**: Extracted using PyPDF2 with page tracking
- **TXT**: Plain text files with UTF-8 encoding
- **MD**: Markdown files with formatting preserved

### Document Structure
```
docs/
├── Q4_Marketing_Strategy.pdf
├── Product_Launch_Calendar_2024.md
├── Sales_Forecast_2024.txt
└── Competitive_Analysis.pdf
```

## 🔧 Configuration

### Environment Variables
```bash
# OpenAI
OPENAI_API_KEY=sk-your-openai-api-key-here

# Local Paths
DOCUMENTS_PATH=./docs
FAISS_INDEX_PATH=./faiss_index

# Processing
CHUNK_SIZE=1000
CHUNK_OVERLAP=200
```

### Chunking Strategy
- **Chunk Size**: 1000 characters (configurable)
- **Overlap**: 200 characters for context preservation
- **Splitters**: Recursive splitting on paragraphs, sentences, words

### Vector Search
- **Embedding Model**: text-embedding-3-small (1536 dimensions)
- **Similarity**: Cosine similarity via FAISS
- **Top-K**: 4 sources by default (configurable 1-20)
- **Filtering**: Support for SKU and document name filters

### Citation Styles
- **IEEE** (default): `"Document.pdf", p. 12, 2024.`
- **APA**: `Document Title (2024), p. 12.`
- **MLA**: `"Document Title." 12. 2024.`

## 🧪 Testing

### Integration Tests
```bash
# Run all tests
pytest tests/ -v

# Test specific functionality
pytest tests/test_faiss_vector.py::TestFAISSVectorStore::test_store_and_search_documents -v
```

### Manual Testing
```bash
# Health check
curl http://localhost:8003/health

# Test search
curl "http://localhost:8003/search?query=test&top_k=2"

# Test ask endpoint
curl -X POST http://localhost:8003/ask \
  -H "Content-Type: application/json" \
  -d '{"query": "What is our marketing strategy?"}'
```

## 📈 Monitoring & Observability

### Health Checks
- **Vector Store**: FAISS index connectivity
- **Documents**: Count of indexed documents
- **Embeddings**: OpenAI API connectivity

### Logging
- **Structured Logging**: JSON format with timestamps
- **Document Processing**: Chunk counts and processing times
- **Search Performance**: Query times and result counts
- **Error Tracking**: Detailed error messages and stack traces

### Metrics
- **Document Count**: Total indexed documents
- **Chunk Count**: Total text chunks in vector store
- **Index Size**: FAISS index size in MB
- **Search Latency**: Average query response time

## 🔒 Security & Best Practices

### Data Privacy
- **Local Storage**: All data remains on your infrastructure
- **No Cloud Dependencies**: Zero external data transmission
- **Access Control**: File system permissions control access

### Production Deployment
- **Environment Variables**: All secrets via environment
- **Health Checks**: Kubernetes-ready health endpoints
- **Graceful Shutdown**: Proper cleanup of connections and watchers
- **Volume Persistence**: Docker volumes for data persistence

## 🚀 Advanced Features

### Custom Embeddings
```python
# Override embedding service for custom models
class CustomEmbeddingService(EmbeddingService):
    async def get_embedding(self, text: str) -> List[float]:
        # Your custom embedding logic
        pass
```

### Document Metadata Enhancement
```python
# Add custom metadata during processing
metadata = {
    "department": "marketing",
    "classification": "confidential",
    "expiry_date": "2024-12-31"
}
```

### Advanced Filtering
```python
# Custom search filters
results = await vector_store.similarity_search(
    query="marketing strategy",
    top_k=5,
    sku_filter="SKU-ABC"
)
```

## 🤝 Contributing

1. Fork the repository
2. Create feature branch with descriptive name
3. Add comprehensive tests for new functionality
4. Update documentation and examples
5. Submit pull request with detailed description

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

---

**RAG Service**: Self-hosted document intelligence with local FAISS and zero cloud dependencies.