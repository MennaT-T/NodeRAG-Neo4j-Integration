"""
Test script to verify Q&A nodes were created successfully
"""
import sys
import os
import yaml

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from NodeRAG.config import NodeConfig
from NodeRAG.storage import storage

def test_qa_nodes():
    """Check if Q&A nodes exist in the graph"""
    
    # Load config from YAML
    config_path = 'POC_Data/documents/Node_config.yaml'
    with open(config_path, 'r', encoding='utf-8') as f:
        config_dict = yaml.safe_load(f)
    
    config = NodeConfig(config_dict)
    
    # Load graph
    if os.path.exists(config.graph_path):
        G = storage.load_pickle(config.graph_path)
        print(f"\n✓ Graph loaded: {len(G.nodes())} nodes, {len(G.edges())} edges")
    else:
        print("✗ Graph file not found!")
        return
    
    # Count node types (check both lowercase and capitalized)
    node_types = {}
    question_nodes = []
    answer_nodes = []
    
    for node, data in G.nodes(data=True):
        node_type = data.get('type', 'unknown')
        node_types[node_type] = node_types.get(node_type, 0) + 1
        
        # Check both 'Question' and 'question' (case insensitive)
        if node_type.lower() == 'question':
            question_nodes.append((node, data))
        elif node_type.lower() == 'answer':
            answer_nodes.append((node, data))
    
    # Print summary
    print("\n=== Node Type Summary ===")
    for node_type, count in sorted(node_types.items()):
        print(f"  {node_type}: {count}")
    
    # Print Q&A details
    if question_nodes:
        print(f"\n=== Question Nodes ({len(question_nodes)}) ===")
        for node, data in question_nodes[:3]:  # Show first 3
            print(f"  ID: {node}")
            print(f"  Question: {data.get('raw_context', 'N/A')[:100]}...")
            print(f"  Job Title: {data.get('job_title', 'N/A')}")
            print(f"  Company: {data.get('company_name', 'N/A')}")
            print()
        if len(question_nodes) > 3:
            print(f"  ... and {len(question_nodes) - 3} more")
    else:
        print("\n✗ No Question nodes found!")
    
    if answer_nodes:
        print(f"\n=== Answer Nodes ({len(answer_nodes)}) ===")
        for node, data in answer_nodes[:3]:  # Show first 3
            print(f"  ID: {node}")
            print(f"  Answer: {data.get('raw_context', 'N/A')[:100]}...")
            print()
        if len(answer_nodes) > 3:
            print(f"  ... and {len(answer_nodes) - 3} more")
    else:
        print("\n✗ No Answer nodes found!")
    
    # Check Q&A relationships
    qa_edges = [(u, v) for u, v, data in G.edges(data=True) 
                if G.nodes[u].get('type', '').lower() == 'question' 
                and G.nodes[v].get('type', '').lower() == 'answer']
    
    print(f"\n=== Q&A Relationships ===")
    print(f"  Question→Answer edges: {len(qa_edges)}")
    
    if qa_edges:
        print("\n✓ Q&A Pipeline test PASSED!")
    else:
        print("\n✗ Q&A Pipeline test FAILED - No Q&A nodes or relationships found")

if __name__ == '__main__':
    test_qa_nodes()
