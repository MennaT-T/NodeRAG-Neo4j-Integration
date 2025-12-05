"""
Graph Visualization Script
Generates an interactive HTML visualization of the knowledge graph
"""
from NodeRAG.Vis.html.visual_html import visualize
from pathlib import Path

def main():
    # Path to your documents folder (adjust for utils subdirectory)
    main_folder = Path(__file__).parent.parent / "POC_Data" / "documents"
    
    print("=" * 70)
    print("NodeRAG Graph Visualization")
    print("=" * 70)
    
    # Number of nodes to display (2000 is a good starting point)
    # Reduce if visualization is too slow, increase for more detail
    nodes_num = 2000
    
    print(f"\nGenerating visualization with up to {nodes_num} nodes...")
    print(f"Main folder: {main_folder}")
    
    try:
        # Generate the visualization
        visualize(str(main_folder), nodes_num=nodes_num)
        
        # Output path
        html_file = main_folder / "index.html"
        
        print("\n" + "=" * 70)
        print("✓ Visualization generated successfully!")
        print("=" * 70)
        print(f"\nOpen this file in your browser:")
        print(f"  {html_file}")
        print("\nFeatures:")
        print("  • Hover over nodes to see details")
        print("  • Drag nodes to move them")
        print("  • Scroll to zoom in/out")
        print("  • Right-click for more options")
        print("\nNode Colors:")
        print("  • Blue      = Entities")
        print("  • Gold      = Attributes")
        print("  • Orange    = Relationships")
        print("  • Green     = High-level Elements")
        print("  • Purple    = Semantic Units")
        print("=" * 70)
        
    except Exception as e:
        print(f"\n[ERROR] Failed to generate visualization: {e}")
        print("\nMake sure you have:")
        print("  1. Built the graph: python -m NodeRAG.build -f \"POC_Data\\documents\"")
        print("  2. PyVis installed: pip install pyvis")

if __name__ == "__main__":
    main()
