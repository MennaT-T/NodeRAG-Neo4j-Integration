# Contributing to NodeRAG Neo4j Integration

Thank you for contributing! This guide will help you work effectively with the team.

## 📋 Development Workflow

### 1. Before Starting Work
```powershell
# Pull latest changes
git pull origin main

# Create a feature branch (optional but recommended)
git checkout -b feature/your-feature-name
```

### 2. Making Changes
- **Keep changes focused**: One feature or fix per commit
- **Test your changes**: Run `python utils/test_neo4j_search.py` before committing
- **Update documentation**: If you change functionality, update relevant docs

### 3. Committing Changes
```powershell
# Check what you changed
git status

# Stage specific files (don't use git add .)
git add search_resumes.py neo4j_native_search.py

# Commit with clear message
git commit -m "Fix: Resolved batch query timeout issue"
```

### 4. Commit Message Convention
Use prefixes for clarity:
- `Add:` New features or files
- `Fix:` Bug fixes
- `Update:` Changes to existing functionality
- `Docs:` Documentation updates
- `Refactor:` Code restructuring without functional changes
- `Test:` Adding or updating tests

**Examples:**
```
Add: Implemented incremental graph updates
Fix: Resolved Neo4j connection pool exhaustion
Update: Improved batch query performance by 30%
Docs: Added troubleshooting section for Windows users
```

### 5. Pushing Changes
```powershell
# Push to your branch
git push origin feature/your-feature-name

# Create pull request on GitHub/GitLab
```

---

## ⚠️ NEVER Commit These Files

### Automatically Ignored (in .gitignore)
- `venv/`, `.venv/` - Virtual environments
- `__pycache__/`, `*.pyc` - Python cache
- `*.log` - Log files
- `POC_Data/documents/Node_config.yaml` - API keys!
- `POC_Data/documents/cache/` - Generated files
- `*.pkl`, `*.bin`, `*.parquet` - Binary cache files

### Double-Check Before Committing
```powershell
# Review what will be committed
git diff --cached

# If you see API keys or sensitive data, unstage immediately
git reset HEAD <file>
```

---

## ✅ What Should Be Committed

### Always Commit
- Source code (`.py` files)
- Documentation (`.md` files)
- Configuration examples (`Node_config.yaml.example`)
- Requirements file (`requirements.txt`)
- Utility scripts (`utils/*.py`)

### Optional (Discuss with Team)
- Sample input data (small files in `POC_Data/documents/input/`)
- Test data (if small and non-sensitive)

---

## 🧪 Testing Guidelines

### Before Committing
Run all tests to ensure nothing broke:
```powershell
# End-to-end test
python utils/test_neo4j_search.py

# Manual smoke test
python search_resumes.py
# Ask a test question and verify output
```

### Writing Tests
If you add new functionality:
1. Add test cases to `utils/test_neo4j_search.py`
2. Document expected behavior
3. Include edge cases

---

## 📝 Code Style Guidelines

### Python Style
- Follow PEP 8 conventions
- Use meaningful variable names
- Add docstrings to functions and classes
- Keep functions focused (single responsibility)

**Good Example:**
```python
def get_batch_node_properties(node_ids: List[str], property_names: List[str]) -> Dict[str, Dict]:
    """
    Get multiple properties for multiple nodes in one query.
    
    Args:
        node_ids: List of node IDs to query
        property_names: List of property names to retrieve
    
    Returns:
        Dictionary mapping node_id to {property: value}
    """
    # Implementation
```

### Comments
- Explain **why**, not **what** (code shows what)
- Add comments for complex logic
- Use section headers for organization

**Good Example:**
```python
# ==================== Step 2: Enable Neo4j Optimization ====================
# This is the KEY optimization that eliminates graph.pkl loading
integrate_neo4j_search(config, NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
```

---

## 🔧 Development Setup

### Initial Setup (One Time)
```powershell
# Clone repo
git clone <repo-url>
cd NodeRAG

# Create venv
python -m venv venv
.\venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# Copy config
cp Node_config.yaml.example POC_Data/documents/Node_config.yaml
# Edit Node_config.yaml and add your API key

# Start Neo4j
docker run -d --name neo4j-noderag -p 7474:7474 -p 7687:7687 -e NEO4J_AUTH=neo4j/autoapply123 neo4j
```

### Daily Development
```powershell
# Activate venv (do this every time)
.\venv\Scripts\Activate.ps1

# Pull latest changes
git pull origin main

# Start Neo4j if not running
docker start neo4j-noderag
```

---

## 🐛 Debugging Tips

### Enable Debug Logging
Add to your script:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Neo4j Query Debugging
Check queries in Neo4j Browser (http://localhost:7474):
```cypher
// Check node count
MATCH (n:Node) RETURN count(n)

// Check recent queries (if enabled in Neo4j config)
CALL dbms.listQueries()
```

### Memory Profiling
```python
import psutil
import os

process = psutil.Process(os.getpid())
print(f"Memory: {process.memory_info().rss / 1024 / 1024:.2f} MB")
```

---

## 📂 Project Organization

### Where to Add New Files

**Core functionality**: Root directory
```
search_resumes.py
neo4j_native_search.py
```

**Utility scripts**: `utils/` directory
```
utils/migrate_to_neo4j.py
utils/test_neo4j_search.py
```

**Documentation**: `docs/` directory
```
docs/NEO4J_OPTIMIZATION_SUMMARY.md
docs/SEARCH_ARCHITECTURE_EXPLAINED.md
```

**Configuration**: Root directory (examples only)
```
Node_config.yaml.example
requirements.txt
```

---

## 🤝 Code Review Checklist

Before submitting for review:
- [ ] Code runs without errors
- [ ] Tests pass (`python utils/test_neo4j_search.py`)
- [ ] No API keys or passwords in code
- [ ] Added comments for complex logic
- [ ] Updated relevant documentation
- [ ] Followed naming conventions
- [ ] No unnecessary files included
- [ ] Commit messages are clear

---

## 🆘 Getting Help

### Common Issues

**"Import errors after git pull"**
```powershell
# Reinstall dependencies
pip install -r requirements.txt
```

**"Neo4j connection failed"**
```powershell
# Restart Neo4j container
docker restart neo4j-noderag
```

**"Merge conflicts"**
```powershell
# Update from main first
git pull origin main

# If conflicts, resolve them in your editor
# Then commit the resolution
git add .
git commit -m "Merge: Resolved conflicts with main"
```

### Contact Points
- Team Lead: [Add contact info]
- Technical Issues: Check `docs/` folder or create GitHub issue
- Neo4j Questions: Refer to `docs/NEO4J_OPTIMIZATION_SUMMARY.md`

---

## 📚 Additional Resources

- **Main README**: `README.md`
- **Setup Guide**: `SETUP_GUIDE.md`
- **Technical Docs**: `docs/` folder
- **Git Basics**: https://git-scm.com/doc
- **Python Style Guide**: https://pep8.org/

---

**Remember**: When in doubt, ask! It's better to clarify than to make assumptions.

Happy coding! 🚀
