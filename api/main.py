"""
NodeRAG FastAPI Application
===========================

Main FastAPI application with all REST API endpoints for the NodeRAG system.

Endpoints Overview:
------------------
Health & Config:
  - GET  /                          - API info
  - GET  /health                    - Health check
  - GET  /config                    - Get current config
  - POST /initialize                - Initialize the service

Build Pipeline:
  - POST /build                     - Build/rebuild the knowledge graph
  - GET  /build/{build_id}/status   - Get build status

Search & Q&A:
  - POST /search                    - Search the knowledge graph
  - POST /answer                    - Get AI-generated answer for a question
  - POST /ask                       - Alias for /answer

Documents:
  - GET    /documents               - List all documents
  - POST   /documents               - Upload a new document
  - PUT    /documents/{filename}    - Update a document
  - DELETE /documents/{filename}    - Delete a document
  - POST   /documents/bulk          - Upload multiple documents

Q&A Nodes:
  - GET    /qa-pairs                - List all Q&A pairs
  - POST   /qa-pairs                - Create a new Q&A pair
  - DELETE /qa-pairs/{hash_id}      - Delete a Q&A pair
  - POST   /qa-pairs/bulk           - Create multiple Q&A pairs

Neo4j:
  - GET  /neo4j/stats               - Get Neo4j statistics
  - POST /neo4j/sync                - Sync graph to Neo4j
  - POST /neo4j/clear               - Clear Neo4j database

Graph Stats:
  - GET  /graph/stats               - Get graph statistics

Run with:
  uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks, Query, File, UploadFile, Form, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader
from contextlib import asynccontextmanager
from typing import Optional, List
from datetime import datetime
import time
import asyncio
import os

from .file_parser import parse_file

from .models import (
    # Base
    BaseResponse, ErrorResponse,
    # Config
    ConfigResponse, Neo4jConfig,
    # Build
    BuildRequest, BuildResponse, BuildStatusResponse, BuildStatus,
    # Search
    SearchRequest, SearchResponse, AnswerResponse, SearchResult, RetrievedNode,
    # Documents
    DocumentUploadRequest, DocumentUploadResponse, DocumentListResponse, 
    DocumentInfo, BulkDocumentUploadRequest,
    # Q&A
    QAPairCreate, QAPairResponse, QAPairListResponse, BulkQACreate,
    # Neo4j
    Neo4jSyncRequest, Neo4jSyncResponse, Neo4jStatsResponse,
    # Health & Stats
    HealthResponse, HealthStatus, GraphStatsResponse
)

from .services import (
    noderag_service,
    search_service,
    build_service,
    document_service,
    qa_service,
    neo4j_service
)


# ============================================================================
# Application Lifecycle
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler - initialize on startup"""
    print("🚀 Starting NodeRAG API...")
    
    # Try to auto-initialize with default folder
    if noderag_service.initialize():
        print("✓ Configuration loaded")
        
        # Try to connect to Neo4j
        if noderag_service.initialize_neo4j():
            print("✓ Neo4j connection established")
        else:
            print("⚠ Neo4j not available (search may be limited)")
        
        # Try to initialize search
        try:
            if noderag_service.initialize_search():
                print("✓ Search engine ready")
            else:
                print("⚠ Search engine not initialized (build graph first)")
        except Exception as e:
            print(f"⚠ Search engine not ready: {e}")
    else:
        print("⚠ Failed to auto-initialize (call /initialize endpoint)")
    
    print("✓ NodeRAG API is running!")
    yield
    
    # Cleanup on shutdown
    print("Shutting down NodeRAG API...")
    from NodeRAG.storage.neo4j_storage import close_neo4j_storage
    close_neo4j_storage()


# ============================================================================
# Create FastAPI App
# ============================================================================

app = FastAPI(
    title="NodeRAG API",
    description="""
    REST API for NodeRAG Knowledge Graph System
    
    Features:
    - Build and manage knowledge graphs from documents
    - Semantic search across the knowledge graph
    - AI-powered question answering
    - Document management (resumes, job descriptions)
    - Q&A pair management
    - Neo4j integration
    
    **Authentication:**
    Most endpoints require an API key. Click the 🔓 Authorize button and enter your API key.
    Set the NODERAG_API_KEY environment variable in your .env file.
    """,
    version="1.0.0",
    lifespan=lifespan,
    swagger_ui_parameters={
        "persistAuthorization": True
    }
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# Authentication
# ============================================================================

# Define API Key security scheme for Swagger UI
api_key_header = APIKeyHeader(
    name="X-API-Key",
    description="API Key for accessing protected endpoints. Set NODERAG_API_KEY in your .env file.",
    auto_error=False
)

async def verify_api_key(x_api_key: str = Depends(api_key_header)):
    """
    Verify API key for protected endpoints.
    
    The API key should be provided in the X-API-Key header.
    Set NODERAG_API_KEY environment variable to configure.
    """
    expected_key = os.environ.get('NODERAG_API_KEY')
    
    # If no key is configured, skip authentication (development mode)
    if not expected_key:
        print("[WARNING] NODERAG_API_KEY not set - authentication disabled")
        return True
    
    # Validate API key
    if not x_api_key or x_api_key != expected_key:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key. Provide X-API-Key header."
        )
    
    return True


# ============================================================================
# Health & Info Endpoints
# ============================================================================

@app.get("/", tags=["Info"])
async def root():
    """API root - basic information"""
    return {
        "name": "NodeRAG API",
        "version": "1.0.0",
        "description": "REST API for NodeRAG Knowledge Graph System",
        "docs_url": "/docs",
        "endpoints": {
            "health": "/health",
            "build": "/build",
            "search": "/search",
            "answer": "/answer",
            "documents": "/documents",
            "qa_pairs": "/qa-pairs",
            "neo4j": "/neo4j/stats"
        }
    }


@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """
    Health check endpoint.
    
    Returns the current status of all system components.
    """
    neo4j_connected = noderag_service.is_neo4j_connected
    graph_loaded = noderag_service.search_engine is not None
    search_ready = noderag_service.is_ready
    
    # Get stats if available
    total_nodes = 0
    total_relationships = 0
    
    if neo4j_connected:
        try:
            stats = neo4j_service.get_neo4j_stats()
            if stats.get("success"):
                total_nodes = stats.get("total_nodes", 0)
                total_relationships = stats.get("total_relationships", 0)
        except:
            pass
    
    return HealthResponse(
        success=True,
        message="NodeRAG API is running",
        status=HealthStatus(
            api_status="healthy",
            neo4j_connected=neo4j_connected,
            graph_loaded=graph_loaded,
            search_ready=search_ready,
            total_nodes=total_nodes,
            total_relationships=total_relationships
        )
    )


@app.get("/config", response_model=ConfigResponse, tags=["Config"])
async def get_config():
    """
    Get current configuration.
    
    Returns the active NodeRAG configuration settings.
    """
    if not noderag_service.config:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    # Return safe config (no passwords)
    config = dict(noderag_service.config.config)
    config.pop('neo4j_password', None)  # Remove password
    
    # Return the actual resolved main_folder (with MAIN_FOLDER env var applied)
    config['main_folder'] = noderag_service.config.main_folder
    
    return ConfigResponse(
        success=True,
        message="Configuration retrieved",
        config=config,
        neo4j_connected=noderag_service.is_neo4j_connected
    )


@app.post("/initialize", response_model=BaseResponse, tags=["Config"])
async def initialize_service(
    folder_path: Optional[str] = None,
    user_id: Optional[str] = None
):
    """
    Initialize or re-initialize the NodeRAG service.
    
    Args:
        folder_path: Path to documents folder (optional)
        user_id: User ID for multi-user support (optional)
    """
    # Reset service state
    noderag_service._initialized = False
    noderag_service.__init__()
    
    if not noderag_service.initialize(folder_path, user_id):
        raise HTTPException(status_code=500, detail="Failed to initialize service")
    
    # Initialize Neo4j
    neo4j_ok = noderag_service.initialize_neo4j()
    
    # Try to initialize search
    search_ok = False
    try:
        search_ok = noderag_service.initialize_search()
    except Exception as e:
        print(f"Search initialization skipped: {e}")
    
    return BaseResponse(
        success=True,
        message=f"Service initialized. Neo4j: {'connected' if neo4j_ok else 'not available'}. Search: {'ready' if search_ok else 'build graph first'}"
    )


# ============================================================================
# Build Pipeline Endpoints
# ============================================================================

@app.post("/build", response_model=BuildResponse, tags=["Build"], dependencies=[Depends(verify_api_key)])
async def build_graph(request: BuildRequest, background_tasks: BackgroundTasks):
    """
    Build or rebuild the knowledge graph.
    
    This endpoint triggers the full NodeRAG build pipeline:
    1. Document processing
    2. Text decomposition  
    3. Entity extraction
    4. Graph construction
    5. Embedding generation
    6. HNSW index creation
    7. (Optional) Neo4j sync
    
    The build runs in the background. Use `/build/{build_id}/status` to check progress.
    
    **Incremental Build**: When `incremental=True`, only new/changed documents are processed.
    This is faster but requires an existing graph.
    
    **Full Rebuild**: When `incremental=False`, the entire graph is rebuilt from scratch.
    """
    # Synchronous build for simplicity (can be made async with background tasks)
    try:
        result = await build_service.build_graph(
            folder_path=request.folder_path,
            incremental=request.incremental,
            sync_to_neo4j=request.sync_to_neo4j,
            user_id=request.user_id,
            force_rebuild=request.force_rebuild
        )
        
        if not result["success"]:
            raise HTTPException(status_code=500, detail=result.get("error", "Build failed"))
        
        return BuildResponse(
            success=True,
            message="Build completed successfully",
            build_id=result["build_id"],
            status=BuildStatus.COMPLETED,
            duration_seconds=result.get("duration_seconds"),
            nodes_created=result.get("nodes_created", 0),
            edges_created=result.get("edges_created", 0),
            neo4j_synced=result.get("neo4j_synced", False)
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/build/{build_id}/status", response_model=BuildStatusResponse, tags=["Build"])
async def get_build_status(build_id: str):
    """
    Get the status of a build operation.
    
    Args:
        build_id: The build ID returned from /build endpoint
    """
    result = build_service.get_build_status(build_id)
    
    if not result.get("success"):
        raise HTTPException(status_code=404, detail="Build ID not found")
    
    return BuildStatusResponse(
        success=True,
        message="Build status retrieved",
        status=BuildStatus(result.get("status", "pending")),
        current_stage=result.get("current_stage"),
        stages_completed=result.get("stages_completed", []),
        error_details=result.get("error")
    )


# ============================================================================
# Search & Q&A Endpoints
# ============================================================================

@app.post("/search", response_model=SearchResponse, tags=["Search"], dependencies=[Depends(verify_api_key)])
async def search(request: SearchRequest):
    """
    Search the knowledge graph.
    
    Performs semantic search across the knowledge graph without generating an answer.
    Returns relevant nodes, relationships, and Q&A pairs.
    
    Use this for:
    - Exploring related information
    - Finding specific entities
    - Retrieving context without LLM generation
    """
    if not noderag_service.is_ready:
        raise HTTPException(
            status_code=503, 
            detail="Search not ready. Initialize service and build graph first."
        )
    
    try:
        result = search_service.search(request.query, top_k=request.top_k, user_id=request.user_id)
        
        nodes = [
            RetrievedNode(
                hash_id=n["hash_id"],
                node_type=n["node_type"],
                text=n["text"],
                weight=n.get("weight", 0)
            )
            for n in result["nodes"]
        ]
        
        return SearchResponse(
            success=True,
            message="Search completed",
            query=request.query,
            results=SearchResult(
                nodes=nodes,
                relationships=result.get("relationships", []),
                qa_pairs=result.get("qa_pairs", []),
                total_count=result.get("total_count", 0)
            ),
            processing_time_ms=result["processing_time_ms"]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/answer", response_model=AnswerResponse, tags=["Search"], dependencies=[Depends(verify_api_key)])
async def answer_question(request: SearchRequest):
    """
    Generate an AI answer for a question.
    
    Performs semantic search and uses an LLM to generate a contextual answer
    based on the retrieved knowledge graph information.
    
    Args:
        query: The question to answer
        job_context: Optional job description to tailor the answer
        user_id: Optional user ID for personalization
    
    Use this for:
    - Interview question preparation
    - Getting detailed explanations
    - Resume-to-job matching analysis
    """
    if not noderag_service.is_ready:
        raise HTTPException(
            status_code=503,
            detail="Service not ready. Initialize service and build graph first."
        )
    
    try:
        result = search_service.answer(request.query, job_context=request.job_context, user_id=request.user_id)
        
        nodes = [
            RetrievedNode(
                hash_id=n["hash_id"],
                node_type=n["node_type"],
                text=n["text"],
                weight=n.get("weight", 0)
            )
            for n in result["nodes"]
        ]
        
        return AnswerResponse(
            success=True,
            message="Answer generated",
            query=request.query,
            answer=result["answer"],
            search_results=SearchResult(
                nodes=nodes,
                relationships=result.get("relationships", []),
                qa_pairs=result.get("qa_pairs", []),
                total_count=result.get("total_count", 0)
            ),
            processing_time_ms=result["processing_time_ms"]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/ask", response_model=AnswerResponse, tags=["Search"])
async def ask_question(request: SearchRequest):
    """
    Alias for /answer endpoint.
    
    Generate an AI answer for a question.
    """
    return await answer_question(request)


# ============================================================================
# Document Management Endpoints
# ============================================================================

@app.get("/documents", response_model=DocumentListResponse, tags=["Documents"])
async def list_documents(user_id: Optional[str] = Query(None)):
    """
    List all documents in the input folder.
    
    Args:
        user_id: Optional filter by user ID
    """
    documents = document_service.list_documents(user_id)
    
    return DocumentListResponse(
        success=True,
        message=f"Found {len(documents)} documents",
        documents=[DocumentInfo(**doc) for doc in documents],
        total_count=len(documents)
    )


@app.post("/documents", response_model=DocumentUploadResponse, tags=["Documents"], dependencies=[Depends(verify_api_key)])
async def upload_document(
    file: UploadFile = File(...),
    document_type: str = Form("resume"),
    user_id: Optional[str] = Form(None),
    filename: Optional[str] = Form(None)
):
    """
    Upload a binary document file (PDF, DOCX, TXT).
    
    The file will be parsed automatically to extract text content,
    then stored in the input folder for processing.
    
    **Supported Formats**: PDF, DOCX, TXT
    **Max File Size**: 10MB
    
    **Note**: After uploading, run `/build` with `incremental=True` to 
    add the document to the knowledge graph.
    """
    # Initialize NodeRAGService with user_id if provided
    if user_id:
        init_success = noderag_service.initialize(user_id=user_id)
        if not init_success:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to initialize service for user {user_id}"
            )
    
    # Read file bytes
    file_bytes = await file.read()
    
    # Validate file size (10MB limit)
    max_size = 10 * 1024 * 1024  # 10MB
    if len(file_bytes) > max_size:
        raise HTTPException(
            status_code=413, 
            detail=f"File too large. Maximum size is 10MB. Received: {len(file_bytes) / 1024 / 1024:.2f}MB"
        )
    
    # Use provided filename or fall back to uploaded filename
    final_filename = filename or file.filename
    
    # Parse file to extract text
    try:
        content = parse_file(file_bytes, final_filename)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"File parsing failed: {str(e)}")
    except ImportError as e:
        raise HTTPException(status_code=500, detail=f"Parser dependency missing: {str(e)}")
    
    # Validate extracted content
    if not content or len(content.strip()) < 10:
        raise HTTPException(
            status_code=400, 
            detail="Extracted content is too short or empty. Please check the file."
        )
    
    # Upload using existing document service
    result = document_service.upload_document(
        content=content,
        filename=final_filename,
        document_type=document_type,
        user_id=user_id,
        metadata={
            "original_filename": file.filename,
            "content_type": file.content_type,
            "file_size_bytes": len(file_bytes)
        }
    )
    
    if not result["success"]:
        raise HTTPException(status_code=500, detail=result.get("error", "Upload failed"))
    
    return DocumentUploadResponse(
        success=True,
        message=f"Document uploaded and parsed successfully. Extracted {len(content)} characters.",
        document=DocumentInfo(**result["document"]),
        requires_rebuild=result["requires_rebuild"]
    )


@app.put("/documents/{filename}", response_model=DocumentUploadResponse, tags=["Documents"])
async def update_document(
    filename: str, 
    content: str,
    user_id: Optional[str] = Query(None)
):
    """
    Update an existing document.
    
    The old version is backed up automatically.
    
    **Note**: After updating, run `/build` with `incremental=True` to 
    update the knowledge graph.
    """
    result = document_service.update_document(filename, content, user_id)
    
    if not result["success"]:
        raise HTTPException(status_code=404, detail=result.get("error", "Update failed"))
    
    return DocumentUploadResponse(
        success=True,
        message="Document updated successfully",
        document=DocumentInfo(**result["document"]),
        requires_rebuild=result["requires_rebuild"]
    )


@app.delete("/documents/{filename}", response_model=BaseResponse, tags=["Documents"])
async def delete_document(filename: str, user_id: Optional[str] = Query(None)):
    """
    Delete a document.
    
    **Note**: Deleting a document doesn't automatically remove it from the 
    knowledge graph. Run a full rebuild to clean up.
    """
    success = document_service.delete_document(filename, user_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Document not found")
    
    return BaseResponse(
        success=True,
        message="Document deleted successfully"
    )


@app.post("/documents/bulk", response_model=BaseResponse, tags=["Documents"])
async def bulk_upload_documents(request: BulkDocumentUploadRequest):
    """
    Upload multiple documents at once.
    
    Optionally triggers an incremental build after all uploads complete.
    """
    uploaded = 0
    errors = []
    
    for doc in request.documents:
        try:
            result = document_service.upload_document(
                content=doc.content,
                filename=doc.filename,
                document_type=doc.document_type,
                user_id=doc.user_id,
                metadata=doc.metadata
            )
            if result["success"]:
                uploaded += 1
            else:
                errors.append(f"{doc.filename}: {result.get('error')}")
        except Exception as e:
            errors.append(f"{doc.filename}: {str(e)}")
    
    # Auto-build if requested
    if request.auto_build and uploaded > 0:
        try:
            await build_service.build_graph(incremental=True, sync_to_neo4j=True)
        except Exception as e:
            errors.append(f"Auto-build failed: {str(e)}")
    
    return BaseResponse(
        success=len(errors) == 0,
        message=f"Uploaded {uploaded}/{len(request.documents)} documents" + 
                (f". Errors: {'; '.join(errors)}" if errors else "")
    )


# ============================================================================
# Q&A Node Management Endpoints
# ============================================================================

@app.get("/qa-pairs", response_model=QAPairListResponse, tags=["Q&A Pairs"])
async def list_qa_pairs(user_id: Optional[str] = Query(None)):
    """
    List all Q&A pairs from the knowledge graph.
    
    Q&A pairs are question-answer nodes that help the system learn
    from historical interview questions and answers.
    """
    qa_pairs = qa_service.list_qa_pairs(user_id)
    
    return QAPairListResponse(
        success=True,
        message=f"Found {len(qa_pairs)} Q&A pairs",
        qa_pairs=qa_pairs,
        total_count=len(qa_pairs)
    )


@app.post("/qa-pairs", response_model=QAPairResponse, tags=["Q&A Pairs"], dependencies=[Depends(verify_api_key)])
async def create_qa_pair(request: QAPairCreate):
    """
    Create a new Q&A pair.
    
    This adds Question and Answer nodes to the knowledge graph **incrementally**,
    without requiring a full rebuild. The nodes are linked together and can be
    used to improve answer generation.
    
    **Incremental**: Q&A pairs are added directly to Neo4j without rebuilding.
    """
    result = qa_service.create_qa_pair(
        question=request.question,
        answer=request.answer,
        question_id=request.question_id,
        user_id=request.user_id,
        job_title=request.job_title,
        company_name=request.company_name,
        submission_date=request.submission_date,
        sync_to_neo4j=True
    )
    
    if not result["success"]:
        raise HTTPException(status_code=500, detail=result.get("error", "Failed to create Q&A pair"))
    
    return QAPairResponse(
        success=True,
        message="Q&A pair created successfully",
        question_hash_id=result["question_hash_id"],
        answer_hash_id=result["answer_hash_id"],
        question=result["question"],
        answer=result["answer"],
        added_to_graph=result["added_to_graph"]
    )


@app.delete("/qa-pairs/{question_hash_id}", response_model=BaseResponse, tags=["Q&A Pairs"])
async def delete_qa_pair(question_hash_id: str):
    """
    Delete a Q&A pair by question hash ID.
    
    This removes both the Question and Answer nodes from Neo4j.
    """
    success = qa_service.delete_qa_pair(question_hash_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Q&A pair not found or Neo4j not connected")
    
    return BaseResponse(
        success=True,
        message="Q&A pair deleted successfully"
    )


@app.post("/qa-pairs/bulk", response_model=BaseResponse, tags=["Q&A Pairs"], dependencies=[Depends(verify_api_key)])
async def bulk_create_qa_pairs(request: BulkQACreate):
    """
    Create multiple Q&A pairs at once.
    
    All Q&A pairs are added incrementally to Neo4j without rebuilding the graph.
    """
    created = 0
    errors = []
    
    for qa in request.qa_pairs:
        try:
            result = qa_service.create_qa_pair(
                question=qa.question,
                answer=qa.answer,
                question_id=qa.question_id,
                user_id=qa.user_id,
                job_title=qa.job_title,
                company_name=qa.company_name,
                submission_date=qa.submission_date,
                sync_to_neo4j=request.sync_to_neo4j
            )
            if result["success"]:
                created += 1
            else:
                errors.append(result.get("error", "Unknown error"))
        except Exception as e:
            errors.append(str(e))
    
    return BaseResponse(
        success=len(errors) == 0,
        message=f"Created {created}/{len(request.qa_pairs)} Q&A pairs" +
                (f". Errors: {'; '.join(errors[:3])}" if errors else "")
    )


# ============================================================================
# Neo4j Endpoints
# ============================================================================

@app.get("/neo4j/stats", response_model=Neo4jStatsResponse, tags=["Neo4j"])
async def get_neo4j_stats(user_id: Optional[str] = Query(None, description="Filter stats by user ID")):
    """
    Get Neo4j database statistics.
    
    Returns node counts, relationship counts, and type distribution.
    Optionally filter by user_id.
    """
    result = neo4j_service.get_neo4j_stats(user_id=user_id)
    
    if not result["success"]:
        raise HTTPException(status_code=503, detail=result.get("error", "Neo4j not available"))
    
    return Neo4jStatsResponse(
        success=True,
        message=f"Statistics retrieved{' for user_id=' + user_id if user_id else ''}",
        total_nodes=result["total_nodes"],
        total_relationships=result["total_relationships"],
        node_types=result["node_types"],
        connected=True
    )


@app.post("/neo4j/sync", response_model=Neo4jSyncResponse, tags=["Neo4j"], dependencies=[Depends(verify_api_key)])
async def sync_to_neo4j(request: Neo4jSyncRequest):
    """
    Sync the graph to Neo4j.
    
    **Full Sync** (`full_sync=True`): Clears Neo4j data for user and re-imports everything.
    Use after major changes or to ensure consistency.
    
    **Incremental Sync** (`full_sync=False`): Adds/updates nodes without clearing.
    Faster but may leave orphaned nodes from deleted data.
    
    **user_id**: If provided, only syncs/clears data for this user.
    """
    result = neo4j_service.sync_to_neo4j(full_sync=request.full_sync, user_id=request.user_id)
    
    if not result["success"]:
        raise HTTPException(status_code=500, detail=result.get("error", "Sync failed"))
    
    return Neo4jSyncResponse(
        success=True,
        message=f"Sync completed successfully{' for user_id=' + request.user_id if request.user_id else ''}",
        nodes_synced=result["nodes_synced"],
        relationships_synced=result["relationships_synced"],
        duration_seconds=result["duration_seconds"],
        sync_type=result["sync_type"]
    )


@app.post("/neo4j/clear", response_model=BaseResponse, tags=["Neo4j"], dependencies=[Depends(verify_api_key)])
async def clear_neo4j(user_id: Optional[str] = Query(None, description="Only clear data for this user ID")):
    """
    Clear data from Neo4j database.
    
    **WARNING**: If no user_id provided, permanently deletes ALL nodes and relationships!
    
    With user_id: Only deletes data for that specific user.
    """
    success = neo4j_service.clear_neo4j(user_id=user_id)
    
    if not success:
        raise HTTPException(status_code=500, detail="Failed to clear Neo4j")
    
    msg = f"Neo4j data cleared for user_id={user_id}" if user_id else "Neo4j database cleared (all data)"
    return BaseResponse(
        success=True,
        message=msg
    )


# ============================================================================
# Graph Statistics Endpoint
# ============================================================================

@app.get("/graph/stats", response_model=GraphStatsResponse, tags=["Stats"])
async def get_graph_stats():
    """
    Get knowledge graph statistics.
    
    Returns comprehensive statistics about the graph including
    node counts by type, relationship counts, and document counts.
    """
    if not noderag_service.is_neo4j_connected:
        raise HTTPException(status_code=503, detail="Neo4j not connected")
    
    result = neo4j_service.get_neo4j_stats()
    
    if not result["success"]:
        raise HTTPException(status_code=500, detail=result.get("error"))
    
    node_types = result.get("node_types", {})
    
    return GraphStatsResponse(
        success=True,
        message="Statistics retrieved",
        total_nodes=result["total_nodes"],
        total_edges=result["total_relationships"],
        node_type_distribution=node_types,
        documents_count=node_types.get("document", 0),
        entities_count=node_types.get("entity", 0),
        relationships_count=node_types.get("relationship", 0),
        qa_pairs_count=node_types.get("question", 0)
    )


# ============================================================================
# Run Application
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
