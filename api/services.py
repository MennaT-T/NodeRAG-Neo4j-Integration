"""
Service Layer for NodeRAG API
=============================

Business logic and service functions for the API endpoints.
Handles interaction with NodeRAG core modules.
"""

import os
import sys
import asyncio
import time
import uuid
import shutil
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime
import json
import threading

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from NodeRAG import NodeConfig, NodeSearch, NodeRag
from NodeRAG.storage.neo4j_storage import get_neo4j_storage, close_neo4j_storage
from NodeRAG.build.component import Question, Answer


class NodeRAGService:
    """
    Service class for NodeRAG operations.
    Manages configuration, search, and build operations.
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        """Singleton pattern for service instance"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        self.config: Optional[NodeConfig] = None
        self.search_engine: Optional[NodeSearch] = None
        self.neo4j_storage = None
        self.neo4j_uri: Optional[str] = None
        self.neo4j_user: Optional[str] = None
        self.neo4j_password: Optional[str] = None
        self.default_folder: str = str(Path(__file__).parent.parent / "POC_Data" / "documents")
        self._build_status: Dict[str, Any] = {}
        self._neo4j_integrated = False
        self._initialized = True
    
    def initialize(self, folder_path: Optional[str] = None, user_id: Optional[str] = None) -> bool:
        """
        Initialize the service with configuration.
        
        Args:
            folder_path: Path to documents folder
            user_id: Optional user ID for multi-user support
            
        Returns:
            True if successful, False otherwise
        """
        try:
            folder = folder_path or self.default_folder
            
            # Reset singleton for new config if user_id changes
            if user_id:
                NodeConfig._instance = None
            
            self.config = NodeConfig.from_main_folder(folder)
            
            # Set user_id if provided
            if user_id:
                self.config.config['user_id'] = user_id
                self.config.user_id = user_id
            
            # Get Neo4j credentials from config
            self.neo4j_uri = self.config.config.get('neo4j_uri')
            self.neo4j_user = self.config.config.get('neo4j_user')
            self.neo4j_password = self.config.config.get('neo4j_password')
            
            return True
        except Exception as e:
            print(f"[ERROR] Failed to initialize: {e}")
            return False
    
    def initialize_neo4j(self) -> bool:
        """
        Initialize Neo4j connection and integrate with search.
        
        Returns:
            True if successful, False otherwise
        """
        if not self.config:
            return False
        
        if not all([self.neo4j_uri, self.neo4j_user, self.neo4j_password]):
            print("[WARNING] Neo4j credentials not configured")
            return False
        
        try:
            # Import and integrate Neo4j search
            from neo4j_native_search import integrate_neo4j_search
            integrate_neo4j_search(
                self.config, 
                self.neo4j_uri, 
                self.neo4j_user, 
                self.neo4j_password
            )
            self._neo4j_integrated = True
            return True
        except Exception as e:
            print(f"[ERROR] Failed to initialize Neo4j: {e}")
            return False
    
    def initialize_search(self) -> bool:
        """
        Initialize the search engine.
        
        Returns:
            True if successful, False otherwise
        """
        if not self.config:
            return False
        
        try:
            self.search_engine = NodeSearch(self.config)
            return True
        except Exception as e:
            print(f"[ERROR] Failed to initialize search: {e}")
            return False
    
    def get_neo4j_storage(self):
        """Get or create Neo4j storage instance"""
        if not all([self.neo4j_uri, self.neo4j_user, self.neo4j_password]):
            raise ValueError("Neo4j credentials not configured")
        
        return get_neo4j_storage(self.neo4j_uri, self.neo4j_user, self.neo4j_password)
    
    @property
    def is_ready(self) -> bool:
        """Check if service is ready for operations"""
        return self.config is not None and self.search_engine is not None
    
    @property
    def is_neo4j_connected(self) -> bool:
        """Check if Neo4j is connected"""
        try:
            if not all([self.neo4j_uri, self.neo4j_user, self.neo4j_password]):
                return False
            storage = self.get_neo4j_storage()
            return storage is not None
        except:
            return False


class SearchService:
    """Service for search and Q&A operations"""
    
    def __init__(self, noderag_service: NodeRAGService):
        self.noderag = noderag_service
    
    def search(self, query: str, top_k: int = 10) -> Dict[str, Any]:
        """
        Perform search without generating an answer.
        
        Args:
            query: Search query
            top_k: Number of results to return
            
        Returns:
            Search results dictionary
        """
        if not self.noderag.search_engine:
            raise RuntimeError("Search engine not initialized")
        
        start_time = time.time()
        
        # Temporarily adjust config for top_k
        original_hnsw_results = self.noderag.config.HNSW_results
        self.noderag.config.HNSW_results = top_k
        
        try:
            retrieval = self.noderag.search_engine.search(query)
            
            # Process results
            nodes = []
            for node_id in retrieval.search_list[:top_k]:
                node_info = {
                    "hash_id": node_id,
                    "node_type": retrieval.id_to_type.get(node_id, "unknown"),
                    "text": retrieval.id_to_text.get(node_id, ""),
                    "weight": retrieval.weighted_nodes.get(node_id, 0) if hasattr(retrieval, 'weighted_nodes') else 0
                }
                nodes.append(node_info)
            
            relationships = []
            for rel in retrieval.relationship_list[:top_k]:
                if isinstance(rel, tuple) and len(rel) >= 2:
                    relationships.append({
                        "source": rel[0],
                        "target": rel[1],
                        "type": rel[2] if len(rel) > 2 else "related"
                    })
            
            qa_pairs = []
            if hasattr(retrieval, 'qa_results') and retrieval.qa_results:
                # Sanitize numpy types to Python native types for JSON serialization
                for qa in retrieval.qa_results[:top_k]:
                    sanitized_qa = {}
                    for k, v in qa.items():
                        if hasattr(v, 'item'):  # numpy scalar
                            sanitized_qa[k] = v.item()
                        else:
                            sanitized_qa[k] = v
                    qa_pairs.append(sanitized_qa)
            
            elapsed_time = (time.time() - start_time) * 1000
            
            return {
                "query": query,
                "nodes": nodes,
                "relationships": relationships,
                "qa_pairs": qa_pairs,
                "total_count": len(retrieval.search_list),
                "processing_time_ms": elapsed_time
            }
        finally:
            self.noderag.config.HNSW_results = original_hnsw_results
    
    def answer(self, query: str, job_context: Optional[str] = None) -> Dict[str, Any]:
        """
        Generate an answer for a query.
        
        Args:
            query: The question to answer
            job_context: Optional job description context
            
        Returns:
            Answer with search results
        """
        if not self.noderag.search_engine:
            raise RuntimeError("Search engine not initialized")
        
        start_time = time.time()
        
        result = self.noderag.search_engine.answer(query, job_context=job_context)
        
        # Process search results
        retrieval = result.retrieval
        nodes = []
        for node_id in retrieval.search_list[:20]:
            node_info = {
                "hash_id": node_id,
                "node_type": retrieval.id_to_type.get(node_id, "unknown"),
                "text": retrieval.id_to_text.get(node_id, ""),
                "weight": 0
            }
            nodes.append(node_info)
        
        relationships = []
        for rel in retrieval.relationship_list[:20]:
            if isinstance(rel, tuple) and len(rel) >= 2:
                relationships.append({
                    "source": rel[0],
                    "target": rel[1],
                    "type": rel[2] if len(rel) > 2 else "related"
                })
        
        qa_pairs = []
        if hasattr(retrieval, 'qa_results') and retrieval.qa_results:
            # Sanitize numpy types to Python native types for JSON serialization
            for qa in retrieval.qa_results:
                sanitized_qa = {}
                for k, v in qa.items():
                    if hasattr(v, 'item'):  # numpy scalar
                        sanitized_qa[k] = v.item()
                    else:
                        sanitized_qa[k] = v
                qa_pairs.append(sanitized_qa)
        
        elapsed_time = (time.time() - start_time) * 1000
        
        return {
            "query": query,
            "answer": result.response,
            "nodes": nodes,
            "relationships": relationships,
            "qa_pairs": qa_pairs,
            "total_count": len(retrieval.search_list),
            "processing_time_ms": elapsed_time
        }


class BuildService:
    """Service for build pipeline operations"""
    
    def __init__(self, noderag_service: NodeRAGService):
        self.noderag = noderag_service
        self._build_tasks: Dict[str, Dict[str, Any]] = {}
    
    async def build_graph(
        self, 
        folder_path: Optional[str] = None,
        incremental: bool = True,
        sync_to_neo4j: bool = True,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Build or rebuild the knowledge graph.
        
        Args:
            folder_path: Path to documents folder
            incremental: Whether to do incremental build
            sync_to_neo4j: Sync to Neo4j after build
            user_id: User ID for multi-user support
            
        Returns:
            Build result information
        """
        build_id = str(uuid.uuid4())[:8]
        start_time = time.time()
        
        self._build_tasks[build_id] = {
            "status": "running",
            "current_stage": "initializing",
            "stages_completed": [],
            "started_at": datetime.now()
        }
        
        try:
            # Initialize config
            folder = folder_path or self.noderag.default_folder
            
            # Reset singleton for fresh build
            NodeConfig._instance = None
            
            self.noderag.config = NodeConfig.from_main_folder(folder)
            
            if user_id:
                self.noderag.config.config['user_id'] = user_id
                self.noderag.config.user_id = user_id
            
            # Run build pipeline
            self._build_tasks[build_id]["current_stage"] = "building"
            
            ng = NodeRag(self.noderag.config, web_ui=True)
            ng.run()
            
            self._build_tasks[build_id]["stages_completed"].append("build")
            
            # Sync to Neo4j if requested
            nodes_created = 0
            edges_created = 0
            neo4j_synced = False
            
            if sync_to_neo4j:
                self._build_tasks[build_id]["current_stage"] = "syncing_neo4j"
                
                neo4j_service = Neo4jSyncService(self.noderag)
                sync_result = neo4j_service.sync_to_neo4j(full_sync=not incremental)
                
                if sync_result["success"]:
                    nodes_created = sync_result["nodes_synced"]
                    edges_created = sync_result["relationships_synced"]
                    neo4j_synced = True
                    self._build_tasks[build_id]["stages_completed"].append("neo4j_sync")
            
            duration = time.time() - start_time
            
            self._build_tasks[build_id]["status"] = "completed"
            self._build_tasks[build_id]["current_stage"] = "finished"
            
            return {
                "success": True,
                "build_id": build_id,
                "status": "completed",
                "duration_seconds": duration,
                "nodes_created": nodes_created,
                "edges_created": edges_created,
                "neo4j_synced": neo4j_synced
            }
            
        except Exception as e:
            self._build_tasks[build_id]["status"] = "failed"
            self._build_tasks[build_id]["error"] = str(e)
            
            return {
                "success": False,
                "build_id": build_id,
                "status": "failed",
                "error": str(e),
                "duration_seconds": time.time() - start_time
            }
    
    def get_build_status(self, build_id: str) -> Dict[str, Any]:
        """Get the status of a build operation"""
        if build_id not in self._build_tasks:
            return {"success": False, "error": "Build ID not found"}
        
        return {
            "success": True,
            **self._build_tasks[build_id]
        }


class DocumentService:
    """Service for document management operations"""
    
    def __init__(self, noderag_service: NodeRAGService):
        self.noderag = noderag_service
    
    def get_input_folder(self, user_id: Optional[str] = None) -> str:
        """Get the input folder path for documents"""
        if self.noderag.config:
            if user_id:
                # User-specific folder
                base_folder = self.noderag.config.main_folder
                return os.path.join(base_folder, 'users', f'user_{user_id}', 'input')
            return self.noderag.config.input_folder
        return os.path.join(self.noderag.default_folder, 'input')
    
    def list_documents(self, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List all documents in the input folder.
        
        Args:
            user_id: Optional user ID for multi-user support
            
        Returns:
            List of document information
        """
        input_folder = self.get_input_folder(user_id)
        
        if not os.path.exists(input_folder):
            return []
        
        documents = []
        for filename in os.listdir(input_folder):
            filepath = os.path.join(input_folder, filename)
            if os.path.isfile(filepath) and (filename.endswith('.txt') or filename.endswith('.md')):
                stat = os.stat(filepath)
                documents.append({
                    "filename": filename,
                    "path": filepath,
                    "size_bytes": stat.st_size,
                    "created_at": datetime.fromtimestamp(stat.st_ctime),
                    "document_type": self._infer_document_type(filename),
                    "user_id": user_id
                })
        
        return documents
    
    def _infer_document_type(self, filename: str) -> str:
        """Infer document type from filename"""
        filename_lower = filename.lower()
        if 'resume' in filename_lower or 'cv' in filename_lower:
            return 'resume'
        elif 'job' in filename_lower or 'description' in filename_lower or 'jd' in filename_lower:
            return 'job_description'
        return 'general'
    
    def upload_document(
        self, 
        content: str, 
        filename: str, 
        document_type: str = "general",
        user_id: Optional[str] = None,
        metadata: Dict[str, Any] = {}
    ) -> Dict[str, Any]:
        """
        Upload a new document.
        
        Args:
            content: Document content
            filename: Filename
            document_type: Type of document
            user_id: Optional user ID
            metadata: Additional metadata
            
        Returns:
            Upload result information
        """
        input_folder = self.get_input_folder(user_id)
        
        # Create folder if it doesn't exist
        os.makedirs(input_folder, exist_ok=True)
        
        # Ensure proper file extension
        if not filename.endswith(('.txt', '.md')):
            filename = filename + '.txt'
        
        filepath = os.path.join(input_folder, filename)
        
        # Write content
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        
        stat = os.stat(filepath)
        
        return {
            "success": True,
            "document": {
                "filename": filename,
                "path": filepath,
                "size_bytes": stat.st_size,
                "created_at": datetime.fromtimestamp(stat.st_ctime),
                "document_type": document_type,
                "user_id": user_id
            },
            "requires_rebuild": True
        }
    
    def delete_document(self, filename: str, user_id: Optional[str] = None) -> bool:
        """
        Delete a document.
        
        Args:
            filename: Filename to delete
            user_id: Optional user ID
            
        Returns:
            True if deleted successfully
        """
        input_folder = self.get_input_folder(user_id)
        filepath = os.path.join(input_folder, filename)
        
        if os.path.exists(filepath):
            os.remove(filepath)
            return True
        return False
    
    def update_document(
        self, 
        filename: str, 
        content: str,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Update an existing document.
        
        Args:
            filename: Filename to update
            content: New content
            user_id: Optional user ID
            
        Returns:
            Update result information
        """
        input_folder = self.get_input_folder(user_id)
        filepath = os.path.join(input_folder, filename)
        
        if not os.path.exists(filepath):
            return {"success": False, "error": "Document not found"}
        
        # Backup old file
        backup_folder = os.path.join(input_folder, '..', 'input_backup')
        os.makedirs(backup_folder, exist_ok=True)
        backup_path = os.path.join(backup_folder, f"{filename}.{int(time.time())}.bak")
        shutil.copy2(filepath, backup_path)
        
        # Write new content
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        
        stat = os.stat(filepath)
        
        return {
            "success": True,
            "document": {
                "filename": filename,
                "path": filepath,
                "size_bytes": stat.st_size,
                "updated_at": datetime.now(),
                "user_id": user_id
            },
            "requires_rebuild": True,
            "backup_path": backup_path
        }


class QAService:
    """Service for Q&A node management"""
    
    def __init__(self, noderag_service: NodeRAGService):
        self.noderag = noderag_service
    
    def create_qa_pair(
        self,
        question: str,
        answer: str,
        question_id: Optional[str] = None,
        user_id: Optional[str] = None,
        job_title: Optional[str] = None,
        company_name: Optional[str] = None,
        submission_date: Optional[str] = None,
        sync_to_neo4j: bool = True
    ) -> Dict[str, Any]:
        """
        Create a new Q&A pair and add to graph.
        
        This adds Q&A nodes incrementally without rebuilding the entire graph.
        
        Args:
            question: Question text
            answer: Answer text
            question_id: External question ID
            user_id: Associated user ID
            job_title: Job title context
            company_name: Company name context
            submission_date: Submission date
            sync_to_neo4j: Whether to sync to Neo4j
            
        Returns:
            Created Q&A pair information
        """
        if not self.noderag.config:
            return {"success": False, "error": "Service not initialized"}
        
        try:
            # Create Question node
            question_node = Question(
                raw_context=question,
                question_id=question_id or str(uuid.uuid4())[:8],
                job_title=job_title,
                company_name=company_name,
                submission_date=submission_date
            )
            
            # Create Answer node
            answer_node = Answer(
                raw_context=answer,
                question_id=question_node.question_id
            )
            
            # Add to Neo4j if connected and requested
            added_to_graph = False
            if sync_to_neo4j and self.noderag.is_neo4j_connected:
                try:
                    storage = self.noderag.get_neo4j_storage()
                    
                    # Add Question node
                    with storage.driver.session() as session:
                        session.run("""
                            MERGE (q:Node {id: $id})
                            SET q.type = 'question',
                                q.text = $text,
                                q.question_id = $question_id,
                                q.job_title = $job_title,
                                q.company_name = $company_name,
                                q.submission_date = $submission_date,
                                q.human_readable_id = $human_readable_id,
                                q.weight = 1
                        """, 
                            id=question_node.hash_id,
                            text=question,
                            question_id=question_node.question_id,
                            job_title=job_title,
                            company_name=company_name,
                            submission_date=submission_date,
                            human_readable_id=question_node.human_readable_id
                        )
                        
                        # Add Answer node
                        session.run("""
                            MERGE (a:Node {id: $id})
                            SET a.type = 'answer',
                                a.text = $text,
                                a.question_id = $question_id,
                                a.human_readable_id = $human_readable_id,
                                a.weight = 1
                        """,
                            id=answer_node.hash_id,
                            text=answer,
                            question_id=question_node.question_id,
                            human_readable_id=answer_node.human_readable_id
                        )
                        
                        # Create relationship
                        session.run("""
                            MATCH (q:Node {id: $q_id})
                            MATCH (a:Node {id: $a_id})
                            MERGE (q)-[r:CONNECTED_TO]->(a)
                            SET r.type = 'has_answer', r.weight = 1
                        """,
                            q_id=question_node.hash_id,
                            a_id=answer_node.hash_id
                        )
                    
                    added_to_graph = True
                except Exception as e:
                    print(f"[WARNING] Failed to add to Neo4j: {e}")
            
            return {
                "success": True,
                "question_hash_id": question_node.hash_id,
                "answer_hash_id": answer_node.hash_id,
                "question": question,
                "answer": answer,
                "added_to_graph": added_to_graph
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def list_qa_pairs(self, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List all Q&A pairs from Neo4j.
        
        Args:
            user_id: Optional filter by user ID
            
        Returns:
            List of Q&A pairs
        """
        if not self.noderag.is_neo4j_connected:
            return []
        
        try:
            storage = self.noderag.get_neo4j_storage()
            
            with storage.driver.session() as session:
                result = session.run("""
                    MATCH (q:Node {type: 'question'})-[:CONNECTED_TO]->(a:Node {type: 'answer'})
                    RETURN q.id AS question_hash_id, 
                           q.text AS question,
                           q.question_id AS question_id,
                           q.job_title AS job_title,
                           q.company_name AS company_name,
                           a.id AS answer_hash_id,
                           a.text AS answer
                """)
                
                qa_pairs = []
                for record in result:
                    qa_pairs.append({
                        "question_hash_id": record["question_hash_id"],
                        "answer_hash_id": record["answer_hash_id"],
                        "question": record["question"],
                        "answer": record["answer"],
                        "question_id": record["question_id"],
                        "job_title": record["job_title"],
                        "company_name": record["company_name"]
                    })
                
                return qa_pairs
        except Exception as e:
            print(f"[ERROR] Failed to list Q&A pairs: {e}")
            return []
    
    def delete_qa_pair(self, question_hash_id: str) -> bool:
        """
        Delete a Q&A pair from Neo4j.
        
        Args:
            question_hash_id: Hash ID of the question node
            
        Returns:
            True if deleted successfully
        """
        if not self.noderag.is_neo4j_connected:
            return False
        
        try:
            storage = self.noderag.get_neo4j_storage()
            
            with storage.driver.session() as session:
                # Delete question, answer, and relationship
                session.run("""
                    MATCH (q:Node {id: $q_id})
                    OPTIONAL MATCH (q)-[:CONNECTED_TO]->(a:Node {type: 'answer'})
                    DETACH DELETE q, a
                """, q_id=question_hash_id)
            
            return True
        except Exception as e:
            print(f"[ERROR] Failed to delete Q&A pair: {e}")
            return False


class Neo4jSyncService:
    """Service for Neo4j synchronization operations"""
    
    def __init__(self, noderag_service: NodeRAGService):
        self.noderag = noderag_service
    
    def sync_to_neo4j(self, full_sync: bool = False) -> Dict[str, Any]:
        """
        Sync the graph to Neo4j.
        
        Args:
            full_sync: If True, clears Neo4j first. If False, does incremental sync.
            
        Returns:
            Sync result information
        """
        if not self.noderag.config:
            return {"success": False, "error": "Service not initialized"}
        
        if not self.noderag.is_neo4j_connected:
            return {"success": False, "error": "Neo4j not connected"}
        
        start_time = time.time()
        
        try:
            from NodeRAG.storage import storage
            import pickle
            
            # Load graph from pickle
            graph_path = self.noderag.config.base_graph_path
            if not os.path.exists(graph_path):
                return {"success": False, "error": "Graph file not found. Run build first."}
            
            with open(graph_path, 'rb') as f:
                graph = pickle.load(f)
            
            storage_obj = self.noderag.get_neo4j_storage()
            
            if full_sync:
                # Clear and rebuild
                storage_obj.clear_database()
                storage_obj.save_graph(graph, batch_size=1000)
            else:
                # Incremental sync - add new nodes/edges
                # This is a simplified implementation
                storage_obj.save_graph(graph, batch_size=1000)
            
            stats = storage_obj.get_statistics()
            duration = time.time() - start_time
            
            return {
                "success": True,
                "nodes_synced": stats['total_nodes'],
                "relationships_synced": stats['total_relationships'],
                "duration_seconds": duration,
                "sync_type": "full" if full_sync else "incremental"
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def get_neo4j_stats(self) -> Dict[str, Any]:
        """
        Get Neo4j database statistics.
        
        Returns:
            Database statistics
        """
        if not self.noderag.is_neo4j_connected:
            return {"success": False, "error": "Neo4j not connected"}
        
        try:
            storage = self.noderag.get_neo4j_storage()
            stats = storage.get_statistics()
            
            return {
                "success": True,
                "total_nodes": stats['total_nodes'],
                "total_relationships": stats['total_relationships'],
                "node_types": stats['node_types'],
                "connected": True
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def clear_neo4j(self) -> bool:
        """Clear all data from Neo4j"""
        if not self.noderag.is_neo4j_connected:
            return False
        
        try:
            storage = self.noderag.get_neo4j_storage()
            storage.clear_database()
            return True
        except:
            return False


# Create singleton service instances
noderag_service = NodeRAGService()
search_service = SearchService(noderag_service)
build_service = BuildService(noderag_service)
document_service = DocumentService(noderag_service)
qa_service = QAService(noderag_service)
neo4j_service = Neo4jSyncService(noderag_service)
