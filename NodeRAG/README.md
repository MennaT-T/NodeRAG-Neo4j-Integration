# Customized NodeRAG Source Code

This directory contains our customized version of NodeRAG v0.1.0 with Neo4j integration enhancements.

## 🔧 What's Been Customized

### 1. **Neo4j Storage Module** (`storage/neo4j_storage.py`)
**Changes:**
- Added Neo4j driver integration
- Implemented batch processing for efficient node/edge storage
- Added connection pooling and error handling
- Created JSON serialization for complex node properties

**Why:** Enable Neo4j as an alternative to pickle files for graph storage.

---

### 2. **Graph Pipeline** (`build/graph_pipeline.py`)
**Changes:**
- Modified `save_graph()` to support Neo4j storage option
- Added `use_neo4j_storage` flag in config
- Implemented fallback to pickle if Neo4j connection fails
- Added optional backup to both Neo4j and pickle

**Why:** Allow seamless switching between storage backends.

---

### 3. **Configuration** (`config/`)
**Changes:**
- Added Neo4j connection parameters (uri, user, password)
- Added `use_neo4j_storage` boolean flag
- Maintained backward compatibility with pickle-only setups

**Why:** Make Neo4j integration optional and configurable.

---

## 📦 Installation

From the project root:
```powershell
pip install -e NodeRAG_Source/
```

This installs NodeRAG in "editable" mode, meaning any changes you make to this source code will be immediately reflected without reinstalling.

---

## 🔍 Key Files Modified

| File | Location | Purpose |
|------|----------|---------|
| `neo4j_storage.py` | `storage/` | Neo4j CRUD operations |
| `graph_pipeline.py` | `build/` | Graph building with Neo4j support |
| `config.yaml` | `config/` | Configuration schema |

---

## 🚀 How It Works

### Original NodeRAG Flow:
```
Build Graph → Save to graph.pkl → Load into NetworkX → Search
```

### Enhanced Neo4j Flow:
```
Build Graph → Save to Neo4j → Query directly with Cypher → Search
```

**Benefit:** No need to load 2-5GB graph.pkl into memory!

---

## 📝 Making Changes

If you need to modify NodeRAG source code:

1. **Edit files** in `NodeRAG_Source/`
2. **No reinstall needed** (editable mode)
3. **Test your changes**: `python utils/test_neo4j_search.py`
4. **Commit changes**: Include `NodeRAG_Source/` in your git commit

---

## 🔗 Integration Points

### Storage Layer (`storage/neo4j_storage.py`)
```python
class Neo4jStorage:
    def save_graph(self, graph, batch_size=1000)
    def load_graph(self) -> nx.Graph
    def get_node(self, node_id)
    def clear_database()
```

### Pipeline Layer (`build/graph_pipeline.py`)
```python
def save_graph(self):
    if self.config.use_neo4j_storage:
        neo4j_storage.save_graph(self.G)
    else:
        # Original pickle saving
        pickle.dump(self.G, f)
```

---

## ⚠️ Important Notes

### Version Compatibility
- Based on NodeRAG v0.1.0
- Neo4j 5.x compatible
- Python 3.8+ required

### Backward Compatibility
- All original NodeRAG features still work
- Pickle storage remains the default
- Neo4j is optional (enable via config)

### Testing
Run tests after making changes:
```powershell
# Test Neo4j integration
python utils/test_neo4j_search.py

# Test original functionality
python -m NodeRAG.build -f "POC_Data/documents"
```

---

## 📚 Original NodeRAG Documentation

For original NodeRAG documentation and features:
- Official site: https://terry-xu-666.github.io/NodeRAG_web/
- GitHub: https://github.com/Terry-Xu-666/NodeRAG

---

## 🤝 Contributing

When modifying NodeRAG source:
1. Document your changes in this README
2. Add comments explaining modifications
3. Test thoroughly with both pickle and Neo4j modes
4. Update integration layer (`neo4j_native_search.py`) if needed

---

## 📋 Modification Log

### December 2025
- **Added**: Neo4j storage backend support
- **Modified**: `storage/neo4j_storage.py` - Complete Neo4j integration
- **Modified**: `build/graph_pipeline.py` - Optional Neo4j saving
- **Added**: Configuration flags for Neo4j connection
- **Maintained**: Full backward compatibility with pickle storage

---

## 🐛 Known Issues

1. **Large graphs**: Neo4j initial migration can take 10-30 minutes for 50K+ nodes
2. **Memory usage**: First migration still requires loading pickle file
3. **Connection pooling**: May need tuning for production workloads

**Solutions planned**: Incremental graph updates, streaming migration

---

## 📞 Questions?

- Check `docs/NEO4J_OPTIMIZATION_SUMMARY.md` for technical details
- Review original NodeRAG docs for base functionality
- Contact team lead for customization questions

---

**Customized by**: [Your Team Name]  
**Base Version**: NodeRAG v0.1.0  
**Last Updated**: December 2025
