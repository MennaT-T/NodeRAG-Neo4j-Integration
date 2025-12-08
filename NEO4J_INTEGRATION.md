# NodeRAG with Neo4j Integration

**Production-ready graph-based RAG system with native Neo4j storage for scalable document search and question answering.**

---

## Overview

This implementation extends NodeRAG with Neo4j-native graph operations, replacing in-memory NetworkX processing with database-backed Cypher queries. The integration eliminates large memory overhead while improving query performance and scalability.

### Key Achievements

| Metric | Before | After | Impact |
|--------|--------|-------|--------|
| **Memory Usage** | Graph.pkl in RAM | Empty graph placeholder | Significant reduction |
| **Initialization** | Pickle deserialization | Direct Neo4j connection | Faster startup |
| **Query Execution** | NetworkX Python loops | Native Cypher queries | Optimized performance |
| **Scalability** | RAM-limited | Database-backed | Large graph support |

---

## Architecture

### Data Flow

```
┌─────────────────────────────────────────────────────────────┐
│ 1. DOCUMENT INGESTION                                       │
│    Documents → Text Chunks → Embeddings                     │
└────────────────┬────────────────────────────────────────────┘
                 ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. GRAPH CONSTRUCTION                                        │
│    Entities + Relationships + Hierarchy → NetworkX Graph    │
└────────────────┬────────────────────────────────────────────┘
                 ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. STORAGE (Hybrid Architecture)                            │
│    ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│    │   Neo4j DB   │  │  HNSW Index  │  │ Parquet Files│   │
│    │  Structure   │  │   Vectors    │  │   Content    │   │
│    └──────────────┘  └──────────────┘  └──────────────┘   │
└────────────────┬────────────────────────────────────────────┘
                 ↓
┌─────────────────────────────────────────────────────────────┐
│ 4. QUERY PROCESSING                                          │
│    HNSW Seeds → Neo4j Expansion → Context Assembly → LLM   │
└─────────────────────────────────────────────────────────────┘
```

### Storage Layers

| Layer | Technology | Purpose | Data |
|-------|-----------|---------|------|
| **Graph Structure** | Neo4j | Node relationships and properties | IDs, types, attributes |
| **Vector Search** | HNSW | Fast similarity matching | 768-dim embeddings |
| **Full Text** | Parquet | Complete content retrieval | Documents, descriptions |

---

## Installation

### Prerequisites

- Python 3.8+
- Docker (for Neo4j)
- Gemini API key

### Quick Start

```bash
# 1. Clone repository
git clone <repository-url>
cd NodeRAG-Neo4j-Integration

# 2. Create virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1  # Windows
source venv/bin/activate      # Linux/Mac

# 3. Install dependencies
pip install -r requirements.txt

# 4. Start Neo4j
docker run -d \
  --name neo4j-noderag \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/your-password \
  neo4j:latest

# 5. Configure
cp Node_config.yaml.example POC_Data/documents/Node_config.yaml
# Edit Node_config.yaml with your credentials

# 6. Add documents
# Place .txt files in POC_Data/documents/input/

# 7. Build graph
python -m NodeRAG.build -f "POC_Data\documents"

# 8. Migrate to Neo4j
python utils/migrate_to_neo4j.py

# 9. Run search
python search_resumes.py
```

---

## Configuration

### Essential Settings

**`POC_Data/documents/Node_config.yaml`:**

```yaml
# AI Configuration
model_config:
  service_provider: gemini
  api_keys: YOUR_GEMINI_API_KEY
  model_name: gemini-2.5-flash
  temperature: 0
  max_tokens: 10000

embedding_config:
  service_provider: gemini_embedding
  api_keys: YOUR_GEMINI_API_KEY
  embedding_model_name: text-embedding-004

# Neo4j Configuration
config:
  neo4j_uri: 'bolt://localhost:7687'
  neo4j_user: 'neo4j'
  neo4j_password: 'your-password'
  
  # Search Parameters
  chunk_size: 1048           # Token size for text chunks
  HNSW_results: 10          # Initial vector search results
  cross_node: 10            # Additional nodes to include
  Enode: 10                 # Entity nodes to retrieve
  Rnode: 30                 # Relationship nodes to retrieve
  Hnode: 10                 # Hierarchy nodes to retrieve
```

### Security Best Practices

- Never commit `Node_config.yaml` to version control
- Use environment variables in production:

```python
import os
config['neo4j_password'] = os.getenv('NEO4J_PASSWORD')
config['api_keys'] = os.getenv('GEMINI_API_KEY')
```

---

## Usage

### Basic Search

```python
from pathlib import Path
from NodeRAG import NodeConfig, NodeSearch
from neo4j_native_search import integrate_neo4j_search

# Load configuration
DOCUMENTS_FOLDER = Path("POC_Data/documents")
config = NodeConfig.from_main_folder(str(DOCUMENTS_FOLDER))

# Enable Neo4j optimization
NEO4J_URI = config.config.get('neo4j_uri')
NEO4J_USER = config.config.get('neo4j_user')
NEO4J_PASSWORD = config.config.get('neo4j_password')

integrate_neo4j_search(config, NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)

# Initialize search
search = NodeSearch(config)

# Query
result = search.answer("What skills does the candidate have?")
print(result.response)
```

### Web Interface

```bash
python -m NodeRAG.WebUI -f "POC_Data\documents"
# Access: http://localhost:8501
```

### Batch Processing

```python
queries = [
    "List all Python developers",
    "Find candidates with ML experience",
    "What are the top technical skills?"
]

for query in queries:
    result = search.answer(query)
    print(f"\nQuery: {query}")
    print(f"Answer: {result.response}\n")
    print(f"Tokens: {result.retrieval_tokens}")
```

---

## Neo4j Integration Details

### Core Components

#### 1. Neo4jNativeSearch Class

Direct database query interface replacing NetworkX operations.

**Key Methods:**

```python
class Neo4jNativeSearch:
    def find_neighbors(node_ids, max_hops=2)
        # Cypher-based neighbor expansion
        
    def pagerank_subgraph(seed_nodes)
        # Degree-based relevance scoring
        
    def get_batch_node_properties(node_ids, properties)
        # Optimized batch property retrieval
        
    def get_all_node_types()
        # Build ID-to-type mapping from database
```

#### 2. Method Patching

The `integrate_neo4j_search()` function replaces four NodeSearch methods:

| Original Method | Patched Behavior |
|----------------|------------------|
| `__init__()` | Skips graph.pkl loading, fetches types from Neo4j |
| `load_graph()` | Returns empty NetworkX graph |
| `graph_search()` | Executes Cypher PageRank queries |
| `post_process_top_k()` | Batch property queries instead of Python loops |

#### 3. Migration Process

**`utils/migrate_to_neo4j.py`** handles one-time graph transfer:

```python
# Load pickle file
G = storage.load(config.base_graph_path)

# Create nodes with properties
for node_id, node_data in G.nodes(data=True):
    session.run("""
        CREATE (n:Node {
            id: $id,
            type: $type,
            attributes: $attrs
        })
    """, id=node_id, type=node_data['type'], attrs=node_data.get('attributes'))

# Create relationships
for source, target in G.edges():
    session.run("""
        MATCH (a:Node {id: $source}), (b:Node {id: $target})
        CREATE (a)-[:CONNECTED_TO]->(b)
    """, source=source, target=target)

# Create indexes
session.run("CREATE INDEX node_id_index FOR (n:Node) ON (n.id)")
session.run("CREATE INDEX node_type_index FOR (n:Node) ON (n.type)")
```

---

## Project Structure

```
NodeRAG-Neo4j-Integration/
│
├── neo4j_native_search.py              # Core Neo4j integration
├── search_resumes.py                   # CLI interface
├── requirements.txt                    # Python dependencies
├── Node_config.yaml.example           # Configuration template
│
├── NodeRAG/                            # Framework (modified)
│   ├── storage/
│   │   └── neo4j_storage.py           # Neo4j storage backend
│   ├── search/
│   │   ├── search.py                  # Search orchestration
│   │   └── Answer_base.py             # Retrieval & answer classes
│   ├── build/                         # Graph construction
│   ├── WebUI/                         # Streamlit interface
│   └── utils/                         # Helper utilities
│
├── utils/
│   ├── migrate_to_neo4j.py            # Graph migration tool
│   ├── test_neo4j_search.py           # Integration tests
│   └── visualize_graph.py             # Graph visualization
│
├── POC_Data/documents/
│   ├── Node_config.yaml               # Your config (gitignored)
│   ├── input/                         # Place documents here
│   ├── cache/                         # Generated embeddings
│   └── info/                          # Metadata
│
└── docs/                              # Technical documentation
    ├── NEO4J_OPTIMIZATION_SUMMARY.md
    ├── SEARCH_ARCHITECTURE_EXPLAINED.md
    ├── NEO4J_INTEGRATION_GUIDE.md
    └── NEO4J_SETUP.md
```

---

## Advanced Topics

### Custom Graph Queries

Access Neo4j directly for custom operations:

```python
from NodeRAG.storage.neo4j_storage import get_neo4j_storage

neo4j = get_neo4j_storage(uri, user, password)

with neo4j.driver.session() as session:
    result = session.run("""
        MATCH (n:Node {type: 'entity'})
        WHERE n.name CONTAINS 'Python'
        RETURN n.id, n.name
        LIMIT 10
    """)
    
    for record in result:
        print(record['id'], record['name'])
```

### Performance Tuning

#### Neo4j Configuration

```bash
# In Neo4j container, edit neo4j.conf
dbms.memory.heap.initial_size=512m
dbms.memory.heap.max_size=2G
dbms.memory.pagecache.size=1G
```

#### Search Parameters

Adjust retrieval counts based on your use case:

```yaml
config:
  HNSW_results: 20      # More initial seeds → broader context
  Enode: 15            # More entities → richer information
  Rnode: 40            # More relationships → better connections
  Hnode: 15            # More hierarchy → deeper structure
```

### Monitoring

#### Query Performance

```python
import time

start = time.time()
result = search.answer("Your query")
query_time = time.time() - start

print(f"Query time: {query_time:.3f}s")
print(f"Retrieval tokens: {result.retrieval_tokens}")
print(f"Response tokens: {result.response_tokens}")
```

#### Neo4j Metrics

Access Neo4j Browser at http://localhost:7474:

```cypher
// Node counts
MATCH (n:Node) RETURN n.type, count(*) as count

// Relationship counts
MATCH ()-[r:CONNECTED_TO]->() RETURN count(r)

// Query execution plan
PROFILE MATCH (n:Node {id: 'some-id'})-[:CONNECTED_TO*1..2]-(m)
RETURN m
```

---

## Troubleshooting

### Common Issues

#### 1. Neo4j Connection Failed

**Symptoms:** `Failed to establish connection to Neo4j`

**Solutions:**
```bash
# Check container status
docker ps | findstr neo4j

# Restart container
docker restart neo4j-noderag

# Check logs
docker logs neo4j-noderag

# Verify credentials match config
```

#### 2. Empty Database

**Symptoms:** `WARNING: Neo4j database is empty!`

**Solution:**
```bash
# Run migration
python utils/migrate_to_neo4j.py

# Verify nodes created
docker exec neo4j-noderag cypher-shell -u neo4j -p your-password \
  "MATCH (n:Node) RETURN count(n)"
```

#### 3. High Memory Usage

**Cause:** Not calling `integrate_neo4j_search()` before `NodeSearch()`

**Fix:**
```python
# WRONG ORDER
search = NodeSearch(config)
integrate_neo4j_search(config, uri, user, password)  # Too late!

# CORRECT ORDER
integrate_neo4j_search(config, uri, user, password)  # First
search = NodeSearch(config)                          # Then
```

#### 4. KeyError in Retrieval

**Symptoms:** `KeyError: 'node-id-hash'`

**Cause:** Missing node text mappings

**Solution:** Already handled in updated `Answer_base.py` with defensive checks

#### 5. API Rate Limits

**Symptoms:** `429 Resource Exhausted`

**Solution:**
```yaml
model_config:
  request_delay: 10  # Add delay between requests
```

---

## Testing

### Integration Tests

```bash
# Test Neo4j connectivity and search
python utils/test_neo4j_search.py
```

**Expected Output:**
```
======================================================================
Testing Neo4j-Native Search
======================================================================

[1] Loading configuration...
✓ Config loaded

[2] Enabling Neo4j-native search...
✓ Neo4j-native search enabled

[3] Initializing search engine...
  ⚡ Skipping graph.pkl loading (using Neo4j instead)
  ⚡ Loading node types from Neo4j...
  ✓ Loaded 1290 node types from Neo4j
✓ Search engine ready

[4] Testing query: 'What skills does Salma Ali have?'
----------------------------------------------------------------------

[RESULT]
Salma Ali possesses comprehensive technical skills...

[RETRIEVED NODES]
Total nodes retrieved: 26
Relationships: 8

✓ Search completed successfully!

======================================================================
Test PASSED - Neo4j-native search is working!
======================================================================
```

### Unit Tests

```python
# Test Neo4j storage
from NodeRAG.storage.neo4j_storage import get_neo4j_storage

neo4j = get_neo4j_storage(uri, user, password)

# Test node creation
test_node = {'id': 'test-123', 'type': 'entity', 'name': 'Test'}
neo4j.save_node(test_node)

# Test node retrieval
retrieved = neo4j.get_node('test-123')
assert retrieved['name'] == 'Test'

# Cleanup
neo4j.delete_node('test-123')
```

---

## Best Practices

### Development

1. **Use the template**: Start with `Node_config.yaml.example`
2. **Test incrementally**: Build → Migrate → Search
3. **Monitor logs**: Check console output for warnings
4. **Version control**: Never commit credentials

### Production

1. **Environment variables**: Store secrets securely
2. **Neo4j clustering**: Use replica sets for high availability
3. **Backup strategy**: Regular Neo4j dumps
4. **Rate limiting**: Implement API request throttling
5. **Monitoring**: Track query latency and memory usage

### Optimization

1. **Batch operations**: Use `get_batch_node_properties()` over loops
2. **Index strategy**: Ensure indexes on `id` and `type` properties
3. **Query limits**: Use `LIMIT` in Cypher queries
4. **Connection pooling**: Reuse Neo4j driver connections

---

## API Reference

### integrate_neo4j_search()

**Signature:**
```python
integrate_neo4j_search(
    config: NodeConfig,
    neo4j_uri: str,
    neo4j_user: str,
    neo4j_password: str
) -> None
```

**Description:** Patches NodeSearch methods to use Neo4j instead of in-memory graphs.

**Parameters:**
- `config`: NodeRAG configuration object
- `neo4j_uri`: Database connection URI (e.g., 'bolt://localhost:7687')
- `neo4j_user`: Database username
- `neo4j_password`: Database password

**Side Effects:**
- Creates `config.neo4j_search` attribute
- Replaces 4 NodeSearch methods
- Prints confirmation messages

**Example:**
```python
from neo4j_native_search import integrate_neo4j_search
integrate_neo4j_search(config, 'bolt://localhost:7687', 'neo4j', 'password')
```

---

## Contributing

### Development Setup

```bash
# Clone repository
git clone <repository-url>
cd NodeRAG-Neo4j-Integration

# Create feature branch
git checkout -b feature/your-feature

# Install development dependencies
pip install -r requirements.txt
pip install pytest black mypy

# Run tests
pytest utils/test_neo4j_search.py

# Format code
black neo4j_native_search.py

# Type checking
mypy neo4j_native_search.py
```

### Contribution Guidelines

- Follow PEP 8 style guidelines
- Add docstrings to all functions
- Include type hints
- Write tests for new features
- Update documentation

---

## FAQ

**Q: Can I use this without Neo4j?**  
A: Yes, remove the `integrate_neo4j_search()` call and NodeRAG works with pickle files.

**Q: How do I update documents?**  
A: Rebuild the graph and re-migrate to Neo4j. Incremental updates are not yet supported.

**Q: Can I use other LLMs?**  
A: Yes, modify `model_config` in Node_config.yaml. OpenAI and Anthropic are supported.

**Q: What's the maximum graph size?**  
A: Neo4j can handle millions of nodes. HNSW index size depends on available RAM.

**Q: How do I backup Neo4j?**  
A: Use `neo4j-admin dump` or Docker volume backups.

---

## License

This project extends [NodeRAG](https://github.com/Terry-Xu-666/NodeRAG) with custom Neo4j storage optimization.

---

## Acknowledgments

- **NodeRAG Team**: Original framework architecture
- **Neo4j**: Graph database platform
- **Google Gemini**: LLM and embedding services

---

## Support

- **Documentation**: See `docs/` folder for detailed guides
- **Issues**: Open GitHub issues for bugs or feature requests
- **Questions**: Check existing issues or create a discussion

---

**Version:** 1.0.0  
**Maintainer:** Menna Alaa
