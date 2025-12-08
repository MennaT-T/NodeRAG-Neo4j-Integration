import os
from typing import Dict,List,Tuple,Optional
import numpy as np
import re
import hnswlib_noderag


from ..storage import Mapper
from ..utils import HNSW
from ..storage import storage
from ..utils.graph_operator import GraphConcat
from ..config import NodeConfig
from ..utils.PPR import sparse_PPR
from .Answer_base import Answer,Retrieval




class NodeSearch():

    def __init__(self,config:NodeConfig):
        

        self.config = config
        self.hnsw = self.load_hnsw()
        self.mapper = self.load_mapper()
        self.G = self.load_graph()
        self.id_to_type = {id:self.G.nodes[id].get('type') for id in self.G.nodes}
        self.id_to_text,self.accurate_id_to_text = self.mapper.generate_id_to_text(['entity','high_level_element_title'])
        
        # Note: Q&A nodes (question and answer) are now included in the mapper via questions.parquet and answers.parquet
        # No need for workaround - they're loaded automatically through load_mapper()
        
        self.sparse_PPR = sparse_PPR(self.G)
        self._semantic_units = None
        # Load Question HNSW index if available (Phase 2)
        self.question_hnsw = None
        self.question_id_map = {}
        self._load_question_hnsw_index()
            
        
    def load_mapper(self) -> Mapper:
        
        mapping_list = [self.config.semantic_units_path,
                        self.config.entities_path,
                        self.config.relationship_path,
                        self.config.attributes_path,
                        self.config.high_level_elements_path,
                        self.config.text_path,
                        self.config.high_level_elements_titles_path]
        
        # Phase 2: Add Q&A parquet files to mapper (optional - don't fail if they don't exist)
        if hasattr(self.config, 'questions_path') and os.path.exists(self.config.questions_path):
            mapping_list.append(self.config.questions_path)
        if hasattr(self.config, 'answers_path') and os.path.exists(self.config.answers_path):
            mapping_list.append(self.config.answers_path)
        
        # Check required files (original parquet files)
        required_files = [self.config.semantic_units_path,
                         self.config.entities_path,
                         self.config.relationship_path,
                         self.config.attributes_path,
                         self.config.high_level_elements_path,
                         self.config.text_path,
                         self.config.high_level_elements_titles_path]
        
        for path in required_files:
            if not os.path.exists(path):
                raise Exception(f'{path} not found, Please check cache integrity. You may need to rebuild the database due to the loss of cache files.')
        
        mapper = Mapper(mapping_list)
        
        return mapper
    
    def load_hnsw(self) -> HNSW:
        if os.path.exists(self.config.HNSW_path):
            hnsw = HNSW(self.config)
            hnsw.load_HNSW()
            return hnsw
        else:
            raise Exception('No HNSW data found.')
    
    def _load_question_hnsw_index(self):
        """Load Question HNSW index and id_map if available (Phase 2)"""
        hnsw_exists = os.path.exists(self.config.question_hnsw_path)
        id_map_exists = os.path.exists(self.config.question_id_map_path)
        
        if hnsw_exists and id_map_exists:
            try:
                # Load Question HNSW index
                dim = self.config.dim
                self.question_hnsw = hnswlib_noderag.Index(space='cosine', dim=dim)
                self.question_hnsw.load_index(self.config.question_hnsw_path)
                self.question_hnsw.set_ef(50)  # Set ef parameter for search
                
                # Load Question id_map
                id_map_data = storage.load(self.config.question_id_map_path)
                self.question_id_map = dict(zip(id_map_data['id'], id_map_data['node']))  # Maps HNSW id -> node hash_id
            except Exception as e:
                # If loading fails, disable Q&A search (don't break regular search)
                import sys
                print(f"[WARNING] Failed to load Question HNSW index: {e}", file=sys.stderr)
                self.question_hnsw = None
                self.question_id_map = {}
        else:
            # Files don't exist - this is expected if QA pipeline hasn't run
            self.question_hnsw = None
            self.question_id_map = {}
        
    def load_graph(self):
        
        if os.path.exists(self.config.base_graph_path):
            G = storage.load(self.config.base_graph_path)
        else:
            raise Exception('No base graph found.')
        
        if os.path.exists(self.config.hnsw_graph_path):
            HNSW_graph = storage.load(self.config.hnsw_graph_path)
        else:
            raise Exception('No HNSW graph found.')
        
        if self.config.unbalance_adjust:
                G = GraphConcat(G).concat(HNSW_graph)
                return GraphConcat.unbalance_adjust(G)
            
        return GraphConcat(G).concat(HNSW_graph)
        
    
    def search(self,query:str):
        
        retrieval = Retrieval(self.config,self.id_to_text,self.accurate_id_to_text,self.id_to_type)
        

        # HNSW search for enter points by cosine similarity
        query_embedding = np.array(self.config.embedding_client.request(query),dtype=np.float32)
        HNSW_results = self.hnsw.search(query_embedding,HNSW_results=self.config.HNSW_results)
        retrieval.HNSW_results_with_distance = HNSW_results
        
        
        
        # Decompose query into entities and accurate search for short words level items.
        decomposed_entities = self.decompose_query(query)
        
        accurate_results = self.accurate_search(decomposed_entities)
        retrieval.accurate_results = accurate_results
        
        # Personlization for graph search
        personlization = {ids:self.config.similarity_weight for ids in retrieval.HNSW_results}
        personlization.update({id:self.config.accuracy_weight for id in retrieval.accurate_results})
        
        # Phase 2: Q&A semantic search (if Question HNSW index exists)
        if self.question_hnsw is not None and len(self.question_id_map) > 0:
            print(f"[DEBUG Q&A Search] Starting Q&A search with query_embedding shape: {query_embedding.shape}")
            qa_top_k = getattr(self.config, 'qa_top_k', 3)  # Get configurable top_k (default: 3)
            print(f"[DEBUG Q&A Search] Using top_k={qa_top_k} (configurable)")
            qa_results = self._search_qa_pairs(query_embedding, top_k=qa_top_k)
            print(f"[DEBUG Q&A Search] _search_qa_pairs returned {len(qa_results)} results")
            
            # Boost Q&A nodes in PageRank personalization (only if similarity >= threshold)
            qa_similarity_threshold = getattr(self.config, 'qa_similarity_threshold', 0.6)
            boosted_count = 0
            for qa_pair in qa_results:  # Check all returned Q&A pairs
                similarity = qa_pair.get('similarity', 0.0)
                
                # Only boost Q&A pairs that meet the similarity threshold
                if similarity >= qa_similarity_threshold:
                    question_hash_id = qa_pair['question_hash_id']
                    answer_hash_id = qa_pair['answer_hash_id']
                    
                    # Add Q&A nodes to personalization with boost
                    boost = self.config.similarity_weight * 1.2  # 20% boost for Q&A nodes
                    if question_hash_id:
                        personlization[question_hash_id] = personlization.get(question_hash_id, 0) + boost
                    if answer_hash_id:
                        personlization[answer_hash_id] = personlization.get(answer_hash_id, 0) + boost
                    boosted_count += 1
                else:
                    print(f"[DEBUG Q&A Search] Skipping boost for Q&A pair (similarity {similarity:.3f} < threshold {qa_similarity_threshold:.3f})")
            
            print(f"[DEBUG Q&A Search] Boosted {boosted_count}/{len(qa_results)} Q&A pairs (threshold: {qa_similarity_threshold:.3f})")
            
            # Store Q&A results in retrieval for potential use in answer generation
            retrieval.qa_results = qa_results
            print(f"[DEBUG Q&A Search] Stored {len(qa_results)} Q&A results in retrieval")
        
        weighted_nodes = self.graph_search(personlization)
        
        retrieval = self.post_process_top_k(weighted_nodes,retrieval)

        return retrieval

    def decompose_query(self,query:str):
        import json
        
        query = self.config.prompt_manager.decompose_query.format(query=query)
        response = self.config.API_client.request({'query':query,'response_format':self.config.prompt_manager.decomposed_text_json})
        
        # Handle case where response is a string instead of dict
        if isinstance(response, str):
            try:
                response = json.loads(response)
            except json.JSONDecodeError:
                # If JSON parsing fails, return empty list
                print(f"Warning: Could not parse response as JSON. Got: {response[:100]}")
                return []
        
        return response.get('elements', [])
    
    
    def accurate_search(self, entities: List[str]) -> List[str]:
        accurate_results = []
        
        for entity in entities:
            # Split entity into words and create a pattern to match the whole phrase
            words = entity.lower().split()
            pattern = re.compile(r'\b' + r'\s+'.join(map(re.escape, words)) + r'\b')
            result = [id for id, text in self.accurate_id_to_text.items() if pattern.search(text.lower())]
            if result:
                accurate_results.extend(result)
        
        return accurate_results
    
    
    def answer(self,query:str,id_type:bool=True):
        
        
        retrieval = self.search(query)
        
        ans = Answer(query,retrieval)
        
        # Check if any relevant information was retrieved
        if not retrieval.search_list and not retrieval.relationship_list:
            ans.response = "I couldn't find any relevant information in the knowledge graph to answer your question. The requested information may not be available in the current dataset."
            return ans
        
        if id_type:
            retrieved_info = ans.structured_prompt
        else:
            retrieved_info = ans.unstructured_prompt
        
        # Check if retrieved_info is empty after processing
        if not retrieved_info or retrieved_info.strip() == '':
            ans.response = "I couldn't find any relevant information in the knowledge graph to answer your question. The requested information may not be available in the current dataset."
            return ans
        
        query = self.config.prompt_manager.answer.format(info=retrieved_info,query=query)
        response = self.config.API_client.request({'query':query})
        
        # Handle case where response is a string - it should be the answer text
        if isinstance(response, str):
            ans.response = response
        else:
            ans.response = response.get('response', str(response))
        
        return ans    
    
    async def answer_async(self,query:str,id_type:bool=True):
        
        
        retrieval = self.search(query)
        
        ans = Answer(query,retrieval)
        
        # Check if any relevant information was retrieved
        if not retrieval.search_list and not retrieval.relationship_list:
            ans.response = "I couldn't find any relevant information in the knowledge graph to answer your question. The requested information may not be available in the current dataset."
            return ans
        
        if id_type:
            retrieved_info = ans.structured_prompt
        else    :
            retrieved_info = ans.unstructured_prompt

        # Check if retrieved_info is empty after processing
        if not retrieved_info or retrieved_info.strip() == '':
            ans.response = "I couldn't find any relevant information in the knowledge graph to answer your question. The requested information may not be available in the current dataset."
            return ans

        query = self.config.prompt_manager.answer.format(info=retrieved_info,query=query)
        
        ans.response = await self.config.API_client({'query':query})
        
        return ans
        
    
    def stream_answer(self,query:str,retrieved_info:str):
        
        query = self.config.prompt_manager.answer.format(info=retrieved_info,query=query)
        response = self.config.API_client.stream_chat({'query':query})
        yield from response


    def graph_search(self,personlization:Dict[str,float])->List[Tuple[str,str]]|List[str]:
        
        page_rank_scores = self.sparse_PPR.PPR(personlization,alpha=self.config.ppr_alpha,max_iter=self.config.ppr_max_iter)
        
        
        return [id for id,score in page_rank_scores]
    
    def _search_qa_pairs(self, query_embedding: np.ndarray, top_k: int = 5) -> List[Dict]:
        """
        Search Question nodes using Question HNSW index (Phase 2)
        
        Args:
            query_embedding: Query embedding vector
            top_k: Number of results to return
        
        Returns:
            List of Q&A pairs with similarity scores
        """
        if self.question_hnsw is None or len(self.question_id_map) == 0:
            print(f"[DEBUG Q&A Search] HNSW index or id_map is empty: hnsw={self.question_hnsw is not None}, id_map_size={len(self.question_id_map)}")
            return []
        
        try:
            # Search Question HNSW index
            k = min(top_k, len(self.question_id_map))
            print(f"[DEBUG Q&A Search] Searching with k={k}, query_embedding shape={query_embedding.shape}")
            labels, distances = self.question_hnsw.knn_query(query_embedding, k=k)
            print(f"[DEBUG Q&A Search] HNSW returned {len(labels[0])} labels, {len(distances[0])} distances")
            
            results = []
            for idx, (label, distance) in enumerate(zip(labels[0], distances[0])):
                question_hash_id = self.question_id_map.get(label)
                print(f"[DEBUG Q&A Search] Result {idx+1}: label={label}, distance={distance:.4f}, question_hash_id={question_hash_id}")
                
                if not question_hash_id:
                    print(f"[DEBUG Q&A Search]   -> Skipping: no hash_id found for label {label}")
                    continue
                    
                if question_hash_id not in self.G.nodes():
                    print(f"[DEBUG Q&A Search]   -> Skipping: question node {question_hash_id} not in graph")
                    continue
                
                question_node = self.G.nodes[question_hash_id]
                question_text = question_node.get('text', '')
                print(f"[DEBUG Q&A Search]   -> Found question: '{question_text[:50]}...'")
                
                # Get answer node (connected via 'has_answer' edge)
                answer_hash_id = None
                answer_text = None
                
                # Use neighbors() for undirected graphs
                neighbors = list(self.G.neighbors(question_hash_id)) if hasattr(self.G, 'neighbors') else []
                
                for neighbor in neighbors:
                    # Check edge data - try both directions
                    edge_data = None
                    if (question_hash_id, neighbor) in self.G.edges:
                        edge_data = self.G.edges[question_hash_id, neighbor]
                    elif (neighbor, question_hash_id) in self.G.edges:
                        edge_data = self.G.edges[neighbor, question_hash_id]
                    
                    if edge_data and edge_data.get('type') == 'has_answer':
                        # Verify neighbor is an answer node
                        if self.G.nodes[neighbor].get('type') == 'answer':
                            answer_hash_id = neighbor
                            answer_node = self.G.nodes[neighbor]
                            answer_text = answer_node.get('text', '')
                            print(f"[DEBUG Q&A Search]   -> Found answer: '{answer_text[:50]}...'")
                            break
                
                if answer_hash_id is None:
                    print(f"[DEBUG Q&A Search]   -> Warning: No answer node found for question {question_hash_id}")
                
                # Calculate similarity score (1 - distance for cosine)
                similarity = 1 - distance
                
                results.append({
                    'question_hash_id': question_hash_id,
                    'answer_hash_id': answer_hash_id,
                    'question': question_text,
                    'answer': answer_text,
                    'similarity': similarity,
                    'distance': float(distance)
                })
            
            print(f"[DEBUG Q&A Search] Returning {len(results)} Q&A pairs")
            return results
            
        except Exception as e:
            import sys
            print(f"[ERROR] Q&A search failed: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()
            return []
        
    
    def post_process_top_k(self,weighted_nodes:List[str],retrieval:Retrieval)->Retrieval:
        
        
        entity_list = []
        high_level_element_title_list = []
        relationship_list = []
    
        addition_node = 0

        # Extract top entities from PageRank results
        for node in weighted_nodes:
            if node not in retrieval.search_list:
                type = self.G.nodes[node].get('type')
                match type:
                    case 'entity':
                        if node not in entity_list and len(entity_list) < self.config.Enode:
                            entity_list.append(node)
                    case 'relationship':
                        if node not in relationship_list and len(relationship_list) < self.config.Rnode:
                            relationship_list.append(node)
                    case 'high_level_element_title':
                        if node not in high_level_element_title_list and len(high_level_element_title_list) < self.config.Hnode:
                            high_level_element_title_list.append(node)
        
                    case _:
                        if addition_node < self.config.cross_node:
                            if node not in retrieval.unique_search_list:
                                retrieval.search_list.append(node)
                                retrieval.unique_search_list.add(node)
                                addition_node += 1
                
                if (addition_node >= self.config.cross_node 
                    and len(entity_list) >= self.config.Enode  
                    and len(relationship_list) >= self.config.Rnode 
                    and len(high_level_element_title_list) >= self.config.Hnode):
                    break

        # For each selected entity, include its attributes
        for entity in entity_list:
            attributes = self.G.nodes[entity].get('attributes')
            if attributes:
                for attribute in attributes:
                    if attribute not in retrieval.unique_search_list:
                        retrieval.search_list.append(attribute)
                        retrieval.unique_search_list.add(attribute)

    

        for high_level_element_title in high_level_element_title_list:
            related_node = self.G.nodes[high_level_element_title].get('related_node')
            if related_node not in retrieval.unique_search_list:
                retrieval.search_list.append(related_node)
                retrieval.unique_search_list.add(related_node)
            
            
        
        retrieval.relationship_list = list(set(relationship_list))
        
        # Phase 2: Add Q&A nodes to search results if they were found
        # Note: Results are already limited by qa_top_k config, so add all of them
        if hasattr(retrieval, 'qa_results') and retrieval.qa_results:
            for qa_pair in retrieval.qa_results:  # Add all Q&A pairs (already filtered by top_k)
                question_hash_id = qa_pair['question_hash_id']
                answer_hash_id = qa_pair['answer_hash_id']
                
                # Add question node if not already in search list
                if question_hash_id and question_hash_id not in retrieval.unique_search_list:
                    retrieval.search_list.append(question_hash_id)
                    retrieval.unique_search_list.add(question_hash_id)
                
                # Add answer node if not already in search list
                if answer_hash_id and answer_hash_id not in retrieval.unique_search_list:
                    retrieval.search_list.append(answer_hash_id)
                    retrieval.unique_search_list.add(answer_hash_id)
        
        return retrieval
    
    
    