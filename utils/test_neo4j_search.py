"""
Test script to verify Neo4j-native search works correctly
"""
import sys
from pathlib import Path

# Add parent directory to path to import neo4j_native_search
sys.path.insert(0, str(Path(__file__).parent.parent))

from NodeRAG import NodeConfig, NodeSearch
from neo4j_native_search import integrate_neo4j_search

# Path to documents folder (adjust for utils subdirectory)
DOCUMENTS_FOLDER = Path(__file__).parent.parent / "POC_Data" / "documents"

def test_search():
    print("="*70)
    print("Testing Neo4j-Native Search")
    print("="*70)
    
    # Load config
    print("\n[1] Loading configuration...")
    config = NodeConfig.from_main_folder(str(DOCUMENTS_FOLDER))
    print("✓ Config loaded")
    
    # Read Neo4j credentials from config file (no hardcoded fallbacks for security)
    NEO4J_URI = config.config.get('neo4j_uri')
    NEO4J_USER = config.config.get('neo4j_user')
    NEO4J_PASSWORD = config.config.get('neo4j_password')
    
    if not all([NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD]):
        raise ValueError("Neo4j credentials not found in config file. Please add neo4j_uri, neo4j_user, and neo4j_password to Node_config.yaml")
    
    # Enable Neo4j-native search
    print("\n[2] Enabling Neo4j-native search...")
    integrate_neo4j_search(config, NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
    
    # Initialize search
    print("\n[3] Initializing search engine...")
    search = NodeSearch(config)
    print("✓ Search engine ready")
    
    # Test query
    test_query = "what is your experience in python?"
    print(f"\n[4] Testing query: '{test_query}'")
    print("-"*70)
    
    try:
        result = search.answer(test_query)
        print("\n[RESULT]")
        print(result.response)
        print("\n[RETRIEVED NODES]")
        print(f"Total nodes retrieved: {len(result.retrieval.search_list)}")
        print(f"Relationships: {len(result.retrieval.relationship_list)}")
        print("\n✓ Search completed successfully!")
        
    except Exception as e:
        print(f"\n✗ Search failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print("\n" + "="*70)
    print("Test PASSED - Neo4j-native search is working!")
    print("="*70)
    return True

if __name__ == "__main__":
    test_search()
