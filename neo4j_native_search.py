"""
Neo4j-Native Search for NodeRAG
================================

Replaces in-memory NetworkX graph operations with native Neo4j Cypher queries,
eliminating the need to load large pickle files into memory.

Key Benefits:
-------------
• Memory Optimization: Eliminates graph.pkl memory overhead
• Faster Startup: No pickle deserialization required
• Query Performance: Leverages Neo4j's query optimization engine
• Scalability: Handles large graphs without memory constraints

Architecture:
-------------
• Neo4jNativeSearch: Direct Neo4j query methods for graph operations
• integrate_neo4j_search(): Patches NodeSearch to use Neo4j instead of NetworkX
  - Replaces: __init__, load_graph, graph_search, post_process_top_k

Usage:
------
    from neo4j_native_search import integrate_neo4j_search
    from NodeRAG import NodeConfig, NodeSearch
    
    config = NodeConfig.from_main_folder(str(DOCUMENTS_FOLDER))
    integrate_neo4j_search(config, NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
    
    search = NodeSearch(config)
    result = search.answer("What skills does the candidate have?")

Author: Menna Alaa
Version: 1.0.0
"""

from typing import Dict, List, Tuple, Any
from NodeRAG.storage.neo4j_storage import get_neo4j_storage


class Neo4jNativeSearch:
    """Direct Neo4j query interface for graph operations without in-memory NetworkX graphs."""
    
    def __init__(self, neo4j_uri: str, neo4j_user: str, neo4j_password: str):
        self.neo4j = get_neo4j_storage(neo4j_uri, neo4j_user, neo4j_password)
    
    def find_neighbors(self, node_ids: List[str], max_hops: int = 2) -> List[str]:
        """Find neighboring nodes within specified relationship distance."""
        if not node_ids:
            return []
        
        with self.neo4j.driver.session() as session:
            result = session.run(f"""
                UNWIND $node_ids AS start_id
                MATCH (start:Node {{id: start_id}})-[:CONNECTED_TO*1..{max_hops}]-(connected:Node)
                RETURN DISTINCT connected.id AS id
                LIMIT 1000
            """, node_ids=node_ids)
            
            return [record['id'] for record in result]
    
    def get_nodes_by_type(self, node_ids: List[str], node_types: List[str]) -> Dict[str, List[str]]:
        """Filter and group nodes by type."""
        if not node_ids or not node_types:
            return {}
        
        with self.neo4j.driver.session() as session:
            result = session.run("""
                UNWIND $node_ids AS node_id
                MATCH (n:Node {id: node_id})
                WHERE n.type IN $types
                RETURN n.type AS type, n.id AS id
            """, node_ids=node_ids, types=node_types)
            
            typed_nodes = {}
            for record in result:
                node_type = record['type']
                if node_type not in typed_nodes:
                    typed_nodes[node_type] = []
                typed_nodes[node_type].append(record['id'])
            
            return typed_nodes
    
    def pagerank_subgraph(self, seed_nodes: List[str], max_iter: int = 10, damping: float = 0.85) -> List[Tuple[str, float]]:
        """Calculate node importance scores using degree-based heuristic (simplified PageRank).
        
        Note: Uses neighbor expansion instead of full GDS PageRank for compatibility.
        """
        if not seed_nodes:
            return []
        with self.neo4j.driver.session() as session:
            result = session.run("""
                UNWIND $seed_nodes AS seed_id
                MATCH (seed:Node {id: seed_id})-[:CONNECTED_TO*1..2]-(connected:Node)
                WITH connected, count(DISTINCT seed) AS seed_connections
                MATCH (connected)-[:CONNECTED_TO]-(neighbor:Node)
                WITH connected, seed_connections, count(DISTINCT neighbor) AS total_degree
                RETURN connected.id AS id, 
                       (seed_connections * 1.0 / (total_degree + 1)) AS score
                ORDER BY score DESC
                LIMIT 500
            """, seed_nodes=seed_nodes)
            
            return [(record['id'], record['score']) for record in result]
    
    def shortest_path(self, source_id: str, target_id: str, max_length: int = 5) -> List[str]:
        """Find shortest path between two nodes (up to max_length hops)."""
        with self.neo4j.driver.session() as session:
            result = session.run(f"""
                MATCH path = shortestPath(
                    (source:Node {{id: $source}})-[:CONNECTED_TO*1..{max_length}]-(target:Node {{id: $target}})
                )
                RETURN [node IN nodes(path) | node.id] AS path
            """, source=source_id, target=target_id)
            
            record = result.single()
            return record['path'] if record else []
    
    def get_node_context(self, node_id: str) -> Dict:
        """Retrieve all properties for a node."""
        return self.neo4j.get_node(node_id)
    
    def get_node_type(self, node_id: str) -> str:
        """Get node type (entity, relationship, high_level_element_title, etc.)."""
        with self.neo4j.driver.session() as session:
            result = session.run("""
                MATCH (n:Node {id: $node_id})
                RETURN n.type AS type
            """, node_id=node_id)
            
            record = result.single()
            return record['type'] if record else None
    
    def get_node_property(self, node_id: str, property_name: str):
        """Retrieve specific property from a node (with injection protection)."""
        # Whitelist validation prevents Cypher injection
        allowed_properties = {'type', 'attributes', 'related_node', 'name', 'description', 'source_id'}
        if property_name not in allowed_properties:
            raise ValueError(f"Property '{property_name}' not in allowed list: {allowed_properties}")
        
        with self.neo4j.driver.session() as session:
            result = session.run(f"""
                MATCH (n:Node {{id: $node_id}})
                RETURN n.{property_name} AS value
            """, node_id=node_id)
            
            record = result.single()
            if record and record['value']:
                return self.neo4j._deserialize_value(record['value'])
            return None
    
    def get_all_node_types(self) -> Dict[str, str]:
        """Build complete node ID to type mapping from Neo4j."""
        with self.neo4j.driver.session() as session:
            result = session.run("""
                MATCH (n:Node)
                RETURN n.id AS id, n.type AS type
            """)
            
            id_to_type = {record['id']: record['type'] for record in result}
            
            # Validate database has data
            if len(id_to_type) == 0:
                print("  ⚠️  WARNING: Neo4j database is empty!")
                print("  ⚠️  You need to migrate graph.pkl to Neo4j first")
                print("  ⚠️  Run: python migrate_to_neo4j.py")
            
            return id_to_type
    
    def get_batch_node_properties(self, node_ids: List[str], property_names: List[str]) -> Dict[str, Dict]:
        """Batch retrieve properties for multiple nodes (optimized single query)."""
        # Whitelist validation prevents Cypher injection
        allowed_properties = {'type', 'attributes', 'related_node', 'name', 'description', 'source_id'}
        for prop in property_names:
            if prop not in allowed_properties:
                raise ValueError(f"Property '{prop}' not in allowed list: {allowed_properties}")
        
        if not node_ids:
            return {}
        
        with self.neo4j.driver.session() as session:
            props_str = ', '.join([f'n.{prop} AS {prop}' for prop in property_names])
            
            result = session.run(f"""
                UNWIND $node_ids AS node_id
                MATCH (n:Node {{id: node_id}})
                RETURN n.id AS id, {props_str}
            """, node_ids=node_ids)
            
            node_data = {}
            for record in result:
                node_id = record['id']
                node_data[node_id] = {
                    prop: self.neo4j._deserialize_value(record[prop])
                    for prop in property_names
                    if record[prop] is not None
                }
            
            return node_data


def integrate_neo4j_search(config, neo4j_uri: str, neo4j_user: str, neo4j_password: str):
    """Replace NodeSearch methods with Neo4j-native implementations (avoids loading graph.pkl).
    
    Patches: __init__, load_graph, graph_search, post_process_top_k
    
    Args:
        config: NodeRAG config object
        neo4j_uri: Neo4j connection URI (e.g., 'bolt://localhost:7687')
        neo4j_user: Neo4j username
        neo4j_password: Neo4j password
    """
    import networkx as nx
    
    # Create Neo4j native search instance
    config.neo4j_search = Neo4jNativeSearch(neo4j_uri, neo4j_user, neo4j_password)
    
    # Import NodeSearch class
    from NodeRAG.search.search import NodeSearch
    from NodeRAG.utils.PPR import sparse_PPR
    
    # Store original methods
    original_graph_search = NodeSearch.graph_search
    original_load_graph = NodeSearch.load_graph
    original_init = NodeSearch.__init__
    
    def neo4j_init(self, config_obj):
        """Modified __init__ that skips graph.pkl loading."""
        self.config = config_obj
        self.hnsw = self.load_hnsw()
        self.mapper = self.load_mapper()
        
        # Empty placeholder (graph operations use Neo4j)
        print("  ⚡ Skipping graph.pkl loading (using Neo4j instead)")
        self.G = nx.Graph()
        
        # Load node types from Neo4j instead of pickle
        print("  ⚡ Loading node types from Neo4j...")
        self.id_to_type = config.neo4j_search.get_all_node_types()
        print(f"  ✓ Loaded {len(self.id_to_type)} node types from Neo4j")
        
        # Text mappings from parquet files
        self.id_to_text, self.accurate_id_to_text = self.mapper.generate_id_to_text(['entity', 'high_level_element_title'])
        
        # Unused (graph_search is replaced)
        self.sparse_PPR = None
        
        self._semantic_units = None
    
    def neo4j_load_graph(self):
        """Return empty graph (all operations redirected to Neo4j)."""
        return nx.Graph()
    
    def neo4j_graph_search(self, personalization: Dict[str, float]) -> List[str]:
        """Execute PageRank-style search via Neo4j Cypher queries."""
        seed_nodes = list(personalization.keys())
        
        if not seed_nodes:
            return []
        
        # Use Neo4j to find connected nodes
        ranked_nodes = config.neo4j_search.pagerank_subgraph(
            seed_nodes,
            max_iter=self.config.ppr_max_iter,
            damping=self.config.ppr_alpha
        )
        
        return [node_id for node_id, score in ranked_nodes]
    
    from NodeRAG.search.Answer_base import Retrieval
    def neo4j_post_process_top_k(self, weighted_nodes: List[str], retrieval:Retrieval) -> Any:
        """Filter and categorize nodes using batch Neo4j property queries."""
        entity_list = []
        high_level_element_title_list = []
        relationship_list = []
        addition_node = 0
        
        # Batch fetch node properties
        node_ids_to_check = [node for node in weighted_nodes if node not in retrieval.search_list]
        if not node_ids_to_check:
            return retrieval
        
        node_properties = config.neo4j_search.get_batch_node_properties(
            node_ids_to_check,
            ['type', 'attributes', 'related_node']
        )
        
        # Track additional nodes to fetch (attributes, related_nodes)
        additional_node_ids = []
        
        for node in weighted_nodes:
            if node not in retrieval.search_list:
                props = node_properties.get(node, {})
                node_type = props.get('type')
                
                if node_type == 'entity':
                    if node not in entity_list and len(entity_list) < self.config.Enode:
                        entity_list.append(node)
                        attributes = props.get('attributes')
                        if attributes:
                            additional_node_ids.extend(attributes)
                elif node_type == 'relationship':
                    if node not in relationship_list and len(relationship_list) < self.config.Rnode:
                        relationship_list.append(node)
                elif node_type == 'high_level_element_title':
                    if node not in high_level_element_title_list and len(high_level_element_title_list) < self.config.Hnode:
                        high_level_element_title_list.append(node)
                        related_node = props.get('related_node')
                        if related_node:
                            additional_node_ids.append(related_node)
                else:
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
        
        # Fetch properties for linked nodes
        additional_properties = {}
        if additional_node_ids:
            additional_properties = config.neo4j_search.get_batch_node_properties(
                list(set(additional_node_ids)),
                ['type']
            )
        
        # Add entity attributes to retrieval
        for entity in entity_list:
            props = node_properties.get(entity, {})
            attributes = props.get('attributes')
            if attributes:
                for attribute in attributes:
                    if attribute not in retrieval.unique_search_list:
                        retrieval.search_list.append(attribute)
                        retrieval.unique_search_list.add(attribute)
                        # Ensure type mapping exists
                        if attribute in additional_properties:
                            attr_type = additional_properties[attribute].get('type')
                            if attr_type and attribute not in self.id_to_type:
                                self.id_to_type[attribute] = attr_type
                        elif attribute not in self.id_to_type:
                            self.id_to_type[attribute] = 'attribute'
        
        # Add related nodes for high-level elements
        for high_level_element_title in high_level_element_title_list:
            props = node_properties.get(high_level_element_title, {})
            related_node = props.get('related_node')
            if related_node and related_node not in retrieval.unique_search_list:
                retrieval.search_list.append(related_node)
                retrieval.unique_search_list.add(related_node)
                # Ensure type mapping exists
                if related_node in additional_properties:
                    rel_type = additional_properties[related_node].get('type')
                    if rel_type and related_node not in self.id_to_type:
                        self.id_to_type[related_node] = rel_type
                elif related_node not in self.id_to_type:
                    self.id_to_type[related_node] = 'high_level_element'
        
        # Ensure all relationships have type mappings
        retrieval.relationship_list = list(set(relationship_list))
        for rel_node in retrieval.relationship_list:
            if rel_node not in self.id_to_type:
                if rel_node in node_properties:
                    node_type = node_properties[rel_node].get('type', 'relationship')
                    self.id_to_type[rel_node] = node_type
                else:
                    self.id_to_type[rel_node] = 'relationship'
        
        return retrieval
    
    # Apply method replacements
    NodeSearch.__init__ = neo4j_init
    NodeSearch.load_graph = neo4j_load_graph
    NodeSearch.graph_search = neo4j_graph_search
    NodeSearch.post_process_top_k = neo4j_post_process_top_k
    
    print("✓ Neo4j-native search enabled")
    print("  • __init__() → Loads types from Neo4j")
    print("  • load_graph() → Returns empty graph")
    print("  • graph_search() → Cypher-based PageRank") 
    print("  • post_process_top_k() → Batch property queries")

def integrate_neo4j_search_legacy(config, neo4j_uri: str, neo4j_user: str, neo4j_password: str):
    """Legacy integration: only patches graph_search method (minimal change approach)."""
    config.neo4j_search = Neo4jNativeSearch(neo4j_uri, neo4j_user, neo4j_password)
    
    from NodeRAG.search.search import NodeSearch
    
    def neo4j_graph_search(self, personalization: Dict[str, float]) -> List[str]:
        seed_nodes = list(personalization.keys())
        ranked_nodes = config.neo4j_search.pagerank_subgraph(
            seed_nodes,
            max_iter=self.config.ppr_max_iter,
            damping=self.config.ppr_alpha
        )
        return [node_id for node_id, score in ranked_nodes]
    
    NodeSearch.graph_search = neo4j_graph_search
    
    print("✓ Neo4j-native search enabled (legacy mode)")
    print("  Graph operations will query Neo4j directly")
    print("  No NetworkX graph loaded into memory")


# Example usage
if __name__ == "__main__":
    print("""
Neo4j Native Search Module
===========================

Enables Neo4j-native search where graph operations execute directly in the
database instead of loading pickle files into Python memory.

Usage Example:
--------------

from neo4j_native_search import integrate_neo4j_search
from NodeRAG import NodeConfig, NodeSearch

config = NodeConfig.from_main_folder(str(DOCUMENTS_FOLDER))
integrate_neo4j_search(config, NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)

search = NodeSearch(config)
result = search.answer("What are the candidate's skills?")

Benefits:
---------
✓ Reduced memory footprint (no in-memory graph)
✓ Faster initialization (no pickle loading)
✓ Optimized queries via Neo4j engine
✓ Improved scalability for large graphs
          
    """)
