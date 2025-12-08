# NodeRAG with Neo4j Custom Storage

**Graph-based Retrieval-Augmented Generation (RAG) with Neo4j optimization for intelligent document search and question answering.**

This is a customized version of [NodeRAG](https://github.com/Terry-Xu-666/NodeRAG) that replaces in-memory graph storage with **Neo4j-native operations**, delivering memory reduction and faster queries for production workloads.

---

## 🎯 What's New: Neo4j Custom Storage

### Original NodeRAG Architecture
```
Documents → Embedding → Graph Construction → pickle file (2-5GB)
                                              ↓
Query → Load graph.pkl to RAM → NetworkX operations → LLM → Answer
        (2-5GB memory)
```

### Custom Neo4j-Optimized Architecture
```
Documents → Embedding → Graph Construction → Neo4j Database
                                              ↓
Query → Direct Cypher queries (no loading) → LLM → Answer
        (~100MB memory)
```

### Technical Implementation

**Custom Storage Backend** (`neo4j_native_search.py`):
- **Neo4jNativeSearch Class**: Direct Cypher query interface for graph operations
- **Method Patching**: Replaces 4 core NodeRAG methods to bypass pickle loading
- **Batch Operations**: Single queries fetch all node properties (vs Python loops)
- **Native PageRank**: Graph traversal executed in Neo4j (vs NetworkX in memory)

**Modified Pipeline**:
1. **Graph Construction** (one-time): Store nodes/relationships in Neo4j via `migrate_to_neo4j.py`
2. **Query Processing**: Direct Cypher queries for neighbor expansion and ranking
3. **Hybrid Storage**: Graph structure in Neo4j + vectors in HNSW + text in Parquet

---

## 📊 Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         INPUT LAYER                              │
├─────────────────────────────────────────────────────────────────┤
│  Documents (resumes, job descriptions)                           │
│  → POC_Data/documents/input/*.txt                               │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                     PROCESSING LAYER                             │
├─────────────────────────────────────────────────────────────────┤
│  1. Text Chunking (1048 tokens)                                 │
│  2. Embedding Generation (Gemini text-embedding-004)            │
│  3. Graph Construction (Entity/Relationship/Hierarchy nodes)    │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                      STORAGE LAYER                               │
│                    (HYBRID APPROACH)                             │
├─────────────────────────────────────────────────────────────────┤
│  [Neo4j Database]          [HNSW Index]      [Parquet Files]   │
│   Graph Structure           Vector Search      Full Text        │
│   • Nodes (id, type)        • Embeddings       • Complete       │
│   • Relationships           • Fast k-NN          content        │
│   • Properties              • ~10-50ms          • Metadata      │
│   • Cypher queries                                              │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                       QUERY LAYER                                │
├─────────────────────────────────────────────────────────────────┤
│  User Query: "What skills does candidate X have?"               │
│                                                                  │
│  Step 1: Vector Similarity (HNSW)                               │
│   └─→ Find top-k relevant nodes by embedding distance           │
│                                                                  │
│  Step 2: Graph Expansion (Neo4j Cypher) ← CUSTOM OPTIMIZATION   │
│   └─→ MATCH (seed)-[:CONNECTED*1..2]-(neighbor)                │
│   └─→ PageRank-style relevance scoring                          │
│   └─→ Batch property retrieval                                  │
│                                                                  │
│  Step 3: Context Assembly                                       │
│   └─→ Fetch full text from Parquet files                        │
│   └─→ Build structured prompt with entity/relationship context  │
│                                                                  │
│  Step 4: LLM Generation (Gemini)                                │
│   └─→ Generate natural language answer                          │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 ▼
           Final Answer
```

---

## 🚀 First-Time Setup

### Prerequisites
- Python 3.8+
- Docker (for Neo4j)
- Gemini API key ([Get one here](https://aistudio.google.com/app/apikey))

### Step 1: Clone and Install

```bash
git clone https://github.com/MennaT-T/NodeRAG-Neo4j-Integration.git
cd NodeRAG-Neo4j-Integration

# Create virtual environment
python -m venv venv

# Activate (Windows PowerShell)
.\venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt
```

### Step 2: Add Your Input Data

Place your documents in the input folder:

```
POC_Data/documents/input/
├── resume_1.txt          # Candidate resumes
├── resume_2.txt
├── job_description_1.txt # Job requirements
└── job_description_2.txt
```

**Format**: Plain text files with `.txt` extension. Names can include metadata (e.g., `resume_123_Python_Developer.txt`).

### Step 3: Configure API Keys

```bash
# Copy template
cp Node_config.yaml.example POC_Data/documents/Node_config.yaml

# Edit the file and add your keys
```

**Edit `POC_Data/documents/Node_config.yaml`:**

```yaml
# AI Model Configuration
model_config:
  service_provider: gemini
  api_keys: YOUR_GEMINI_API_KEY_HERE  # ← Add your key
  model_name: gemini-2.5-flash
  temperature: 0
  max_tokens: 10000

# Embedding Configuration
embedding_config:
  service_provider: gemini_embedding
  api_keys: YOUR_GEMINI_API_KEY_HERE  # ← Same key
  embedding_model_name: text-embedding-004

# Neo4j Configuration
config:
  neo4j_uri: 'bolt://localhost:7687'
  neo4j_user: 'neo4j'
  neo4j_password: 'autoapply123'     # ← Change if needed
  
  # Search parameters (defaults work well)
  chunk_size: 1048
  cross_node: 10
  Enode: 10
  Rnode: 30
  Hnode: 10
```

### Step 4: Start Neo4j

```bash
# Run Neo4j in Docker
docker run -d \
  --name neo4j-noderag \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/autoapply123 \
  neo4j:latest

# Verify it's running (wait ~30 seconds for startup)
docker ps
```

**Access Neo4j Browser**: http://localhost:7474 (optional, for visualization)

### Step 5: Build the Graph

```bash
# First, build the graph from documents
python -m NodeRAG.build -f "POC_Data\documents"
```

This will:
1. Read all files from `POC_Data/documents/input/`
2. Generate embeddings using Gemini
3. Build graph structure (entities, relationships, hierarchy)
4. Create HNSW index for vector search
5. Save to pickle file and parquet files

**Expected output:**
```
✓ Loading documents...
✓ Generating embeddings...
✓ Building graph...
✓ Saving graph to cache/
```

### Step 6: Migrate to Neo4j

```bash
# Migrate the built graph to Neo4j database
python utils/migrate_to_neo4j.py
```

This will:
1. Load the graph from pickle file
2. Create nodes in Neo4j with properties
3. Create relationships between nodes
4. Create indexes for fast lookups

**Expected output:**
```
✓ Config loaded
✓ Loading graph from pickle...
✓ Migrating to Neo4j...
✓ Successfully migrated X nodes and Y relationships
```

### Step 7: Run Queries

**Option A: Command Line Interface**

```bash
python search_resumes.py
```

**Option B: Web Interface**

```bash
python -m NodeRAG.WebUI -f "POC_Data\documents"
# Open http://localhost:8501
```

---

## 💻 Usage Examples

### CLI Search

```python
from pathlib import Path
from NodeRAG import NodeConfig, NodeSearch
from neo4j_native_search import integrate_neo4j_search

# Load configuration
DOCUMENTS_FOLDER = Path("POC_Data/documents")
config = NodeConfig.from_main_folder(str(DOCUMENTS_FOLDER))

# Enable Neo4j optimization (required for performance gains)
integrate_neo4j_search(
    config,
    neo4j_uri=config.config.get('neo4j_uri'),
    neo4j_user=config.config.get('neo4j_user'),
    neo4j_password=config.config.get('neo4j_password')
)

# Initialize search engine
search = NodeSearch(config)

# Ask questions
result = search.answer("What programming languages does the candidate know?")
print(result.response)

result = search.answer("Find candidates with machine learning experience")
print(result.response)
```

### Batch Processing

```python
queries = [
    "What is the candidate's work experience?",
    "List all Python developers",
    "Who has experience with Neo4j?"
]

for query in queries:
    result = search.answer(query)
    print(f"\nQ: {query}")
    print(f"A: {result.response}")
```

---

## 📁 Project Structure

```
NodeRAG-Neo4j-Integration/
├── README.md                          # This file
├── requirements.txt                   # Python dependencies
├── Node_config.yaml.example          # Configuration template
│
├── neo4j_native_search.py            # ⭐ Custom Neo4j storage backend
├── search_resumes.py                 # CLI search interface
│
├── NodeRAG/                          # Core framework (customized)
│   ├── storage/
│   │   └── neo4j_storage.py          # Neo4j graph storage class
│   ├── search/                       # Search algorithms
│   ├── WebUI/                        # Streamlit interface
│   └── ...
│
├── utils/
│   ├── migrate_to_neo4j.py           # Graph migration tool
│   ├── test_neo4j_search.py          # Integration tests
│   └── visualize_graph.py            # Graph visualization
│
├── POC_Data/documents/
    ├── Node_config.yaml              # Your configuration (gitignored)
    ├── input/                        # ← ADD YOUR DATA HERE
    │   ├── resume_*.txt
    │   └── job_*.txt
    ├── cache/                        # Generated embeddings (auto-created)
    └── info/                         # Graph metadata (auto-created)

```

---

## 🔧 Configuration Reference

### Key Settings

| Parameter | Description | Default | Notes |
|-----------|-------------|---------|-------|
| `neo4j_uri` | Neo4j connection URL | `bolt://localhost:7687` | Required |
| `neo4j_user` | Database username | `neo4j` | Required |
| `neo4j_password` | Database password | `autoapply123` | Change in production |
| `chunk_size` | Text chunk size (tokens) | 1048 | Larger = more context |
| `Enode` | Entity nodes to retrieve | 10 | Increase for more entities |
| `Rnode` | Relationship nodes to retrieve | 30 | Core search parameter |
| `Hnode` | High-level nodes to retrieve | 10 | For hierarchical context |
| `HNSW_results` | Vector search results | 10 | Initial seeds for expansion |

### Security Notes

⚠️ **Never commit credentials to Git!**

- `Node_config.yaml` is gitignored by default
- Use `Node_config.yaml.example` for sharing templates
- In production, use environment variables:

```python
import os
config['neo4j_password'] = os.getenv('NEO4J_PASSWORD')
```

---

## 🧪 Testing & Validation

### Run Integration Tests

```bash
# Test Neo4j connection and search functionality
python utils/test_neo4j_search.py
```

**Expected output:**
```
✓ Config loaded
✓ Neo4j-native search enabled
✓ Search engine ready
✓ Query successful: Retrieved 26 nodes in 0.15s
```

### Visualize the Graph

```bash
# Generate interactive graph visualization
python utils/visualize_graph.py

# Open POC_Data/documents/index.html in browser
```

### Performance Benchmarking

```python
import time

start = time.time()
result = search.answer("Your query here")
elapsed = time.time() - start

print(f"Query time: {elapsed:.3f}s")
# Expected with Neo4j: 0.05-0.2s
# Without Neo4j: 1-5s
```

---

## 🐛 Troubleshooting

### Neo4j Connection Failed

**Error**: `Failed to establish connection to Neo4j`

**Solutions**:
1. Check if Docker container is running: `docker ps | findstr neo4j`
2. Restart container: `docker restart neo4j-noderag`
3. Verify credentials in `Node_config.yaml` match Docker settings
4. Check Neo4j logs: `docker logs neo4j-noderag`

### Graph is Empty

**Error**: `Neo4j database is empty!`

**Solution**: Run the migration script:
```bash
python utils/migrate_to_neo4j.py
```

### High Memory Usage

**Cause**: Neo4j optimization not activated before creating `NodeSearch` object

**Fix**: Ensure correct order in your code:
```python
config = NodeConfig.from_main_folder(str(DOCUMENTS_FOLDER))
integrate_neo4j_search(config, uri, user, password)  # Must be BEFORE NodeSearch
search = NodeSearch(config)  # Now uses Neo4j
```

### API Rate Limits

**Error**: `429 Resource Exhausted` (Gemini free tier)

**Solution**: Increase delays in `Node_config.yaml`:
```yaml
model_config:
  request_delay: 10  # Wait 10 seconds between requests
  
embedding_config:
  request_delay: 10
```

---

## 📖 Technical Details

### How Neo4j Integration Works

The `neo4j_native_search.py` module patches NodeRAG's core methods:

```python
# Original NodeRAG behavior
class NodeSearch:
    def load_graph(self):
        # Loads 2-5GB pickle file into memory
        with open(graph_pkl, 'rb') as f:
            self.G = pickle.load(f)
    
    def graph_search(self, seed_ids):
        # Python NetworkX operations (slow)
        neighbors = list(self.G.neighbors(node))

# After integrate_neo4j_search() patches
class NodeSearch:
    def load_graph(self):
        # Does nothing - graph stays in Neo4j
        pass
    
    def graph_search(self, seed_ids):
        # Direct Cypher queries (fast)
        result = session.run("""
            MATCH (seed)-[:CONNECTED*1..2]-(neighbor)
            WHERE seed.id IN $seed_ids
            RETURN neighbor
        """, seed_ids=seed_ids)
```

### Storage Layers

| Layer | Technology | Data Stored | Size |
|-------|-----------|-------------|------|
| **Graph** | Neo4j | Nodes, relationships, properties | ~50-100MB |
| **Vectors** | HNSW (hnswlib) | Embeddings for similarity search | ~500MB-1GB |
| **Text** | Parquet | Full document content | ~10-50MB |

---

## 🌟 Features

✅ **Hybrid Storage**: Graph in Neo4j + vectors in HNSW + text in Parquet  
✅ **Native Cypher Queries**: All graph operations in database  
✅ **Batch Property Retrieval**: Single query fetches all node data  
✅ **Streaming Responses**: Real-time LLM output in WebUI  
✅ **Configurable Search**: Adjust entity/relationship/hierarchy node counts  
✅ **Production Ready**: Clean code, comprehensive docs, secure config  

---

## 📄 License

This project is based on [NodeRAG](https://github.com/Terry-Xu-666/NodeRAG) with custom Neo4j storage optimization.

---

## 🙏 Acknowledgments

- **NodeRAG Team**: Original graph-RAG framework
- **Neo4j**: High-performance graph database
- **Google Gemini**: LLM and embedding models

---

**Questions?** Open an issue or check the [docs/](docs/) folder for detailed guides.

**Performance Issue?** Ensure you're calling `integrate_neo4j_search()` before `NodeSearch()` initialization.
