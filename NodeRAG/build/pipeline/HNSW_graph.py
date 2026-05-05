import os
import pickle
import numpy as np
import pandas as pd
from ...utils.HNSW import HNSW
from ...storage import Mapper
from ...config import NodeConfig
from ...logging import info_timer



class HNSW_pipeline():
    
    def __init__(self,config:NodeConfig):
        
        self.config = config
        self.mapper = self.load_mapper()
        self.hnsw = self.load_hnsw()
        
    def load_mapper(self) -> Mapper:
        
        mapping_list = [self.config.semantic_units_path,
                        self.config.attributes_path,
                        self.config.high_level_elements_path,
                        self.config.text_path]
        
        for i in range(len(mapping_list)):
            if not os.path.exists(mapping_list[i]):
                mapping_list.pop(i)
        
        mapper = Mapper(mapping_list)
        if os.path.exists(self.config.embedding):
            mapper.add_embedding(self.config.embedding)
            
        return mapper
    
    def load_hnsw(self) -> HNSW:
        
        hnsw = HNSW(self.config)
        
        if os.path.exists(self.config.HNSW_path):
            
            hnsw.load_HNSW(self.config.HNSW_path)
            return hnsw
        
        elif self.mapper.embeddings is not None:
            return hnsw
        else:
            raise Exception('No embeddings found')

    
    def generate_HNSW(self):
        unHNSW = self.mapper.find_non_HNSW()
        
        self.config.console.print(f'[yellow]Generating HNSW graph for {len(unHNSW)} nodes[/yellow]')
        self.hnsw.add_nodes(unHNSW)
        self.config.console.print(f'[green]HNSW graph has been added to the graph[/green]')
        self.config.tracker.set(len(unHNSW),desc="storing HNSW graph")
        for id,embedding in unHNSW:
            self.mapper.add_attribute(id,'embedding','HNSW')
            self.config.tracker.update()
        self.config.tracker.close()
        self.config.console.print(f'[green]HNSW graph generated for {len(unHNSW)} nodes[/green]')
    
    def delete_embedding(self):
        
        if os.path.exists(self.config.embedding):
            os.remove(self.config.embedding)
    
    @info_timer(message='HNSW graph generation')
    async def main(self):
        if os.path.exists(self.config.embedding):
            self.generate_HNSW()
            self.hnsw.save_HNSW()
            self.mapper.update_save()
            self.delete_embedding()
            self.config.console.print('[green]HNSW graph saved[/green]')

        # After content HNSW is ready, connect Q/Ans nodes to nearest content nodes
        self._add_qa_content_edges()

    def _add_qa_content_edges(self):
        """
        Add qa_content_link edges between Question/Answer nodes and their nearest
        content nodes in the content HNSW.  These edges give the PPR random walk
        a real graph neighbourhood to propagate through when Q/Ans nodes are seeded.

        Called at the end of the HNSW pipeline so the content HNSW is guaranteed
        to exist before this runs.
        """
        questions_path = getattr(self.config, 'questions_path',
                                 os.path.join(self.config.cache, 'questions.parquet'))
        # graph_path is 'new_graph.pkl' (after summary) but the file may also be at base_graph_path
        graph_path = getattr(self.config, 'graph_path',
                             os.path.join(self.config.cache, 'new_graph.pkl'))
        if not os.path.exists(graph_path):
            graph_path = getattr(self.config, 'base_graph_path',
                                 os.path.join(self.config.cache, 'graph.pkl'))

        if not os.path.exists(questions_path):
            print('[HNSW] No questions.parquet found — skipping qa_content_link edge creation')
            return
        if not os.path.exists(graph_path):
            print('[HNSW] No graph found — skipping qa_content_link edge creation')
            return
        if not os.path.exists(self.config.HNSW_path):
            print('[HNSW] Content HNSW not found — skipping qa_content_link edge creation')
            return

        k         = getattr(self.config, 'qa_content_edges_k', 5)
        threshold = getattr(self.config, 'qa_content_edges_threshold', 0.4)

        # Load questions with embeddings
        try:
            df_q = pd.read_parquet(questions_path)
        except Exception as e:
            print(f'[HNSW] Could not read questions.parquet: {e}')
            return

        if 'embedding' not in df_q.columns or df_q.empty:
            print('[HNSW] No question embeddings found — skipping qa_content_link edge creation')
            return

        # Load graph
        try:
            with open(graph_path, 'rb') as f:
                G = pickle.load(f)
        except Exception as e:
            print(f'[HNSW] Could not load graph: {e}')
            return

        edges_added = 0
        questions_processed = 0
        has_answer_map = {
            u: v for u, v, d in G.edges(data=True)
            if d.get('type') == 'has_answer'
        }
        print(f'[HNSW] has_answer_map size: {len(has_answer_map)}, graph nodes: {G.number_of_nodes()}')

        for _, row in df_q.iterrows():
            q_hash_id  = row.get('hash_id') or row.get('id')
            embedding  = row.get('embedding')
            if q_hash_id is None or embedding is None:
                continue

            try:
                emb_arr = np.array(embedding, dtype=np.float32)
            except Exception:
                continue

            try:
                results = list(self.hnsw.search(emb_arr, HNSW_results=k))
            except Exception as e:
                print(f'[HNSW] HNSW search failed for {q_hash_id}: {e}')
                continue

            questions_processed += 1
            if questions_processed == 1:
                print(f'[HNSW] Sample: {len(results)} results for first Q, '
                      f'first dist={results[0][0]:.4f} sim={1-results[0][0]:.4f} if results else no results')

            ans_hash_id = has_answer_map.get(q_hash_id)

            for distance, content_node_id in results:
                # Convert L2 distance to cosine similarity for unit-norm embeddings.
                # For l2 space: cos_sim = 1 - dist²/2  (exact for unit vectors).
                # For cosine space: cos_sim = 1 - dist  (hnswlib returns 1-cos as dist).
                space = getattr(self.config, 'space', 'l2')
                if space == 'l2':
                    similarity = float(1.0 - (distance ** 2) / 2.0)
                else:
                    similarity = float(1.0 - distance)
                if similarity < threshold:
                    continue
                if not G.has_node(content_node_id):
                    continue

                G.add_edge(q_hash_id, content_node_id,
                           type='qa_content_link',
                           weight=round(similarity, 4))

                if ans_hash_id and G.has_node(ans_hash_id):
                    G.add_edge(ans_hash_id, content_node_id,
                               type='qa_content_link',
                               weight=round(similarity * 0.9, 4))

                edges_added += 1

        if edges_added > 0:
            try:
                with open(graph_path, 'wb') as f:
                    pickle.dump(G, f)
                print(f'[HNSW] qa_content_link: added {edges_added} edges, graph saved')
            except Exception as e:
                print(f'[HNSW] Could not save graph after adding qa_content_link edges: {e}')
        else:
            print('[HNSW] qa_content_link: no edges added (all similarities below threshold or no Q nodes)')
        
        
            
        
    
        
