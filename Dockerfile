# Build stage
FROM python:3.11-slim AS builder

WORKDIR /build

# Copy project files
COPY pyproject.toml requirements.txt ./
COPY freefeed_mcp_server/ freefeed_mcp_server/

# Install dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -e .

# Runtime stage
FROM python:3.11-slim

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY freefeed_mcp_server/ freefeed_mcp_server/

# Health check (check HTTP port)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import socket; socket.create_connection(('localhost', 8000), timeout=5)" || exit 1

# Default environment variables
ENV PYTHONUNBUFFERED=1 \
    FREEFEED_BASE_URL=https://freefeed.net \
    FREEFEED_API_VERSION=4 \
    FREEFEED_API_MODE=1 \
    FREEFEED_API_HOST=0.0.0.0 \
    FREEFEED_API_PORT=8000

# Run the API server
CMD ["python", "-m", "freefeed_mcp_server"]
