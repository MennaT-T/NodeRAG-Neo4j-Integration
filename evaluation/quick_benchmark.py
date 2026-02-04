"""
Quick Benchmark Script for Job Application Q&A System
======================================================
Uses working patterns from api/services.py to run evaluation queries.

Run: python evaluation/quick_benchmark.py [user_id]
Example: python evaluation/quick_benchmark.py user_8
"""

import sys
import time
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any
import yaml

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from NodeRAG import NodeConfig, NodeSearch

# ============================================================================
# Configuration
# ============================================================================

DEFAULT_USER_ID = "user_8"

TEST_QUERIES = [
    {"query": "Why are you interested in this position and what makes you a good fit?", "category": "motivation"},
    {"query": "Describe your most relevant technical experience for this role.", "category": "experience"},
    {"query": "What programming languages and tools are you proficient in?", "category": "technical_skills"},
    {"query": "Tell me about a challenging project you worked on.", "category": "experience"},
    {"query": "What is your educational background?", "category": "education"},
    {"query": "Describe your experience working in a team.", "category": "soft_skills"},
    {"query": "What machine learning or data science experience do you have?", "category": "technical_skills"},
    {"query": "How do you stay updated with latest technologies?", "category": "soft_skills"}
]

RUNS_PER_QUERY = 3

# ============================================================================
# Functions
# ============================================================================

def initialize_system(user_id: str) -> tuple:
    print(f"🔧 Initializing system for user '{user_id}'...")
    
    user_config_path = Path(__file__).parent.parent / "POC_Data" / "documents" / "users" / user_id / "Node_config.yaml"
    root_config_path = Path(__file__).parent.parent / "Node_config.yaml"
    
    # If user has their own config, use it directly (it already has correct paths)
    if user_config_path.exists():
        print(f"   ✓ Using user-specific config")
        with open(user_config_path, 'r') as f:
            config_data = yaml.safe_load(f)
        # Don't set user_id - the config already has correct main_folder path
        config = NodeConfig(config_data)
    else:
        # Use root config and set user_id to route to user folder
        print(f"   ✓ Using root config with user_id routing")
        with open(root_config_path, 'r') as f:
            config_data = yaml.safe_load(f)
        if 'config' not in config_data:
            config_data['config'] = {}
        # Strip 'user_' prefix if present (NodeConfig will add it)
        clean_user_id = user_id.replace('user_', '') if user_id.startswith('user_') else user_id
        config_data['config']['user_id'] = clean_user_id
        config = NodeConfig(config_data)
    
    search_engine = NodeSearch(config)
    
    print(f"   ✓ Graph loaded: {len(search_engine.G.nodes)} nodes, {len(search_engine.G.edges)} edges")
    return config, search_engine


def run_single_query(search_engine: NodeSearch, query: str, category: str) -> Dict[str, Any]:
    start_time = time.time()
    
    try:
        result = search_engine.answer(query)
        latency_ms = (time.time() - start_time) * 1000
        
        retrieval = result.retrieval
        nodes_retrieved = len(retrieval.search_list) if hasattr(retrieval, 'search_list') else 0
        answer_preview = result.response[:150] + "..." if len(result.response) > 150 else result.response
        
        return {
            "success": True,
            "query": query,
            "category": category,
            "latency_ms": latency_ms,
            "nodes_retrieved": nodes_retrieved,
            "answer_preview": answer_preview,
            "answer_length": len(result.response),
            "error": None
        }
    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000
        return {
            "success": False,
            "query": query,
            "category": category,
            "latency_ms": latency_ms,
            "nodes_retrieved": 0,
            "answer_preview": "",
            "answer_length": 0,
            "error": str(e)
        }


def run_benchmark(search_engine: NodeSearch) -> List[Dict[str, Any]]:
    print(f"\n📊 Running benchmark: {len(TEST_QUERIES)} queries × {RUNS_PER_QUERY} runs")
    print("=" * 70)
    
    all_results = []
    
    for idx, test_case in enumerate(TEST_QUERIES, 1):
        query = test_case["query"]
        category = test_case["category"]
        
        print(f"\n[{idx}/{len(TEST_QUERIES)}] {category.upper()}")
        print(f"   Query: {query[:60]}...")
        
        for run in range(1, RUNS_PER_QUERY + 1):
            print(f"   Run {run}/{RUNS_PER_QUERY}...", end=" ", flush=True)
            
            result = run_single_query(search_engine, query, category)
            result["run_number"] = run
            result["query_index"] = idx
            all_results.append(result)
            
            if result["success"]:
                print(f"✓ {result['latency_ms']:.0f}ms ({result['nodes_retrieved']} nodes)")
            else:
                print(f"✗ FAILED: {result['error']}")
    
    return all_results


def calculate_statistics(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    successful_results = [r for r in results if r["success"]]
    
    if not successful_results:
        return {"error": "No successful queries"}
    
    latencies = [r["latency_ms"] for r in successful_results]
    nodes_retrieved = [r["nodes_retrieved"] for r in successful_results]
    
    return {
        "total_queries": len(results),
        "successful_queries": len(successful_results),
        "failed_queries": len(results) - len(successful_results),
        "success_rate": (len(successful_results) / len(results)) * 100,
        "avg_latency_ms": sum(latencies) / len(latencies),
        "min_latency_ms": min(latencies),
        "max_latency_ms": max(latencies),
        "median_latency_ms": sorted(latencies)[len(latencies) // 2],
        "std_dev_latency_ms": (sum((x - sum(latencies) / len(latencies))**2 for x in latencies) / len(latencies))**0.5,
        "avg_nodes_retrieved": sum(nodes_retrieved) / len(nodes_retrieved),
        "avg_answer_length": sum(r["answer_length"] for r in successful_results) / len(successful_results)
    }


def calculate_per_category_stats(results: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    categories = {}
    
    for result in results:
        category = result["category"]
        if category not in categories:
            categories[category] = []
        categories[category].append(result)
    
    category_stats = {}
    for category, cat_results in categories.items():
        successful = [r for r in cat_results if r["success"]]
        
        if successful:
            latencies = [r["latency_ms"] for r in successful]
            category_stats[category] = {
                "count": len(cat_results),
                "successful": len(successful),
                "success_rate": (len(successful) / len(cat_results)) * 100,
                "avg_latency_ms": sum(latencies) / len(latencies),
                "std_dev_latency_ms": (sum((x - sum(latencies) / len(latencies))**2 for x in latencies) / len(latencies))**0.5 if len(latencies) > 1 else 0,
            }
        else:
            category_stats[category] = {
                "count": len(cat_results),
                "successful": 0,
                "success_rate": 0,
                "avg_latency_ms": 0,
                "std_dev_latency_ms": 0
            }
    
    return category_stats


def generate_markdown_report(results, stats, category_stats, config, search_engine) -> str:
    report = f"""# Benchmark Results - Job Application Q&A System
**Generated:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}  
**Test User:** {config.user_id}

---

## System Configuration

| Component | Specification |
|-----------|---------------|
| Python Version | {sys.version.split()[0]} |
| NodeRAG Framework | Graph-based RAG with Multi-User Support |
| Knowledge Graph Backend | Neo4j (user_id filtered) |
| Vector Search | HNSW Index (user-specific) |
| **Test User ID** | **{config.user_id}** |
| User Data Folder | {config.effective_main_folder} |

---

## Dataset Statistics

| Metric | Value |
|--------|-------|
| Total Graph Nodes | {len(search_engine.G.nodes)} |
| Total Graph Edges | {len(search_engine.G.edges)} |
| Q&A HNSW Index | {'Available' if search_engine.question_hnsw is not None else 'Not Available'} |

---

## Table 1: Overall Query Latency Results

| Metric | Value |
|--------|-------|
| **Average Latency** | **{stats['avg_latency_ms']:.2f} ms** |
| Standard Deviation | {stats['std_dev_latency_ms']:.2f} ms |
| Median Latency | {stats['median_latency_ms']:.2f} ms |
| Minimum Latency | {stats['min_latency_ms']:.2f} ms |
| Maximum Latency | {stats['max_latency_ms']:.2f} ms |
| **Success Rate** | **{stats['success_rate']:.1f}%** |
| Successful Queries | {stats['successful_queries']}/{stats['total_queries']} |
| Throughput | {60000 / stats['avg_latency_ms']:.2f} queries/min |

---

## Table 2: Performance by Query Category

| Category | Count | Successful | Success Rate | Avg Latency (ms) | Std Dev (ms) |
|----------|-------|------------|--------------|------------------|--------------|
"""
    
    for category in sorted(category_stats.keys()):
        cat_stat = category_stats[category]
        report += f"| {category} | {cat_stat['count']} | {cat_stat['successful']} | {cat_stat['success_rate']:.1f}% | {cat_stat['avg_latency_ms']:.2f} | {cat_stat['std_dev_latency_ms']:.2f} |\n"
    
    report += f"""
---

## Table 3: Retrieval Statistics

| Metric | Value |
|--------|-------|
| Average Nodes Retrieved | {stats['avg_nodes_retrieved']:.1f} |
| Average Answer Length (chars) | {stats['avg_answer_length']:.0f} |
| Total Graph Nodes Available | {len(search_engine.G.nodes)} |

---

## Files Generated

- `benchmark_results_raw.json` - Raw results data
- `benchmark_report.md` - This report

## Reproducibility

```bash
python evaluation/quick_benchmark.py {config.user_id}
```
"""
    
    return report


# ============================================================================
# Main
# ============================================================================

def main():
    print("\n" + "="*70)
    print("  JOB APPLICATION Q&A SYSTEM - BENCHMARK EVALUATION")
    print("="*70)
    
    user_id = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_USER_ID
    
    user_folder = Path(__file__).parent.parent / "POC_Data" / "documents" / "users" / user_id
    if not user_folder.exists():
        print(f"\n❌ ERROR: User folder not found: {user_folder}")
        sys.exit(1)
    
    config, search_engine = initialize_system(user_id)
    results = run_benchmark(search_engine)
    
    print("\n\n📈 Calculating statistics...")
    stats = calculate_statistics(results)
    category_stats = calculate_per_category_stats(results)
    
    print("📝 Generating markdown report...")
    report = generate_markdown_report(results, stats, category_stats, config, search_engine)
    
    output_dir = Path(__file__).parent / "results"
    output_dir.mkdir(exist_ok=True)
    
    json_file = output_dir / "benchmark_results_raw.json"
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "user_id": config.user_id,
            "statistics": stats,
            "category_statistics": category_stats,
            "all_results": results
        }, f, indent=2)
    
    md_file = output_dir / "benchmark_report.md"
    with open(md_file, "w", encoding="utf-8") as f:
        f.write(report)
    
    print("\n\n" + "="*70)
    print("  ✅ BENCHMARK COMPLETE")
    print("="*70)
    print(f"\n👤 TEST USER: {config.user_id}")
    print(f"\n📊 SUMMARY STATISTICS:")
    print(f"   • Total Queries: {stats['total_queries']}")
    print(f"   • Success Rate: {stats['success_rate']:.1f}%")
    print(f"   • Average Latency: {stats['avg_latency_ms']:.2f} ms ({stats['avg_latency_ms']/1000:.2f} sec)")
    print(f"   • Std Deviation: {stats['std_dev_latency_ms']:.2f} ms")
    print(f"   • Min/Max: {stats['min_latency_ms']:.0f} / {stats['max_latency_ms']:.0f} ms")
    print(f"   • Avg Nodes Retrieved: {stats['avg_nodes_retrieved']:.1f}")
    
    print(f"\n📁 FILES SAVED:")
    print(f"   • {json_file}")
    print(f"   • {md_file}")
    
    print("\n" + "="*70 + "\n")


if __name__ == "__main__":
    main()
