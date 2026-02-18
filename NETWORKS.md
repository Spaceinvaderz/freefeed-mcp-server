# Multiple Networks Configuration Examples

## Scenario 1: Only Internal Network (Default)
# Use the default docker-compose.yml
# The service is isolated to its own network

```bash
docker-compose up -d
# Only connections from host via published ports are allowed (8000, 8443)
```

## Scenario 2: Internal + External Shared Network (Recommended)
# Connect to both networks: internal (freefeed-network) and external (freefeed-shared)
# This allows other docker-compose projects to reach the service

```bash
# 1. Create external network (one time only)
docker network create freefeed-shared

# 2. Start service connected to both networks
docker-compose -f docker-compose.yml -f docker-compose.external-network.yml up -d

# Now you can reach it:
# - From internal: http://freefeed-mcp-server:8000 (within freefeed-network)
# - From external: http://freefeed-mcp-server:8000 (from freefeed-shared network)
```

## Scenario 3: Only External Shared Network
# Skip internal network, connect only to external shared network

```bash
# Use this override file (or create one)
docker-compose -f docker-compose.yml -f docker-compose.shared-only.yml up -d
```

Here's an example docker-compose.shared-only.yml:

```yaml
version: '3.8'

services:
  freefeed-mcp-server:
    networks:
      - freefeed-shared  # Only external network

networks:
  freefeed-network:
    driver: bridge
  freefeed-shared:
    external: true
```

## Network Configuration in docker-compose.yml

The current setup supports all scenarios:

```yaml
networks:
  freefeed-network:           # Internal network (created by compose)
    driver: bridge
  freefeed-shared:            # External network (must exist already)
    external: true
    # name: freefeed-shared   # Uncomment if network name differs
```

## Using Multiple Networks with Services

```yaml
services:
  freefeed-mcp-server:
    networks:
      - freefeed-network      # Connect to internal network

# To add external network, use override:
# docker-compose -f docker-compose.yml -f docker-compose.external-network.yml up -d
```

## Accessing Service from Different Networks

From within the same network, use DNS name of the service:
```
http://freefeed-mcp-server:8000
```

From host machine, use published ports:
```
http://localhost:8000
```

From another docker container NOT on the network:
```
Use host IP: http://172.17.0.1:8000 (default Docker gateway)
```

## Common Use Cases

### 1. Development Only
```bash
docker-compose up -d
# Access via localhost:8000
```

### 2. Local Microservices
```bash
# Create shared network
docker network create freefeed-shared

# Start all services on the shared network
docker-compose -f docker-compose.yml -f docker-compose.external-network.yml up -d
# Other services on the same network can reach freefeed-mcp-server:8000
```

### 3. Production with Multiple Compose Files
```bash
# Service 1: freefeed-mcp-server
docker-compose -f docker-compose.yml -f docker-compose.external-network.yml up -d

# Service 2: your-app
cd ../your-app
docker-compose up -d  # (has freefeed-shared in its networks)
```
