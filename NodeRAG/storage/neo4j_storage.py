"""
Neo4j Storage Adapter for NodeRAG
Provides graph storage in Neo4j database instead of pickle files
"""
from typing import Dict, Any, List, Optional
import networkx as nx
from neo4j import GraphDatabase
import json


class Neo4jStorage:
    """
    Storage adapter for Neo4j graph database
    """
    
    def __init__(self, uri: str, user: str, password: str):
        """
        Initialize Neo4j connection
        
        Args:
            uri: Neo4j connection URI (e.g., bolt://localhost:7687)
            user: Neo4j username
            password: Neo4j password
        """
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self._verify_connectivity()
    
    def _verify_connectivity(self):
        """Verify connection to Neo4j"""
        try:
            with self.driver.session() as session:
                session.run("RETURN 1")
            print("✓ Successfully connected to Neo4j")
        except Exception as e:
            raise ConnectionError(f"Failed to connect to Neo4j: {e}")
    
    def close(self):
        """Close Neo4j connection"""
        if self.driver:
            self.driver.close()
    
    def clear_database(self):
        """Clear all nodes and relationships from Neo4j"""
        with self.driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")
            print("✓ Neo4j database cleared")
    
    def save_graph(self, graph: nx.Graph, batch_size: int = 1000):
        """
        Save NetworkX graph to Neo4j
        
        Args:
            graph: NetworkX graph object
            batch_size: Number of nodes/edges to process in each batch
        """
        with self.driver.session() as session:
            # Create nodes in batches
            nodes = list(graph.nodes(data=True))
            total_nodes = len(nodes)
            
            print(f"Saving {total_nodes} nodes to Neo4j...")
            for i in range(0, total_nodes, batch_size):
                batch = nodes[i:i + batch_size]
                self._create_nodes_batch(session, batch)
                if (i + batch_size) % 5000 == 0:
                    print(f"  Processed {min(i + batch_size, total_nodes)}/{total_nodes} nodes")
            
            # Create relationships in batches
            edges = list(graph.edges(data=True))
            total_edges = len(edges)
            
            print(f"Saving {total_edges} relationships to Neo4j...")
            for i in range(0, total_edges, batch_size):
                batch = edges[i:i + batch_size]
                self._create_relationships_batch(session, batch)
                if (i + batch_size) % 5000 == 0:
                    print(f"  Processed {min(i + batch_size, total_edges)}/{total_edges} relationships")
            
            # Create indexes for performance
            self._create_indexes(session)
            
            print(f"✓ Graph saved to Neo4j: {total_nodes} nodes, {total_edges} relationships")
    
    def _create_nodes_batch(self, session, nodes_batch: List):
        """Create a batch of nodes"""
        query = """
        UNWIND $nodes AS node
        CREATE (n:Node {id: node.id})
        SET n += node.properties
        """
        nodes_data = [
            {
                'id': node_id,
                'properties': {k: self._serialize_value(v) for k, v in data.items()}
            }
            for node_id, data in nodes_batch
        ]
        session.run(query, nodes=nodes_data)
    
    def _create_relationships_batch(self, session, edges_batch: List):
        """Create a batch of relationships"""
        query = """
        UNWIND $edges AS edge
        MATCH (source:Node {id: edge.source})
        MATCH (target:Node {id: edge.target})
        CREATE (source)-[r:CONNECTED_TO]->(target)
        SET r += edge.properties
        """
        edges_data = [
            {
                'source': source,
                'target': target,
                'properties': {k: self._serialize_value(v) for k, v in data.items()}
            }
            for source, target, data in edges_batch
        ]
        session.run(query, edges=edges_data)
    
    def _create_indexes(self, session):
        """Create indexes for better query performance"""
        try:
            session.run("CREATE INDEX node_id_index IF NOT EXISTS FOR (n:Node) ON (n.id)")
            session.run("CREATE INDEX node_type_index IF NOT EXISTS FOR (n:Node) ON (n.type)")
            print("✓ Indexes created")
        except Exception as e:
            print(f"Warning: Could not create indexes: {e}")
    
    def _serialize_value(self, value: Any) -> Any:
        """Serialize complex values to Neo4j-compatible types"""
        if isinstance(value, (list, dict, set)):
            return json.dumps(value)
        elif isinstance(value, (str, int, float, bool)) or value is None:
            return value
        else:
            return str(value)
    
    def _deserialize_value(self, value: Any) -> Any:
        """Deserialize values from Neo4j"""
        if isinstance(value, str):
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return value
        return value
    
    def load_graph(self) -> nx.Graph:
        """
        Load graph from Neo4j into NetworkX format
        
        Returns:
            NetworkX graph object
        """
        graph = nx.Graph()
        
        with self.driver.session() as session:
            # Load nodes
            result = session.run("MATCH (n:Node) RETURN n.id AS id, properties(n) AS props")
            for record in result:
                node_id = record['id']
                props = {k: self._deserialize_value(v) for k, v in record['props'].items() if k != 'id'}
                graph.add_node(node_id, **props)
            
            # Load relationships
            result = session.run("""
                MATCH (source:Node)-[r:CONNECTED_TO]->(target:Node)
                RETURN source.id AS source, target.id AS target, properties(r) AS props
            """)
            for record in result:
                source = record['source']
                target = record['target']
                props = {k: self._deserialize_value(v) for k, v in record['props'].items()}
                graph.add_edge(source, target, **props)
            
            print(f"✓ Graph loaded from Neo4j: {len(graph.nodes)} nodes, {len(graph.edges)} edges")
        
        return graph
    
    def get_node(self, node_id: str) -> Optional[Dict]:
        """Get a specific node by ID"""
        with self.driver.session() as session:
            result = session.run(
                "MATCH (n:Node {id: $id}) RETURN properties(n) AS props",
                id=node_id
            )
            record = result.single()
            if record:
                return {k: self._deserialize_value(v) for k, v in record['props'].items()}
        return None
    
    def get_neighbors(self, node_id: str) -> List[str]:
        """Get all neighbors of a node"""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (n:Node {id: $id})-[:CONNECTED_TO]-(neighbor:Node)
                RETURN neighbor.id AS id
            """, id=node_id)
            return [record['id'] for record in result]
    
    def query_nodes_by_type(self, node_type: str) -> List[Dict]:
        """Query nodes by type"""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (n:Node {type: $type})
                RETURN n.id AS id, properties(n) AS props
            """, type=node_type)
            return [
                {'id': record['id'], **{k: self._deserialize_value(v) for k, v in record['props'].items()}}
                for record in result
            ]
    
    def get_statistics(self) -> Dict[str, int]:
        """Get database statistics"""
        with self.driver.session() as session:
            node_count = session.run("MATCH (n:Node) RETURN count(n) AS count").single()['count']
            edge_count = session.run("MATCH ()-[r:CONNECTED_TO]->() RETURN count(r) AS count").single()['count']
            
            # Get node type distribution
            type_result = session.run("""
                MATCH (n:Node)
                RETURN n.type AS type, count(n) AS count
                ORDER BY count DESC
            """)
            type_distribution = {record['type']: record['count'] for record in type_result}
            
            return {
                'total_nodes': node_count,
                'total_relationships': edge_count,
                'node_types': type_distribution
            }


# Singleton instance
_neo4j_instance: Optional[Neo4jStorage] = None


def get_neo4j_storage(uri: str = None, user: str = None, password: str = None) -> Neo4jStorage:
    """
    Get or create Neo4j storage singleton instance
    
    Args:
        uri: Neo4j URI (only needed on first call)
        user: Neo4j username (only needed on first call)
        password: Neo4j password (only needed on first call)
    
    Returns:
        Neo4jStorage instance
    """
    global _neo4j_instance
    
    if _neo4j_instance is None:
        if not all([uri, user, password]):
            raise ValueError("Must provide uri, user, and password on first call")
        _neo4j_instance = Neo4jStorage(uri, user, password)
    
    return _neo4j_instance


def close_neo4j_storage():
    """Close Neo4j connection"""
    global _neo4j_instance
    if _neo4j_instance:
        _neo4j_instance.close()
        _neo4j_instance = None
