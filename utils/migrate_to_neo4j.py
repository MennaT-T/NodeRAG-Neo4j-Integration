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


def migrate_graph_to_neo4j(config: 'NodeConfig', neo4j_uri: str, neo4j_user: str, neo4j_password: str):
    """
    Migrate existing graph.pkl to Neo4j database
    
    Args:
        config: NodeConfig object (handles multi-user routing)
        neo4j_uri: Neo4j connection URI
        neo4j_user: Neo4j username
        neo4j_password: Neo4j password
    """
    print("=" * 70)
    print("NodeRAG Graph Migration to Neo4j")
    print("=" * 70)
    
    # Use effective_main_folder for multi-user support
    if hasattr(config, 'user_id') and config.user_id:
        print(f"\n[INFO] Multi-user mode: user_id = {config.user_id}")
        print(f"[INFO] Using effective_main_folder: {config.effective_main_folder}")
    
    # Try to find the graph file (check both base_graph_path and graph_path)
    graph_path = None
    if hasattr(config, 'base_graph_path') and os.path.exists(config.base_graph_path):
        graph_path = config.base_graph_path
        print(f"\n[INFO] Using base_graph_path: {graph_path}")
    elif hasattr(config, 'graph_path') and os.path.exists(config.graph_path):
        graph_path = config.graph_path
        print(f"\n[INFO] Using graph_path: {graph_path}")
    else:
        # Try both paths and show which ones don't exist
        paths_checked = []
        if hasattr(config, 'base_graph_path'):
            paths_checked.append(config.base_graph_path)
        if hasattr(config, 'graph_path'):
            paths_checked.append(config.graph_path)
        
        print(f"\n❌ Error: Graph file not found")
        print("Checked paths:")
        for p in paths_checked:
            print(f"  - {p}")
        print("\nPlease build the graph first: python -m NodeRAG.build -f <folder>")
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
    
    # Load config to get Neo4j credentials AND handle multi-user routing
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
    
    # Run migration (pass config object instead of main_folder string)
    success = migrate_graph_to_neo4j(
        config,
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
