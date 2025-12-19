# NodeRAG Docker Deployment Guide

## Quick Start

### 1. Setup Environment Variables

```bash
# Copy example env file
cp .env.example .env

# Edit .env with your API keys
nano .env  # or use any text editor
```

**Required in `.env`:**
```env
NEO4J_PASSWORD=your-secure-password
GOOGLE_API_KEY=your-google-api-key
# OR
OPENAI_API_KEY=your-openai-api-key
```

### 2. Build and Run

```bash
# Build and start all services
docker-compose up -d --build

# View logs
docker-compose logs -f

# Check status
docker-compose ps
```

### 3. Access Services

| Service | URL | Description |
|---------|-----|-------------|
| **API** | http://localhost:8000 | NodeRAG REST API |
| **API Docs** | http://localhost:8000/docs | Swagger UI |
| **Neo4j Browser** | http://localhost:7474 | Neo4j Web Interface |

## Docker Commands

### Basic Operations

```bash
# Start services
docker-compose up -d

# Stop services
docker-compose down

# Restart services
docker-compose restart

# View logs
docker-compose logs -f api      # API logs only
docker-compose logs -f neo4j    # Neo4j logs only

# Check health
docker-compose ps
curl http://localhost:8000/health
```

### Building

```bash
# Build with no cache (fresh build)
docker-compose build --no-cache

# Build specific service
docker-compose build api

# Pull latest base images
docker-compose pull
```

### Data Management

```bash
# Backup Neo4j data
docker run --rm -v noderag-neo4j-integration_neo4j_data:/data -v $(pwd)/backup:/backup alpine tar czf /backup/neo4j-backup.tar.gz /data

# View volumes
docker volume ls | grep noderag

# Remove all data (WARNING: destructive!)
docker-compose down -v
```

## Build the Image for Deployment

### Option 1: Build Locally and Push to Registry

```bash
# Build the image
docker build -t noderag-api:latest .

# Tag for your registry
docker tag noderag-api:latest your-registry.com/noderag-api:latest

# Push to registry
docker push your-registry.com/noderag-api:latest
```

### Option 2: Build for Multiple Architectures

```bash
# Create builder (one-time)
docker buildx create --name multiarch --use

# Build for amd64 and arm64
docker buildx build --platform linux/amd64,linux/arm64 \
  -t your-registry.com/noderag-api:latest \
  --push .
```

## Production Deployment

### Using Docker Compose (Simple)

```bash
# On your production server
git clone <your-repo>
cd NodeRAG-Neo4j-Integration

# Setup environment
cp .env.example .env
nano .env  # Add production credentials

# Start with production settings
docker-compose -f docker-compose.yml up -d
```

### Using Docker Swarm

```bash
# Initialize swarm (one-time)
docker swarm init

# Deploy stack
docker stack deploy -c docker-compose.yml noderag
```

### Using Kubernetes

See `k8s/` directory for Kubernetes manifests (if available).

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `NEO4J_URI` | Neo4j connection URI | `bolt://neo4j:7687` |
| `NEO4J_USER` | Neo4j username | `neo4j` |
| `NEO4J_PASSWORD` | Neo4j password | `noderag123` |
| `OPENAI_API_KEY` | OpenAI API key | - |
| `GOOGLE_API_KEY` | Google AI API key | - |
| `API_HOST` | API bind host | `0.0.0.0` |
| `API_PORT` | API port | `8000` |
| `LOG_LEVEL` | Logging level | `info` |

### Mounting Your Data

The `POC_Data` directory is mounted as a volume. Place your documents in:
```
POC_Data/documents/input/
```

### Custom Configuration

Mount a custom config file:
```yaml
volumes:
  - ./my-config.yaml:/app/POC_Data/documents/Node_config.yaml:ro
```

## Troubleshooting

### API won't start

```bash
# Check logs
docker-compose logs api

# Common issues:
# 1. Neo4j not ready - wait for healthcheck
# 2. Missing API keys - check .env file
# 3. Port conflict - change port in docker-compose.yml
```

### Neo4j connection failed

```bash
# Check Neo4j is running
docker-compose ps neo4j

# Check Neo4j logs
docker-compose logs neo4j

# Test connection from API container
docker-compose exec api curl -v http://neo4j:7474
```

### Out of memory

Adjust Neo4j memory in `docker-compose.yml`:
```yaml
environment:
  - NEO4J_dbms_memory_heap_max__size=2G
  - NEO4J_dbms_memory_pagecache_size=1G
```

### Reset everything

```bash
# Stop and remove containers, networks, volumes
docker-compose down -v

# Remove built images
docker-compose down --rmi all

# Fresh start
docker-compose up -d --build
```

## Resource Requirements

### Minimum (Development)
- CPU: 2 cores
- RAM: 4GB
- Disk: 10GB

### Recommended (Production)
- CPU: 4+ cores
- RAM: 8GB+
- Disk: 50GB+ SSD

## Security Notes

1. **Never commit `.env` file** - it's in `.gitignore`
2. **Change default Neo4j password** in production
3. **Use HTTPS** in production (add reverse proxy like Nginx/Traefik)
4. **Restrict network access** - use firewall rules
5. **Regular backups** - backup Neo4j data volume

## Architecture

```
┌─────────────────────────────────────────────────┐
│                   Docker Host                    │
│                                                  │
│  ┌──────────────┐      ┌──────────────────────┐ │
│  │   NodeRAG    │      │       Neo4j          │ │
│  │     API      │─────▶│     Database         │ │
│  │  :8000       │ bolt │  :7474 (HTTP)        │ │
│  └──────────────┘      │  :7687 (Bolt)        │ │
│         │              └──────────────────────┘ │
│         │                        │              │
│  ┌──────▼──────┐         ┌──────▼──────┐       │
│  │  POC_Data   │         │  neo4j_data │       │
│  │  (volume)   │         │  (volume)   │       │
│  └─────────────┘         └─────────────┘       │
└─────────────────────────────────────────────────┘
```
