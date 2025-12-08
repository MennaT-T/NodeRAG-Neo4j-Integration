"""
Standalone script to run QA pipeline on existing graph
"""
import asyncio
import sys
import os
import yaml

# Add parent directory to path to use local NodeRAG instead of installed package
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)

from NodeRAG.config import NodeConfig
from NodeRAG.build.pipeline.qa_pipeline import QA_Pipeline
from NodeRAG.utils.qa_api_client import QAAPIClient

async def run_qa_pipeline():
    """Run QA pipeline independently"""
    
    # Load config from YAML
    config_path = 'POC_Data/documents/Node_config.yaml'
    with open(config_path, 'r', encoding='utf-8') as f:
        config_dict = yaml.safe_load(f)
    
    # Create NodeConfig instance
    config = NodeConfig(config_dict)
    
    # Check if QA is enabled
    if not hasattr(config, 'qa_api') or not config.qa_api.get('enabled', False):
        print("❌ Q&A integration is not enabled in config")
        return
    
    print("✓ Q&A integration enabled")
    print(f"  Base URL: {config.qa_api.get('base_url')}")
    print(f"  Use mock: {config.qa_api.get('use_mock')}")
    print(f"  User ID: {config.qa_api.get('user_id')}")
    
    # Initialize QA API client
    mock_path = config.qa_api.get('mock_data_path', 'mock_data/mock_qa_data.json')
    # Make path absolute relative to main_folder
    if not os.path.isabs(mock_path):
        mock_path = os.path.join(config.main_folder, mock_path)
    
    qa_api_client = QAAPIClient(
        api_base_url=config.qa_api.get('base_url', ''),
        use_mock=config.qa_api.get('use_mock', True),
        mock_data_path=mock_path
    )
    
    print("\n🚀 Starting Q&A Pipeline...")
    
    # Run QA pipeline
    qa_pipeline = QA_Pipeline(config, qa_api_client)
    graph = await qa_pipeline.main()
    
    print(f"\n✅ Q&A Pipeline completed!")
    print(f"   Graph now has {len(graph.nodes())} nodes and {len(graph.edges())} edges")
    
    # Count Q&A nodes
    question_count = sum(1 for _, data in graph.nodes(data=True) if data.get('type') == 'Question')
    answer_count = sum(1 for _, data in graph.nodes(data=True) if data.get('type') == 'Answer')
    
    print(f"   Question nodes: {question_count}")
    print(f"   Answer nodes: {answer_count}")

if __name__ == '__main__':
    asyncio.run(run_qa_pipeline())
