.PHONY: help setup build test run clean docker-build docker-run docker-stop

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Targets:'
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-15s %s\n", $$1, $$2}\' $(MAKEFILE_LIST)

setup: ## Setup conda environment
	conda env create -f environment.yml
	@echo "Activate environment with: conda activate forecast_service"

build: ## Install dependencies in existing environment
	conda env update -f environment.yml

test: ## Run all tests
	pytest tests/ -v

test-integration: ## Run integration tests only
	pytest tests/test_integration.py -v

test-coverage: ## Run tests with coverage
	pytest tests/ --cov=app --cov-report=html --cov-report=term

run: ## Run the service locally
	python -m app.main

run-dev: ## Run with auto-reload
	uvicorn app.main:app --host 0.0.0.0 --port 8002 --reload

clean: ## Clean up generated files
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf htmlcov/
	rm -rf .coverage
	rm -rf .pytest_cache/

docker-build: ## Build Docker image
	docker build -t forecast-service:latest .

docker-run: ## Run with Docker Compose
	docker-compose up -d

docker-stop: ## Stop Docker Compose
	docker-compose down

docker-logs: ## View Docker logs
	docker-compose logs -f forecast-service

setup-mlflow: ## Setup MLflow experiment
	python scripts/setup_mlflow.py

retrain: ## Trigger manual retraining
	python app/cron/retrain_scheduler.py

lint: ## Run code linting
	flake8 app/ tests/
	black --check app/ tests/
	isort --check-only app/ tests/

format: ## Format code
	black app/ tests/
	isort app/ tests/

requirements: ## Export conda environment
	conda env export > environment.yml

notebook: ## Start Jupyter notebook
	jupyter notebook

mlflow-ui: ## Start MLflow UI
	mlflow ui --host 0.0.0.0 --port 5000