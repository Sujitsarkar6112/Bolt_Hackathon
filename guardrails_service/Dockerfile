FROM nvcr.io/nvidia/tritonserver:23.10-py3

# Install additional Python packages
RUN pip install pydantic==2.5.0

# Copy model repository
COPY models/ /models/

# Set working directory
WORKDIR /models

# Expose Triton ports
EXPOSE 8000 8001 8002

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/v2/health/ready || exit 1

# Start Triton server
CMD ["tritonserver", "--model-repository=/models", "--log-verbose=1"]