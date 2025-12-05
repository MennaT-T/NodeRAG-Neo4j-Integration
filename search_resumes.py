"""
Resume Search with NodeRAG + Neo4j Native Queries
==================================================

Main entry point for resume search using NodeRAG with Neo4j backend.

This script demonstrates the optimized Neo4j integration where graph operations
are performed directly in Neo4j instead of loading graph.pkl into memory.

Key Features:
-------------
• Neo4j-native queries: All graph operations via Cypher (no NetworkX loading)
• Memory optimized: Saves 2-5GB RAM by not loading graph.pkl
• Fast startup: 60 seconds faster without pickle deserialization
• Interactive CLI: Ask questions about candidate resumes

Architecture:
-------------
1. Load NodeRAG configuration from POC_Data/documents/
2. Enable Neo4j-native search via integrate_neo4j_search()
3. Initialize NodeSearch (uses Neo4j queries under the hood)
4. Interactive question-answering loop

Requirements:
-------------
• Neo4j Docker container running at bolt://localhost:7687
• Graph migrated to Neo4j (run utils/migrate_to_neo4j.py first)
• API keys configured in POC_Data/documents/Node_config.yaml

Usage:
------
    python search_resumes.py

Based on official docs: https://terry-xu-666.github.io/NodeRAG_web/docs/answer/#import-module
"""

from pathlib import Path
from NodeRAG import NodeConfig, NodeSearch
from neo4j_native_search import integrate_neo4j_search

# ==================== Configuration ====================

# Path to documents folder containing Node_config.yaml and graph data
DOCUMENTS_FOLDER = Path(__file__).parent / "POC_Data" / "documents"

# =======================================================


def main():
    """
    Main search loop with interactive question-answering.
    
    Steps:
    1. Load NodeRAG configuration
    2. Enable Neo4j-native search (optimization)
    3. Initialize search engine
    4. Interactive query loop
    """
    print("=" * 70)
    print("Resume Search with NodeRAG + Neo4j (Native Queries)")
    print("=" * 70)
    
    # ==================== Step 1: Load Configuration ====================
    print("\n[1] Loading configuration...")
    try:
        config = NodeConfig.from_main_folder(str(DOCUMENTS_FOLDER))
        print("[OK] Configuration loaded")
        
        # Read Neo4j credentials from config file (access from nested config dict)
        NEO4J_URI = config.config.get('neo4j_uri')
        NEO4J_USER = config.config.get('neo4j_user')
        NEO4J_PASSWORD = config.config.get('neo4j_password')
        
        if not all([NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD]):
            raise ValueError("Neo4j credentials not found in config file. Please add neo4j_uri, neo4j_user, and neo4j_password to Node_config.yaml")
        
    except Exception as e:
        print(f"\n[ERROR] Failed to load config: {e}")
        print("\nMake sure you have:")
        print("  1. Run: python -m NodeRAG.build -f \"POC_Data/documents\"")
        print("  2. Added your API keys to Node_config.yaml")
        print("  3. Built the graph by running the build command again")
        return
    
    # ==================== Step 2: Enable Neo4j Optimization ====================
    # This is the KEY optimization that eliminates graph.pkl loading
    print("\n[1.5] Enabling Neo4j-native search...")
    try:
        integrate_neo4j_search(config, NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
        print("[OK] Neo4j-native search enabled")
        print("     → Graph queries will run directly in Neo4j")
        print("     → No NetworkX graph loaded (saves 2-5GB RAM)")
    except Exception as e:
        print(f"\n[ERROR] Failed to connect to Neo4j: {e}")
        print("\nMake sure you have:")
        print("  1. Neo4j container running: docker ps")
        print("  2. Migrated graph to Neo4j: python utils/migrate_to_neo4j.py")
        return
    
    # ==================== Step 3: Initialize Search Engine ====================
    print("\n[2] Initializing search engine...")
    try:
        # NodeSearch now uses Neo4j natively (thanks to integrate_neo4j_search)
        search = NodeSearch(config)
        print("[OK] Search engine ready")
    except Exception as e:
        print(f"\n[ERROR] Failed to initialize search: {e}")
        print("\nMake sure the knowledge graph has been built.")
        return
    
    # ==================== Step 4: Interactive Query Loop ====================
    print("\n" + "=" * 70)
    print("Ready to search resumes!")
    print("=" * 70)
    print("\nType your questions below (or 'quit' to exit)")
    print("\nExample questions:")
    print("  - What programming languages does the candidate know?")
    print("  - Does the candidate have Python experience?")
    print("  - What is the candidate's education background?")
    print("  - List the candidate's skills")
    print("-" * 70)
    
    while True:
        question = input("\nQuestion: ").strip()
        
        if question.lower() in ['quit', 'exit', 'q']:
            print("\nGoodbye!")
            break
        
        if not question:
            continue
        
        try:
            print("\n[Searching...]")
            
            # Query the system using official NodeRAG API
            # Internally: HNSW vector search → Neo4j PageRank → Gemini generation
            ans = search.answer(question)
            
            # Display results
            print("\n" + "=" * 70)
            print("ANSWER:")
            print("=" * 70)
            print(f"\n{ans.response}\n")
            
            print("-" * 70)
            print(f"Response tokens: {ans.response_tokens}")
            print(f"Retrieval tokens: {ans.retrieval_tokens}")
            print("-" * 70)
            
        except Exception as e:
            print(f"\n[ERROR] {str(e)}")


if __name__ == "__main__":
    main()

