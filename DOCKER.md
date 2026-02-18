# Docker Support

## Quick Start

### 1. Build and run with Docker Compose (recommended)

```bash
# Create .env file with your credentials
cp .env.example .env
# Edit .env and add your FREEFEED_APP_TOKEN or FREEFEED_USERNAME/PASSWORD

# Start the server
docker-compose up -d

# View logs
docker-compose logs -f freefeed-mcp-server

# Stop the server
docker-compose down
```

### 2. Build and run with Docker directly

```bash
# Build the image
docker build -t freefeed-mcp-server .

# Run the container
docker run -d \
  -e FREEFEED_APP_TOKEN="your_app_token" \
  -e FREEFEED_BASE_URL="https://freefeed.net" \
  -e FREEFEED_API_VERSION="4" \
  -p 8000:8000 \
  --name freefeed-mcp-server \
  freefeed-mcp-server

# View logs
docker logs -f freefeed-mcp-server

# Stop the container
docker stop freefeed-mcp-server
```

## Environment Variables

Set these when running the container:

- `FREEFEED_BASE_URL` - FreeFeed API base URL (default: https://freefeed.net)
- `FREEFEED_API_VERSION` - API version (default: 4)
- `FREEFEED_APP_TOKEN` - Your app token (required if not using username/password)
- `FREEFEED_USERNAME` - Username (alternative to app token)
- `FREEFEED_PASSWORD` - Password (required with username)
- `FREEFEED_API_MODE` - Set to "1" to run REST API server (default: "1" in Docker)
- `FREEFEED_API_HOST` - API host (default: 0.0.0.0)
- `FREEFEED_API_PORT` - HTTP port (default: 8000)
- `FREEFEED_API_HTTPS_PORT` - HTTPS port (default: 8443)
- `FREEFEED_SSL_ENABLED` - Set to "1" or "true" to enable HTTPS (requires certificates)

## With docker-compose and .env

```bash
# .env file format
FREEFEED_APP_TOKEN=your_app_token_here
FREEFEED_BASE_URL=https://freefeed.net
FREEFEED_API_VERSION=4

# Optional: opt-out settings
FREEFEED_OPTOUT_ENABLED=false
FREEFEED_OPTOUT_TAGS=#noai,#opt-out-ai
FREEFEED_OPTOUT_RESPECT_PRIVATE=true
```

## SSL/TLS Support (Dual HTTP+HTTPS)

### Generate SSL Certificates

```bash
# Generate self-signed certificates
./generate_cert.sh

# Certificates will be created in ./certs/ directory
```

### Enable SSL in docker-compose

**Option 1: Using docker-compose.ssl.yml (recommended)**

```bash
# Generate certificates
./generate_cert.sh

# Start with SSL enabled
docker-compose -f docker-compose.yml -f docker-compose.ssl.yml up -d

# View logs
docker-compose logs -f freefeed-mcp-server
```

**Option 2: Set environment variable**

```bash
FREEFEED_SSL_ENABLED=1 docker-compose up -d
```

**Option 3: Edit docker-compose.yml**

Edit `docker-compose.yml` and set:
```yaml
environment:
  FREEFEED_SSL_ENABLED: "1"
```

### What happens when SSL is enabled:

- 🌐 **HTTP server** runs on port **8000**
- 🔐 **HTTPS server** runs on port **8443**
- Both servers are active simultaneously
- Both have the same API endpoints available

### Access the server:

```bash
# HTTP (development)
curl http://localhost:8000/docs

# HTTPS (production)
curl -k https://localhost:8443/docs  # -k to skip certificate validation

# Docker compose with SSL enabled
docker-compose up -d
docker-compose logs -f
```

## Health Check

The container includes a built-in health check that runs every 30 seconds. Check status:

```bash
docker ps --filter "name=freefeed-mcp-server"
```

## Persisting Logs

Logs are stored in `./logs` directory (mounted volume in docker-compose).

To view them:
```bash
tail -f logs/*.log
```

## Production Deployment

For production, consider:

1. **Use an .env file** with sensitive credentials (never commit it)
2. **Enable SSL/TLS** for security:
   ```bash
   ./generate_cert.sh
   docker-compose -f docker-compose.yml -f docker-compose.ssl.yml up -d
   ```
3. **Set `restart: always`** in docker-compose for automatic recovery
4. **Configure logging driver** for container logs
5. **Use a shared volume** for logs if needed
6. **Behind a reverse proxy** (nginx, caddy) for load balancing and additional security
7. **Environment-specific overrides:**

```yaml
# docker-compose.prod.yml - for production without SSL override
version: '3.8'
services:
  freefeed-mcp-server:
    build: .
    restart: always
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
    networks:
      - production-network

networks:
  production-network:
    external: true
```

Run production with SSL:
```bash
docker-compose -f docker-compose.yml -f docker-compose.prod.yml -f docker-compose.ssl.yml up -d
```
    restart: always
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
    networks:
      - production-network

networks:
  production-network:
    external: true
```

Run with: `docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d`

## Connecting from Other Docker Containers

### Option 1: Using External Shared Network (Recommended)

Create an external network that multiple docker-compose projects can share:

```bash
# 1. Create external network (one time only)
# Option A: Manual
docker network create freefeed-shared

# Option B: Using setup script
./setup-docker-network.sh

# 2. Start freefeed-mcp-server with external network
docker-compose -f docker-compose.yml -f docker-compose.external-network.yml up -d

# 3. Verify the network
docker network inspect freefeed-shared
```

Now other services can connect to this network and reach `freefeed-mcp-server` via DNS name:

```yaml
# Example: your-other-service/docker-compose.yml
version: '3.8'

services:
  my-client:
    image: my-client:latest
    networks:
      - freefeed-shared
    environment:
      FREEFEED_API_URL: http://freefeed-mcp-server:8000
      # or for HTTPS (if enabled):
      # FREEFEED_API_URL: https://freefeed-mcp-server:8443

networks:
  freefeed-shared:
    external: true
```

### Option 2: Using Docker Run with Network

```bash
# Start freefeed-mcp-server with external network
docker-compose -f docker-compose.yml -f docker-compose.external-network.yml up -d

# Run another container on the same network
docker run -it \
  --network freefeed-shared \
  --name my-client \
  my-image:latest \
  bash

# Inside the container, you can reach the server:
curl http://freefeed-mcp-server:8000/docs
```

### Option 3: Using Host Network (Development Only)

For local development, connect via host IP:

```bash
# Get host IP (from inside container perspective)
docker inspect -f '{{range .NetworkSettings.Networks}}{{.Gateway}}{{end}}' freefeed-mcp-server

# Then connect using that IP from another container
curl http://172.17.0.1:8000/docs
```

### Service Discovery via DNS

When using the same Docker network, the service name becomes available as DNS:

- **Service name**: `freefeed-mcp-server` (from container_name in docker-compose.yml)
- **HTTP endpoint**: `http://freefeed-mcp-server:8000`
- **HTTPS endpoint**: `https://freefeed-mcp-server:8443` (if SSL enabled)
- **API docs**: `http://freefeed-mcp-server:8000/docs`

Example from inside another container:

```bash
curl http://freefeed-mcp-server:8000/users/me
curl http://freefeed-mcp-server:8000/timeline
```

### See Also

- [docker-compose.external-network.yml](docker-compose.external-network.yml) - Override for using external network
- [docker-compose.example-client.yml](docker-compose.example-client.yml) - Example client configuration
- [NETWORKS.md](NETWORKS.md) - Detailed guide on multiple networks configuration
