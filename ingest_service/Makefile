.PHONY: help build test test-unit test-integration run dev clean docker-build docker-run docker-stop

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Targets:'
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-15s %s\n", $$1, $$2}\' $(MAKEFILE_LIST)

build: ## Install dependencies
	pip install -r requirements.txt
	python -m grpc_tools.protoc --python_out=app/proto --proto_path=proto proto/sales_event.proto

test: ## Run all tests
	pytest tests/ -v

test-unit: ## Run unit tests only
	pytest tests/ -v -m "not integration"

test-integration: ## Run integration tests only
	pytest tests/ -v -m integration

test-coverage: ## Run tests with coverage
	pytest tests/ --cov=app --cov-report=html --cov-report=term

run: ## Run the service locally
	uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

dev: ## Start development environment
	docker-compose -f docker-compose.override.yml up -d

clean: ## Clean up generated files
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf htmlcov/
	rm -rf .coverage
	rm -rf .pytest_cache/

docker-build: ## Build Docker image
	docker build -t ingest-service:latest .

docker-run: ## Run with Docker Compose
	docker-compose -f docker-compose.override.yml up -d

docker-stop: ## Stop Docker Compose
	docker-compose -f docker-compose.override.yml down

docker-logs: ## View Docker logs
	docker-compose -f docker-compose.override.yml logs -f ingest-service

lint: ## Run code linting
	flake8 app/ tests/
	black --check app/ tests/
	isort --check-only app/ tests/

format: ## Format code
	black app/ tests/
	isort app/ tests/

proto: ## Generate protobuf files
	python -m grpc_tools.protoc --python_out=app/proto --proto_path=proto proto/sales_event.proto

requirements: ## Update requirements.txt
	pip freeze > requirements.txt