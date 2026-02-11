# Multi-stage build for optimized production image
# Stage 1: Builder stage for dependencies
FROM python:3.11-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc && \
    rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt


# Stage 2: Runtime stage - minimal production image
FROM python:3.11-slim

WORKDIR /app

# Create non-root user for security
RUN useradd -m -u 1000 apiuser && \
    mkdir -p /tmp/uploads /tmp/outputs && \
    chown -R apiuser:apiuser /app /tmp/uploads /tmp/outputs

# Copy Python dependencies from builder stage
COPY --from=builder /root/.local /home/apiuser/.local

# Copy application code
COPY --chown=apiuser:apiuser ./app ./app

# Switch to non-root user
USER apiuser

# Update PATH to include user-installed packages
ENV PATH=/home/apiuser/.local/bin:$PATH

# Expose port 8000
EXPOSE 8000

# Health check (Kubernetes will use this)
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/v1/health')"

# Run the application
# Using uvicorn with:
# - host 0.0.0.0: Listen on all interfaces (required in container)
# - port 8000: Standard HTTP port
# - workers 1: Single worker for local dev (scale with replicas in K8s)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
