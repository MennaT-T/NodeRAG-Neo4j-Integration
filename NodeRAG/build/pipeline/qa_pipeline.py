"""
Q&A Pipeline: Creates Question and Answer nodes from backend API
"""
import networkx as nx
from typing import List, Dict, Optional
import os
import json
import asyncio
import numpy as np
import sys
import hnswlib_noderag

from ...config import NodeConfig
from ...build.component import Question, Answer
from ...utils.qa_api_client import QAAPIClient
from ...storage import storage
from ...LLM import Embedding_message
from ...logging import info_timer

class QA_Pipeline:
    """Pipeline for creating Question and Answer nodes from API"""
    
    def __init__(self, config: NodeConfig, api_client: Optional[QAAPIClient] = None):
        self.config = config
        self.api_client = api_client
        self.storage_obj = storage
        self.G = None  # Graph loaded in main()
        self.question_hnsw_path = os.path.join(self.config.cache, 'question_hnsw.bin')
        self.question_id_map_path = os.path.join(self.config.cache, 'question_id_map.parquet')
        self.questions = []  # Track Question nodes
        self.answers = []  # Track Answer nodes
    
    @info_timer(message='Q&A Pipeline')
    async def main(self) -> nx.DiGraph:
        """
        Main pipeline method: Create Q&A nodes and add to graph
        
        Returns:
            Updated graph with Q&A nodes
        """
        # Load existing graph
        if os.path.exists(self.config.graph_path):
            self.G = self.storage_obj.load_pickle(self.config.graph_path)
        else:
            self.G = nx.DiGraph()
        
        # Skip if no API client provided
        if not self.api_client:
            self.config.console.print('[yellow][DEBUG QA Pipeline] No API client provided, skipping[/yellow]')
            return self.G
        
        # Get user_id from config.qa_api (not top-level config.user_id which is for multi-user folder routing)
        user_id = self.config.qa_api.get('user_id', None) if hasattr(self.config, 'qa_api') else None
        self.config.console.print(f'[yellow][DEBUG QA Pipeline] user_id: {user_id}[/yellow]')
        if not user_id:
            # No user_id means no Q&A data to load
            self.config.console.print('[yellow][DEBUG QA Pipeline] No user_id in qa_api config, skipping[/yellow]')
            return self.G
        
        try:
            # Get Q&A pairs for user from API
            self.config.console.print(f'[yellow][DEBUG QA Pipeline] Fetching Q&A pairs for user {user_id}...[/yellow]')
            qa_pairs = self.api_client.get_qa_pairs_by_user(str(user_id))
            self.config.console.print(f'[yellow][DEBUG QA Pipeline] Retrieved {len(qa_pairs) if qa_pairs else 0} Q&A pairs[/yellow]')
            
            if not qa_pairs:
                self.config.console.print('[yellow]No Q&A pairs found for user[/yellow]')
                return self.G
            
            self.config.console.print(f'[green]Found {len(qa_pairs)} Q&A pairs for user {user_id}[/green]')
            
            # Create Q&A nodes and generate embeddings
            question_nodes_data = []
            question_texts = []
            question_hash_ids = []
            
            self.config.console.print(f'[yellow][DEBUG] Processing {len(qa_pairs)} Q&A pairs...[/yellow]')
            print(f'[QA Pipeline] Processing {len(qa_pairs)} Q&A pairs...')  # Use print() so it persists
            sys.stdout.flush()
            
            for idx, qa in enumerate(qa_pairs):
                print(f'[QA Pipeline] Processing Q&A pair {idx+1}/{len(qa_pairs)}')  # Use print() so it persists
                sys.stdout.flush()
                
                # Create Question node
                question_node = Question(
                    raw_context=qa['question'],
                    question_id=str(qa['question_id']),
                    job_title=qa.get('job_title'),
                    company_name=qa.get('company_name'),
                    submission_date=qa.get('submission_date')
                )
                
                # Create Answer node
                answer_node = Answer(
                    raw_context=qa['answer'],
                    question_id=str(qa['question_id'])
                )
                
                # Add Question node to graph
                if self.G.has_node(question_node.hash_id):
                    # Node already exists, increment weight
                    self.G.nodes[question_node.hash_id]['weight'] += 1
                    self.config.console.print(f'[yellow][DEBUG] Question node {idx+1} already exists, incrementing weight[/yellow]')
                else:
                    self.G.add_node(
                        question_node.hash_id,
                        type='question',
                        text=question_node.raw_context,
                        question_id=question_node.question_id,
                        job_title=question_node.job_title,
                        company_name=question_node.company_name,
                        submission_date=question_node.submission_date,
                        embedding=None,  # Will be set after embedding generation
                        human_readable_id=question_node.human_readable_id,
                        weight=1
                    )
                    # Only track new nodes
                    self.questions.append(question_node)
                    self.config.console.print(f'[yellow][DEBUG] Added new question node {idx+1} to graph and list (total questions: {len(self.questions)})[/yellow]')
                
                # Add Answer node to graph
                if self.G.has_node(answer_node.hash_id):
                    # Node already exists, increment weight
                    self.G.nodes[answer_node.hash_id]['weight'] += 1
                    self.config.console.print(f'[yellow][DEBUG] Answer node {idx+1} already exists, incrementing weight[/yellow]')
                else:
                    self.G.add_node(
                        answer_node.hash_id,
                        type='answer',
                        text=answer_node.raw_context,
                        question_id=answer_node.question_id,
                        human_readable_id=answer_node.human_readable_id,
                        weight=1
                    )
                    # Only track new nodes
                    self.answers.append(answer_node)
                    self.config.console.print(f'[yellow][DEBUG] Added new answer node {idx+1} to graph and list (total answers: {len(self.answers)})[/yellow]')
                
                # Add relationship: Question ΓåÆ Answer
                self.G.add_edge(
                    question_node.hash_id,
                    answer_node.hash_id,
                    type='has_answer',
                    weight=1  # Add weight attribute for graph operations
                )
                
                # Store for embedding generation
                question_texts.append(qa['question'])
                question_hash_ids.append(question_node.hash_id)
                print(f'[QA Pipeline] Completed processing pair {idx+1}/{len(qa_pairs)}')  # Use print() so it persists
                sys.stdout.flush()
            
            print(f'[QA Pipeline] Loop completed. Processed {len(question_hash_ids)} questions')  # Use print() so it persists
            sys.stdout.flush()
            
            # Generate embeddings for all questions
            print(f'[QA Pipeline] About to generate embeddings. question_texts: {len(question_texts)}, embedding_client: {self.config.embedding_client is not None}')  # Use print() so it persists
            sys.stdout.flush()
            if question_texts and self.config.embedding_client:
                print(f'[QA Pipeline] Generating embeddings for {len(question_texts)} questions...')  # Use print() so it persists
                sys.stdout.flush()
                embeddings = await self._generate_embeddings(question_texts, question_hash_ids)
                print(f'[QA Pipeline] Generated {len(embeddings) if embeddings else 0} embeddings')  # Use print() so it persists
                sys.stdout.flush()
                
                # Validate embeddings format
                if embeddings:
                    print(f'[QA Pipeline] Validating embeddings... First embedding type: {type(embeddings[0]) if embeddings else None}')  # Use print() so it persists
                    if len(embeddings) != len(question_hash_ids):
                        print(f'[QA Pipeline] WARNING: Mismatch - {len(question_hash_ids)} questions but {len(embeddings)} embeddings')  # Use print() so it persists
                    sys.stdout.flush()
                    
                    # Update graph nodes with embeddings
                    for idx, (hash_id, embedding) in enumerate(zip(question_hash_ids, embeddings)):
                        # Ensure embedding is a numpy array
                        if isinstance(embedding, (list, tuple)):
                            try:
                                embedding = np.array(embedding, dtype=np.float32)
                            except (ValueError, TypeError) as e:
                                print(f'[QA Pipeline] ERROR: Failed to convert embedding {idx} to numpy array: {e}')  # Use print() so it persists
                                print(f'[QA Pipeline] Embedding type: {type(embedding)}, value: {embedding[:50] if hasattr(embedding, "__getitem__") else embedding}')  # Use print() so it persists
                                sys.stdout.flush()
                                continue
                        elif isinstance(embedding, np.ndarray):
                            embedding = embedding.astype(np.float32)
                        else:
                            print(f'[QA Pipeline] ERROR: Invalid embedding type for {hash_id}: {type(embedding)}, value: {str(embedding)[:100]}')  # Use print() so it persists
                            sys.stdout.flush()
                            continue
                        
                        # Validate embedding is numeric
                        if embedding.dtype.kind not in 'fc':  # float or complex
                            print(f'[QA Pipeline] ERROR: Embedding {idx} is not numeric: dtype={embedding.dtype}')  # Use print() so it persists
                            sys.stdout.flush()
                            continue
                        
                        self.G.nodes[hash_id]['embedding'] = embedding
                        question_nodes_data.append({
                            'hash_id': hash_id,
                            'embedding': embedding
                        })
                    
                    # Build HNSW index for Question nodes
                    if question_nodes_data:
                        print(f'[QA Pipeline] Building HNSW index for {len(question_nodes_data)} questions...')  # Use print() so it persists
                        sys.stdout.flush()
                        await self._build_question_hnsw_index(question_nodes_data)
                        print(f'[QA Pipeline] HNSW index built successfully')  # Use print() so it persists
                        sys.stdout.flush()
            else:
                print(f'[QA Pipeline] Skipping embedding generation (question_texts: {len(question_texts)}, embedding_client: {self.config.embedding_client is not None})')  # Use print() so it persists
                sys.stdout.flush()
            
            # Save updated graph
            self.storage_obj(self.G).save_pickle(self.config.graph_path)
            
            # Count nodes in graph before saving
            question_count = len([n for n in self.G.nodes() if self.G.nodes[n].get('type') == 'question'])
            answer_count = len([n for n in self.G.nodes() if self.G.nodes[n].get('type') == 'answer'])
            print(f'[QA Pipeline] Graph has {question_count} question nodes, {answer_count} answer nodes')  # Use print() so it persists
            sys.stdout.flush()
            
            # Save questions and answers to parquet files
            # Always save (saves ALL nodes from graph, not just new ones)
            print(f'[QA Pipeline] Calling save() method...')  # Use print() so it persists
            sys.stdout.flush()
            self.save()
            print(f'[QA Pipeline] save() completed')  # Use print() so it persists
            sys.stdout.flush()
            
            self.config.console.print(f'[green]Q&A Pipeline: Added {len(question_hash_ids)} Question nodes and {len(question_hash_ids)} Answer nodes[/green]')
            
        except Exception as e:
            # Log error but don't fail the entire build
            print(f'[QA Pipeline] EXCEPTION CAUGHT: {e}')  # Use print() so it persists
            sys.stdout.flush()
            import traceback
            print(f'[QA Pipeline] Traceback: {traceback.format_exc()}')  # Use print() so it persists
            sys.stdout.flush()
            self.config.console.print(f'[red]Warning: Failed to load Q&A nodes: {e}[/red]')
            return self.G
        
        return self.G
    
    async def _generate_embeddings(self, texts: List[str], hash_ids: List[str]) -> List[List[float]]:
        """Generate embeddings for question texts - matches embedding.py pattern exactly"""
        if not self.config.embedding_client:
            raise ValueError("Embedding client not configured")
        
        # Generate embeddings in batches - EXACTLY like embedding.py does it
        batch_size = getattr(self.config, 'embedding_batch_size', 100)
        all_embeddings = []
        
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i + batch_size]
            batch_hash_ids = hash_ids[i:i + batch_size]
            
            # Create context_dict exactly like embedding.py: Dict[str, Embedding_message]
            # Keys are hash_ids, values are Embedding_message objects
            context_dict = {}
            for hash_id, text in zip(batch_hash_ids, batch_texts):
                context_dict[hash_id] = Embedding_message(input=text)
            
            # Extract embedding_input as list of Embedding_message objects (matching embedding.py line 47)
            embedding_input = list(context_dict.values())
            ids = list(context_dict.keys())
            
            # Call embedding_client exactly like embedding.py does (line 51)
            # embedding.py passes a list of Embedding_message objects
            embedding_output = await self.config.embedding_client(
                embedding_input,
                cache_path=self.config.LLM_error_cache,
                meta_data={'ids': ids}
            )
            
            print(f'[QA Pipeline] DEBUG: embedding_client returned type: {type(embedding_output)}, length: {len(embedding_output) if hasattr(embedding_output, "__len__") else "N/A"}')  # Use print() so it persists
            sys.stdout.flush()
            
            if embedding_output == 'Error cached':
                raise Exception("Error cached during embedding generation")
            
            # Check if we got an error string (from error_handler_async)
            if isinstance(embedding_output, str):
                print(f'[QA Pipeline] ERROR: Received error string from embedding client: {embedding_output}')  # Use print() so it persists
                sys.stdout.flush()
                # Check error log file for details
                if os.path.exists(self.config.LLM_error_cache):
                    print(f'[QA Pipeline] Checking error log: {self.config.LLM_error_cache}')  # Use print() so it persists
                    sys.stdout.flush()
                    try:
                        with open(self.config.LLM_error_cache, 'r', encoding='utf-8') as f:
                            lines = f.readlines()
                            if lines:
                                print(f'[QA Pipeline] Last error log entry: {lines[-1][:500]}')  # Use print() so it persists
                                sys.stdout.flush()
                    except Exception as e:
                        print(f'[QA Pipeline] Could not read error log: {e}')  # Use print() so it persists
                        sys.stdout.flush()
                raise ValueError(f"Embedding client returned error: {embedding_output}")
            
            # embedding_output is a list where embedding_output[i] corresponds to ids[i]
            # This matches embedding.py line 60: embedding_output[i]
            if isinstance(embedding_output, list):
                all_embeddings.extend(embedding_output)
            else:
                print(f'[QA Pipeline] ERROR: embedding_output is not a list: {type(embedding_output)}, value: {str(embedding_output)[:200]}')  # Use print() so it persists
                sys.stdout.flush()
                raise ValueError(f"Expected list of embeddings, got {type(embedding_output)}")
        
        return all_embeddings
    
    async def _build_question_hnsw_index(self, question_nodes_data: List[Dict]):
        """Build separate HNSW index for Question nodes"""
        if not question_nodes_data:
            return
        
        # Extract embeddings and hash_ids with validation
        embedding_list = []
        hash_ids = []
        
        for node in question_nodes_data:
            embedding = node.get('embedding')
            if embedding is None:
                print(f'[QA Pipeline] WARNING: Node {node.get("hash_id")} has no embedding, skipping')
                continue
            
            # Convert to numpy array if needed
            if isinstance(embedding, (list, tuple)):
                embedding = np.array(embedding, dtype=np.float32)
            elif isinstance(embedding, np.ndarray):
                embedding = embedding.astype(np.float32)
            else:
                print(f'[QA Pipeline] ERROR: Invalid embedding type for node {node.get("hash_id")}: {type(embedding)}')
                print(f'[QA Pipeline] Embedding value: {embedding}')
                continue
            
            # Validate embedding shape
            if embedding.ndim != 1:
                print(f'[QA Pipeline] ERROR: Embedding for node {node.get("hash_id")} has wrong shape: {embedding.shape}')
                continue
            
            embedding_list.append(embedding)
            hash_ids.append(node['hash_id'])
        
        if not embedding_list:
            print('[QA Pipeline] ERROR: No valid embeddings found, cannot build HNSW index')
            return
        
        # Convert to numpy array
        embeddings = np.array(embedding_list, dtype=np.float32)
        
        print(f'[QA Pipeline] Building HNSW index with {len(embeddings)} embeddings, shape: {embeddings.shape}')
        sys.stdout.flush()
        
        # Load existing index if it exists
        if os.path.exists(self.question_hnsw_path):
            # Load existing index
            dim = self.config.dim  # Use config dimension for consistency
            hnsw_index = hnswlib_noderag.Index(space='cosine', dim=dim)
            hnsw_index.load_index(self.question_hnsw_path)
            
            # Load existing id_map
            if os.path.exists(self.question_id_map_path):
                id_map_data = self.storage_obj.load(self.question_id_map_path)
                id_map = dict(zip(id_map_data['id'], id_map_data['node']))
            else:
                id_map = {}
            
            # Add new nodes
            current_length = len(id_map)
            new_id_list = []
            for idx, hash_id in enumerate(hash_ids):
                new_id = current_length + idx
                id_map[new_id] = hash_id
                new_id_list.append(new_id)
            
            # Resize and add items
            hnsw_index.resize_index(len(id_map))
            hnsw_index.add_items(embeddings, new_id_list)
        else:
            # Create new index
            dim = self.config.dim  # Use config dimension for consistency
            hnsw_index = hnswlib_noderag.Index(space='cosine', dim=dim)
            hnsw_index.init_index(
                max_elements=len(question_nodes_data),
                ef_construction=self.config._ef,
                M=self.config._m
            )
            
            # Create id_map
            id_map = {i: hash_ids[i] for i in range(len(hash_ids))}
            
            # Add embeddings
            hnsw_index.add_items(embeddings, list(range(len(hash_ids))))
        
        # Save index and id_map
        hnsw_index.save_index(self.question_hnsw_path)
        self.storage_obj({'id': list(id_map.keys()), 'node': list(id_map.values())}).save_parquet(self.question_id_map_path)
        
        self.config.console.print(f'[green]Question HNSW index built and saved[/green]')
    
    def save_questions(self):
        """Save Question nodes to parquet file - saves ALL question nodes from graph"""
        questions = []
        # Get all question nodes from the graph (not just new ones)
        question_nodes_in_graph = [node_id for node_id in self.G.nodes() if self.G.nodes[node_id].get('type') == 'question']
        
        for node_id in question_nodes_in_graph:
            node_data = self.G.nodes[node_id]
            questions.append({
                'hash_id': node_id,
                'human_readable_id': node_data.get('human_readable_id'),
                'type': 'question',
                'context': node_data.get('text', ''),
                'question_id': node_data.get('question_id'),
                'job_title': node_data.get('job_title'),
                'company_name': node_data.get('company_name'),
                'submission_date': node_data.get('submission_date'),
                'embedding': node_data.get('embedding'),
                'weight': node_data.get('weight', 0)
            })
        return questions
    
    def save_answers(self):
        """Save Answer nodes to parquet file - saves ALL answer nodes from graph"""
        answers = []
        # Get all answer nodes from the graph (not just new ones)
        answer_nodes_in_graph = [node_id for node_id in self.G.nodes() if self.G.nodes[node_id].get('type') == 'answer']
        
        for node_id in answer_nodes_in_graph:
            node_data = self.G.nodes[node_id]
            answers.append({
                'hash_id': node_id,
                'human_readable_id': node_data.get('human_readable_id'),
                'type': 'answer',
                'context': node_data.get('text', ''),
                'question_id': node_data.get('question_id'),
                'weight': node_data.get('weight', 0)
            })
        return answers
    
    def save(self):
        """Save questions and answers to parquet files - saves ALL nodes from graph"""
        try:
            print(f'[QA Pipeline] save() method called')  # Use print() so it persists
            sys.stdout.flush()
            
            questions = self.save_questions()
            answers = self.save_answers()
            
            print(f'[QA Pipeline] Found {len(questions)} question nodes in graph (for saving)')  # Use print() so it persists
            print(f'[QA Pipeline] Found {len(answers)} answer nodes in graph (for saving)')  # Use print() so it persists
            print(f'[QA Pipeline] Saving questions to {self.config.questions_path}')  # Use print() so it persists
            print(f'[QA Pipeline] Saving answers to {self.config.answers_path}')  # Use print() so it persists
            sys.stdout.flush()
            
            self.config.console.print(f'[yellow][DEBUG] Found {len(questions)} question nodes in graph[/yellow]')
            self.config.console.print(f'[yellow][DEBUG] Found {len(answers)} answer nodes in graph[/yellow]')
            self.config.console.print(f'[yellow][DEBUG] Saving to {self.config.questions_path}[/yellow]')
            self.config.console.print(f'[yellow][DEBUG] Saving to {self.config.answers_path}[/yellow]')
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.config.questions_path), exist_ok=True)
            os.makedirs(os.path.dirname(self.config.answers_path), exist_ok=True)
            
            # Always overwrite (not append) to ensure consistency with graph
            # The graph is the source of truth
            if questions:
                print(f'[QA Pipeline] About to save {len(questions)} questions to parquet...')  # Use print() so it persists
                print(f'[QA Pipeline] Questions path: {self.config.questions_path}')  # Use print() so it persists
                print(f'[QA Pipeline] Questions directory exists: {os.path.exists(os.path.dirname(self.config.questions_path))}')  # Use print() so it persists
                sys.stdout.flush()
                try:
                    self.storage_obj(questions).save_parquet(self.config.questions_path)
                    print(f'[QA Pipeline] Successfully saved {len(questions)} questions to parquet')  # Use print() so it persists
                    print(f'[QA Pipeline] File exists after save: {os.path.exists(self.config.questions_path)}')  # Use print() so it persists
                    sys.stdout.flush()
                    self.config.console.print(f'[green]Saved {len(questions)} questions to parquet[/green]')
                except Exception as save_error:
                    print(f'[QA Pipeline] ERROR saving questions: {save_error}')  # Use print() so it persists
                    import traceback
                    print(f'[QA Pipeline] Questions save traceback: {traceback.format_exc()}')  # Use print() so it persists
                    sys.stdout.flush()
                    raise
            else:
                print('[QA Pipeline] No questions to save')  # Use print() so it persists
                sys.stdout.flush()
                self.config.console.print('[yellow]No questions to save[/yellow]')
            
            if answers:
                print(f'[QA Pipeline] About to save {len(answers)} answers to parquet...')  # Use print() so it persists
                print(f'[QA Pipeline] Answers path: {self.config.answers_path}')  # Use print() so it persists
                print(f'[QA Pipeline] Answers directory exists: {os.path.exists(os.path.dirname(self.config.answers_path))}')  # Use print() so it persists
                sys.stdout.flush()
                try:
                    self.storage_obj(answers).save_parquet(self.config.answers_path)
                    print(f'[QA Pipeline] Successfully saved {len(answers)} answers to parquet')  # Use print() so it persists
                    print(f'[QA Pipeline] File exists after save: {os.path.exists(self.config.answers_path)}')  # Use print() so it persists
                    sys.stdout.flush()
                    self.config.console.print(f'[green]Saved {len(answers)} answers to parquet[/green]')
                except Exception as save_error:
                    print(f'[QA Pipeline] ERROR saving answers: {save_error}')  # Use print() so it persists
                    import traceback
                    print(f'[QA Pipeline] Answers save traceback: {traceback.format_exc()}')  # Use print() so it persists
                    sys.stdout.flush()
                    raise
            else:
                print('[QA Pipeline] No answers to save')  # Use print() so it persists
                sys.stdout.flush()
                self.config.console.print('[yellow]No answers to save[/yellow]')
            
            print('[QA Pipeline] save() method completed successfully')  # Use print() so it persists
            sys.stdout.flush()
            self.config.console.print('[green]Questions and answers stored[/green]')
        except Exception as e:
            print(f'[QA Pipeline] ERROR in save(): {e}')  # Use print() so it persists
            sys.stdout.flush()
            import traceback
            print(f'[QA Pipeline] Traceback in save(): {traceback.format_exc()}')  # Use print() so it persists
            sys.stdout.flush()
            self.config.console.print(f'[red]Error saving questions/answers: {e}[/red]')
            self.config.console.print(f'[red]Traceback: {traceback.format_exc()}[/red]')
            raise

