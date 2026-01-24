"""
Pydantic Models for NodeRAG API
===============================

Request and response models for the REST API endpoints.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


# ============================================================================
# Enums
# ============================================================================

class BuildStatus(str, Enum):
    """Build pipeline status"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class NodeType(str, Enum):
    """Types of nodes in the knowledge graph"""
    ENTITY = "entity"
    RELATIONSHIP = "relationship"
    ATTRIBUTE = "attribute"
    SEMANTIC_UNIT = "semantic_unit"
    TEXT_UNIT = "text"
    QUESTION = "question"
    ANSWER = "answer"
    COMMUNITY = "community"
    HIGH_LEVEL_ELEMENT = "high_level_element"


# ============================================================================
# Base Models
# ============================================================================

class BaseResponse(BaseModel):
    """Base response model with common fields"""
    success: bool = True
    message: str = ""
    timestamp: datetime = Field(default_factory=datetime.now)


class ErrorResponse(BaseModel):
    """Error response model"""
    success: bool = False
    error: str
    details: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)


# ============================================================================
# Configuration Models
# ============================================================================

class Neo4jConfig(BaseModel):
    """Neo4j connection configuration"""
    uri: str = Field(default="bolt://localhost:7687", description="Neo4j connection URI")
    user: str = Field(default="neo4j", description="Neo4j username")
    password: str = Field(description="Neo4j password")


class ConfigResponse(BaseResponse):
    """Configuration response"""
    config: Dict[str, Any]
    neo4j_connected: bool = False


# ============================================================================
# Build Pipeline Models
# ============================================================================

class BuildRequest(BaseModel):
    """Request to build/rebuild the knowledge graph"""
    folder_path: Optional[str] = Field(
        default=None, 
        description="Path to documents folder (uses default if not provided)"
    )
    incremental: bool = Field(
        default=True, 
        description="Whether to perform incremental build (True) or full rebuild (False)"
    )
    sync_to_neo4j: bool = Field(
        default=True,
        description="Automatically sync to Neo4j after build"
    )
    user_id: Optional[str] = Field(
        default=None,
        description="User ID for multi-user support"
    )
    force_rebuild: bool = Field(
        default=False,
        description="Force rebuild by clearing cache (useful when switching users or forcing fresh build)"
    )


class BuildStatusResponse(BaseResponse):
    """Build pipeline status response"""
    status: BuildStatus
    current_stage: Optional[str] = None
    progress: Optional[float] = None
    stages_completed: List[str] = []
    error_details: Optional[str] = None


class BuildResponse(BaseResponse):
    """Build completion response"""
    build_id: str
    status: BuildStatus
    duration_seconds: Optional[float] = None
    nodes_created: Optional[int] = None
    edges_created: Optional[int] = None
    neo4j_synced: Optional[bool] = None


# ============================================================================
# Search & Q&A Models
# ============================================================================

class SearchRequest(BaseModel):
    """Search/Question request"""
    query: str = Field(description="The search query or question")
    user_id: Optional[str] = Field(default=None, description="User ID for personalization")
    job_context: Optional[str] = Field(
        default=None,
        description="Optional job description context for tailoring answers"
    )
    top_k: int = Field(default=10, ge=1, le=100, description="Number of results to return")
    include_qa_pairs: bool = Field(default=True, description="Include Q&A pair search")


class RetrievedNode(BaseModel):
    """A retrieved node from the knowledge graph"""
    hash_id: str
    node_type: str
    text: str
    weight: float
    human_readable_id: Optional[str] = None
    metadata: Dict[str, Any] = {}


class SearchResult(BaseModel):
    """Search result with retrieved nodes"""
    nodes: List[RetrievedNode]
    relationships: List[Dict[str, Any]] = []
    qa_pairs: List[Dict[str, Any]] = []
    total_count: int


class AnswerResponse(BaseResponse):
    """Answer response with full context"""
    query: str
    answer: str
    search_results: SearchResult
    processing_time_ms: float


class SearchResponse(BaseResponse):
    """Simple search response (without LLM answer)"""
    query: str
    results: SearchResult
    processing_time_ms: float


# ============================================================================
# Document Management Models
# ============================================================================

class DocumentUploadRequest(BaseModel):
    """Request to upload a new document"""
    content: str = Field(description="Document content (text)")
    filename: str = Field(description="Filename for the document")
    document_type: str = Field(
        default="resume",
        description="Type of document: 'resume', 'job_description', or 'general'"
    )
    user_id: Optional[str] = Field(default=None, description="Associated user ID")
    metadata: Dict[str, Any] = Field(default={}, description="Additional metadata")


class DocumentInfo(BaseModel):
    """Document information"""
    filename: str
    path: str
    size_bytes: int
    created_at: datetime
    document_type: str
    user_id: Optional[str] = None


class DocumentListResponse(BaseResponse):
    """List of documents"""
    documents: List[DocumentInfo]
    total_count: int


class DocumentUploadResponse(BaseResponse):
    """Document upload response"""
    document: DocumentInfo
    requires_rebuild: bool = True


class BulkDocumentUploadRequest(BaseModel):
    """Request to upload multiple documents"""
    documents: List[DocumentUploadRequest]
    auto_build: bool = Field(
        default=False,
        description="Automatically trigger incremental build after upload"
    )


# ============================================================================
# Q&A Node Management Models
# ============================================================================

class QAPairCreate(BaseModel):
    """Create a new Q&A pair"""
    question: str = Field(description="The question text")
    answer: str = Field(description="The answer text")
    question_id: Optional[str] = Field(default=None, description="External question ID")
    user_id: Optional[str] = Field(default=None, description="Associated user ID")
    job_title: Optional[str] = Field(default=None, description="Associated job title")
    company_name: Optional[str] = Field(default=None, description="Associated company name")
    submission_date: Optional[str] = Field(default=None, description="Submission date")


class QAPairResponse(BaseResponse):
    """Q&A pair response"""
    question_hash_id: str
    answer_hash_id: str
    question: str
    answer: str
    added_to_graph: bool = True


class QAPairListResponse(BaseResponse):
    """List of Q&A pairs"""
    qa_pairs: List[Dict[str, Any]]
    total_count: int


class BulkQACreate(BaseModel):
    """Create multiple Q&A pairs"""
    qa_pairs: List[QAPairCreate]
    sync_to_neo4j: bool = Field(default=True, description="Sync to Neo4j after creation")


# ============================================================================
# Neo4j Sync Models
# ============================================================================

class Neo4jSyncRequest(BaseModel):
    """Request to sync with Neo4j"""
    full_sync: bool = Field(
        default=False,
        description="Full sync (clears Neo4j data for user first) vs incremental sync"
    )
    user_id: Optional[str] = Field(
        default=None,
        description="User ID to sync data for (multi-tenant filtering)"
    )


class Neo4jStatsResponse(BaseResponse):
    """Neo4j database statistics"""
    total_nodes: int
    total_relationships: int
    node_types: Dict[str, int]
    connected: bool = True


class Neo4jSyncResponse(BaseResponse):
    """Neo4j sync completion response"""
    nodes_synced: int
    relationships_synced: int
    duration_seconds: float
    sync_type: str  # "full" or "incremental"


# ============================================================================
# Health & Status Models
# ============================================================================

class HealthStatus(BaseModel):
    """System health status"""
    api_status: str = "healthy"
    neo4j_connected: bool = False
    graph_loaded: bool = False
    search_ready: bool = False
    last_build_time: Optional[datetime] = None
    total_nodes: int = 0
    total_relationships: int = 0


class HealthResponse(BaseResponse):
    """Health check response"""
    status: HealthStatus


# ============================================================================
# Graph Statistics Models
# ============================================================================

class GraphStatsResponse(BaseResponse):
    """Graph statistics response"""
    total_nodes: int
    total_edges: int
    node_type_distribution: Dict[str, int]
    documents_count: int
    entities_count: int
    relationships_count: int
    qa_pairs_count: int
