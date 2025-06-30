FROM continuumio/miniconda3:latest

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    cron \
    && rm -rf /var/lib/apt/lists/*

# Copy environment file
COPY environment.yml .

# Create conda environment
RUN conda env create -f environment.yml

# Make RUN commands use the new environment
SHELL ["conda", "run", "-n", "forecast_service", "/bin/bash", "-c"]

# Copy application code
COPY app/ ./app/
COPY scripts/ ./scripts/

# Create directories
RUN mkdir -p /app/models /app/logs

# Setup cron job for retraining
COPY scripts/crontab /etc/cron.d/retrain-cron
RUN chmod 0644 /etc/cron.d/retrain-cron
RUN crontab /etc/cron.d/retrain-cron

# Create non-root user
RUN useradd --create-home --shell /bin/bash forecast
RUN chown -R forecast:forecast /app
USER forecast

# Expose port
EXPOSE 8002

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD conda run -n forecast_service curl -f http://localhost:8002/health || exit 1

# Start script
COPY scripts/start.sh /app/start.sh
RUN chmod +x /app/start.sh

CMD ["/app/start.sh"]