#!/bin/bash
# ============================================================================
# NodeRAG Setup Script for Teammates (Linux/Mac)
# ============================================================================

echo ""
echo "============================================"
echo "  NodeRAG API Setup"
echo "============================================"
echo ""

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "Creating .env file from template..."
    cp .env.example .env
    echo ""
    echo "[IMPORTANT] Please edit .env file and add your API keys!"
    echo "  - GOOGLE_API_KEY=your-key-here"
    echo "  - or OPENAI_API_KEY=your-key-here"
    echo ""
    echo "Press Enter after editing .env..."
    read
fi

# Pull and start containers
echo ""
echo "Starting NodeRAG services..."
docker-compose -f docker-compose.prod.yml up -d

echo ""
echo "============================================"
echo "  Setup Complete!"
echo "============================================"
echo ""
echo "  API:          http://localhost:8000"
echo "  API Docs:     http://localhost:8000/docs"
echo "  Neo4j:        http://localhost:7474"
echo ""
echo "  Commands:"
echo "    View logs:  docker-compose -f docker-compose.prod.yml logs -f"
echo "    Stop:       docker-compose -f docker-compose.prod.yml down"
echo ""
