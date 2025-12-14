# NodeRAG API Documentation

## Overview

The NodeRAG API provides a comprehensive REST interface for the NodeRAG knowledge graph system. It enables you to:

- Build and manage knowledge graphs from documents (resumes, job descriptions)
- Perform semantic search across the knowledge graph
- Get AI-powered answers to questions
- Manage documents (upload, update, delete)
- Manage Q&A pairs incrementally (without rebuilding)
- Sync with Neo4j database

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Start the API Server

```bash
# From the project root directory
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

### 3. Access the API

- **API Documentation (Swagger UI)**: http://localhost:8000/docs
- **Alternative Docs (ReDoc)**: http://localhost:8000/redoc
- **Health Check**: http://localhost:8000/health

## API Endpoints Summary

### Health & Configuration

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | API info and available endpoints |
| GET | `/health` | Health check with system status |
| GET | `/config` | Get current configuration |
| POST | `/initialize` | Initialize/reinitialize the service |

### Build Pipeline

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/build` | Build/rebuild the knowledge graph |
| GET | `/build/{build_id}/status` | Get build operation status |

### Search & Q&A

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/search` | Search without generating answer |
| POST | `/answer` | Generate AI answer for a question |
| POST | `/ask` | Alias for /answer |

### Document Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/documents` | List all documents |
| POST | `/documents` | Upload a new document |
| PUT | `/documents/{filename}` | Update a document |
| DELETE | `/documents/{filename}` | Delete a document |
| POST | `/documents/bulk` | Upload multiple documents |

### Q&A Pair Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/qa-pairs` | List all Q&A pairs |
| POST | `/qa-pairs` | Create a new Q&A pair (incremental) |
| DELETE | `/qa-pairs/{hash_id}` | Delete a Q&A pair |
| POST | `/qa-pairs/bulk` | Create multiple Q&A pairs |

### Neo4j Operations

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/neo4j/stats` | Get Neo4j statistics |
| POST | `/neo4j/sync` | Sync graph to Neo4j |
| POST | `/neo4j/clear` | Clear Neo4j database |

### Statistics

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/graph/stats` | Get graph statistics |

## Detailed Endpoint Documentation

### Build Pipeline

#### POST `/build`

Build or rebuild the knowledge graph from documents.

**Request Body:**
```json
{
  "folder_path": "POC_Data/documents",  // Optional, uses default if not provided
  "incremental": true,                   // true = only process new/changed files
  "sync_to_neo4j": true,                // Automatically sync to Neo4j after build
  "user_id": "user123"                  // Optional, for multi-user support
}
```

**Response:**
```json
{
  "success": true,
  "message": "Build completed successfully",
  "build_id": "a1b2c3d4",
  "status": "completed",
  "duration_seconds": 45.2,
  "nodes_created": 150,
  "edges_created": 320,
  "neo4j_synced": true,
  "timestamp": "2024-12-14T10:30:00"
}
```

**Notes:**
- Incremental build only processes new/changed documents
- Full rebuild (`incremental: false`) processes everything from scratch
- Build is synchronous; for large datasets, consider using background tasks

### Search & Q&A

#### POST `/search`

Search the knowledge graph without generating an answer.

**Request Body:**
```json
{
  "query": "What is your experience with Python?",
  "top_k": 10,
  "include_qa_pairs": true,
  "user_id": "user123"
}
```

**Response:**
```json
{
  "success": true,
  "query": "What is your experience with Python?",
  "results": {
    "nodes": [
      {
        "hash_id": "abc123",
        "node_type": "entity",
        "text": "Python programming",
        "weight": 0.95
      }
    ],
    "relationships": [...],
    "qa_pairs": [...],
    "total_count": 25
  },
  "processing_time_ms": 150.5
}
```

#### POST `/answer`

Get an AI-generated answer based on knowledge graph search.

**Request Body:**
```json
{
  "query": "What is your experience with Python?",
  "job_context": "We are looking for a Senior Python Developer...",
  "user_id": "user123"
}
```

**Response:**
```json
{
  "success": true,
  "query": "What is your experience with Python?",
  "answer": "Based on the resume, the candidate has 5 years of Python experience...",
  "search_results": {
    "nodes": [...],
    "relationships": [...],
    "qa_pairs": [...],
    "total_count": 25
  },
  "processing_time_ms": 2500.0
}
```

### Document Management

#### POST `/documents`

Upload a new document (resume, job description, etc.)

**Request Body:**
```json
{
  "content": "John Doe\nSoftware Engineer\n\nExperience:\n- 5 years Python...",
  "filename": "john_doe_resume.txt",
  "document_type": "resume",
  "user_id": "user123",
  "metadata": {
    "source": "uploaded",
    "date": "2024-12-14"
  }
}
```

**Response:**
```json
{
  "success": true,
  "message": "Document uploaded successfully",
  "document": {
    "filename": "john_doe_resume.txt",
    "path": "POC_Data/documents/input/john_doe_resume.txt",
    "size_bytes": 1024,
    "created_at": "2024-12-14T10:30:00",
    "document_type": "resume"
  },
  "requires_rebuild": true
}
```

**After uploading:** Run `/build` with `incremental: true` to add to the graph.

### Q&A Pair Management

#### POST `/qa-pairs`

Create a new Q&A pair **incrementally** (no rebuild required).

**Request Body:**
```json
{
  "question": "Tell me about a challenging project you worked on.",
  "answer": "I led a team of 5 developers to build a real-time analytics platform...",
  "question_id": "q123",
  "user_id": "user123",
  "job_title": "Senior Software Engineer",
  "company_name": "TechCorp",
  "submission_date": "2024-12-14"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Q&A pair created successfully",
  "question_hash_id": "hash_abc123",
  "answer_hash_id": "hash_def456",
  "question": "Tell me about a challenging project...",
  "answer": "I led a team of 5 developers...",
  "added_to_graph": true
}
```

**Key Feature:** Q&A pairs are added directly to Neo4j without rebuilding the entire graph. This makes it efficient to add new interview Q&A data.

### Neo4j Operations

#### POST `/neo4j/sync`

Sync the graph to Neo4j.

**Request Body:**
```json
{
  "full_sync": false  // false = incremental, true = clear and reimport
}
```

**Response:**
```json
{
  "success": true,
  "message": "Sync completed successfully",
  "nodes_synced": 150,
  "relationships_synced": 320,
  "duration_seconds": 5.2,
  "sync_type": "incremental"
}
```

## Incremental Updates vs Full Rebuild

### When to Use Incremental Updates

1. **Adding new Q&A pairs**: Use `POST /qa-pairs` - no rebuild needed
2. **Adding new documents**: Use `POST /documents` then `POST /build` with `incremental: true`
3. **Minor updates**: Use incremental build for faster processing

### When to Use Full Rebuild

1. **Major changes**: Many documents added/removed
2. **Data inconsistency**: After errors or manual database changes
3. **Clean slate**: When you want to ensure complete consistency

### Comparison

| Operation | Rebuild Required? | Method |
|-----------|------------------|--------|
| Add Q&A pair | No | `POST /qa-pairs` |
| Add document | Incremental | `POST /documents` + `POST /build` (incremental) |
| Update document | Incremental | `PUT /documents/{filename}` + `POST /build` (incremental) |
| Delete document | Full (recommended) | `DELETE /documents/{filename}` + `POST /build` (full) |
| Sync to Neo4j | N/A | `POST /neo4j/sync` |

## Multi-User Support

The API supports multi-user deployments through the `user_id` parameter:

```json
{
  "user_id": "user123"
}
```

When `user_id` is provided:
- Documents are stored in `users/user_{id}/input/`
- Cache is stored in `users/user_{id}/cache/`
- Each user has their own isolated knowledge graph

## Error Handling

All endpoints return consistent error responses:

```json
{
  "success": false,
  "error": "Error description",
  "details": "Additional details if available",
  "timestamp": "2024-12-14T10:30:00"
}
```

Common HTTP Status Codes:
- `200`: Success
- `400`: Bad request (invalid parameters)
- `404`: Resource not found
- `500`: Internal server error
- `503`: Service unavailable (not initialized, Neo4j disconnected)

## Usage Examples

### Python Client Example

```python
import requests

BASE_URL = "http://localhost:8000"

# 1. Check health
response = requests.get(f"{BASE_URL}/health")
print(response.json())

# 2. Upload a resume
response = requests.post(f"{BASE_URL}/documents", json={
    "content": "John Doe\nSoftware Engineer...",
    "filename": "resume.txt",
    "document_type": "resume"
})
print(response.json())

# 3. Build graph (incremental)
response = requests.post(f"{BASE_URL}/build", json={
    "incremental": True,
    "sync_to_neo4j": True
})
print(response.json())

# 4. Ask a question
response = requests.post(f"{BASE_URL}/answer", json={
    "query": "What is the candidate's experience with Python?",
    "job_context": "Looking for a Python developer..."
})
print(response.json()["answer"])

# 5. Add a Q&A pair (no rebuild needed!)
response = requests.post(f"{BASE_URL}/qa-pairs", json={
    "question": "Why do you want this job?",
    "answer": "I'm passionate about building scalable systems..."
})
print(response.json())
```

### cURL Examples

```bash
# Health check
curl http://localhost:8000/health

# Upload document
curl -X POST http://localhost:8000/documents \
  -H "Content-Type: application/json" \
  -d '{"content": "Resume content...", "filename": "resume.txt"}'

# Ask a question
curl -X POST http://localhost:8000/answer \
  -H "Content-Type: application/json" \
  -d '{"query": "What skills does the candidate have?"}'

# Add Q&A pair
curl -X POST http://localhost:8000/qa-pairs \
  -H "Content-Type: application/json" \
  -d '{"question": "Q text", "answer": "A text"}'
```

## Configuration

The API reads configuration from `Node_config.yaml` in your documents folder:

```yaml
config:
  main_folder: "POC_Data/documents"
  neo4j_uri: "bolt://localhost:7687"
  neo4j_user: "neo4j"
  neo4j_password: "your-password"
  # ... other settings
```

## Production Considerations

1. **CORS**: Update `allow_origins` in `main.py` for production
2. **Authentication**: Add JWT or API key authentication
3. **Rate Limiting**: Implement rate limiting for public APIs
4. **Logging**: Configure proper logging for production
5. **SSL**: Use HTTPS in production

## Running in Production

```bash
# With Gunicorn (recommended for production)
gunicorn api.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000

# Or with Uvicorn directly
uvicorn api.main:app --host 0.0.0.0 --port 8000 --workers 4
```
