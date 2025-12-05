"""
Neo4j Integration Script for NodeRAG
This script modifies the graph pipeline to use Neo4j instead of pickle storage
"""
import sys
import os
from pathlib import Path

# Add the parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from NodeRAG.storage.neo4j_storage import get_neo4j_storage, close_neo4j_storage
from NodeRAG import NodeConfig
import pickle


def migrate_graph_to_neo4j(main_folder: str, neo4j_uri: str, neo4j_user: str, neo4j_password: str):
    """
    Migrate existing graph.pkl to Neo4j database
    
    Args:
        main_folder: Path to NodeRAG documents folder
        neo4j_uri: Neo4j connection URI
        neo4j_user: Neo4j username
        neo4j_password: Neo4j password
    """
    print("=" * 70)
    print("NodeRAG Graph Migration to Neo4j")
    print("=" * 70)
    
    # Load the existing graph
    graph_path = os.path.join(main_folder, 'cache', 'graph.pkl')
    
    if not os.path.exists(graph_path):
        print(f"\n❌ Error: Graph file not found at {graph_path}")
        print("Please build the graph first: python -m NodeRAG.build -f <folder>")
        return False
    
    print(f"\n[1/3] Loading graph from {graph_path}...")
    with open(graph_path, 'rb') as f:
        graph = pickle.load(f)
    
    print(f"✓ Graph loaded: {len(graph.nodes)} nodes, {len(graph.edges)} edges")
    
    # Connect to Neo4j
    print(f"\n[2/3] Connecting to Neo4j at {neo4j_uri}...")
    try:
        neo4j = get_neo4j_storage(neo4j_uri, neo4j_user, neo4j_password)
    except Exception as e:
        print(f"\n❌ Failed to connect to Neo4j: {e}")
        return False
    
    # Clear existing data (optional - comment out to append)
    print("\n⚠️  Clearing existing Neo4j data...")
    neo4j.clear_database()
    
    # Save to Neo4j
    print("\n[3/3] Migrating graph to Neo4j...")
    try:
        neo4j.save_graph(graph, batch_size=1000)
        
        # Show statistics
        stats = neo4j.get_statistics()
        print("\n" + "=" * 70)
        print("Migration Complete!")
        print("=" * 70)
        print(f"\nNeo4j Statistics:")
        print(f"  Total Nodes: {stats['total_nodes']}")
        print(f"  Total Relationships: {stats['total_relationships']}")
        print(f"\nNode Type Distribution:")
        for node_type, count in stats['node_types'].items():
            print(f"  {node_type}: {count}")
        print("\n" + "=" * 70)
        print(f"\nNeo4j Browser: http://localhost:7474")
        print(f"Username: {neo4j_user}")
        print("=" * 70)
        
        return True
        
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        close_neo4j_storage()


def load_graph_from_neo4j(neo4j_uri: str, neo4j_user: str, neo4j_password: str):
    """
    Load graph from Neo4j and return NetworkX graph
    
    Args:
        neo4j_uri: Neo4j connection URI
        neo4j_user: Neo4j username
        neo4j_password: Neo4j password
    
    Returns:
        NetworkX graph object
    """
    print("Loading graph from Neo4j...")
    neo4j = get_neo4j_storage(neo4j_uri, neo4j_user, neo4j_password)
    graph = neo4j.load_graph()
    return graph


if __name__ == "__main__":
    # Configuration (adjusted for utils subdirectory)
    MAIN_FOLDER = str(Path(__file__).parent.parent / "POC_Data" / "documents")
    
    # Load config to get Neo4j credentials
    from NodeRAG import NodeConfig
    config = NodeConfig.from_main_folder(MAIN_FOLDER)
    
    # Read Neo4j credentials from config file (access from nested config dict)
    NEO4J_URI = config.config.get('neo4j_uri')
    NEO4J_USER = config.config.get('neo4j_user')
    NEO4J_PASSWORD = config.config.get('neo4j_password')
    
    if not all([NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD]):
        print("\n[ERROR] Neo4j credentials not found in config file")
        print("Please add the following to Node_config.yaml under 'config:' section:")
        print("  neo4j_uri: 'bolt://localhost:7687'")
        print("  neo4j_user: 'neo4j'")
        print("  neo4j_password: 'your-password'")
        sys.exit(1)
    
    # Run migration
    success = migrate_graph_to_neo4j(
        MAIN_FOLDER,
        NEO4J_URI,
        NEO4J_USER,
        NEO4J_PASSWORD
    )
    
    if success:
        print("\n✓ You can now query the graph in Neo4j Browser")
        print("\nExample Cypher queries:")
        print("  // View all node types")
        print("  MATCH (n:Node) RETURN DISTINCT n.type, count(n) as count")
        print("\n  // View sample entities")
        print("  MATCH (n:Node {type: 'entity'}) RETURN n LIMIT 10")
        print("\n  // View relationships")
        print("  MATCH (s:Node)-[r:CONNECTED_TO]->(t:Node) RETURN s, r, t LIMIT 25")
