"""
Quick Benchmark Script for Job Application Q&A System
======================================================
Processes benchmark dataset CSV with NodeRAG and saves results.

Run: python quick_benchmark.py --csv [path_to_csv]
Example: python quick_benchmark.py --csv Dataset/benchmark_dataset_20260204_232109.csv
"""

import sys
import time
import json
import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional
import yaml

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from NodeRAG import NodeConfig, NodeSearch

# ============================================================================
# Configuration
# ============================================================================

SAVE_INTERVAL = 50  # Save CSV every 50 rows processed

# ============================================================================
# Functions
# ============================================================================

def initialize_system(user_id: str) -> tuple:
    """Initialize NodeRAG system for a specific user"""
    
    user_config_path = Path(__file__).parent / "POC_Data" / "documents" / "users" / user_id / "Node_config.yaml"
    root_config_path = Path(__file__).parent / "Node_config.yaml"
    
    # If user has their own config, use it directly (it already has correct paths)
    if user_config_path.exists():
        with open(user_config_path, 'r') as f:
            config_data = yaml.safe_load(f)
        config = NodeConfig(config_data)
    else:
        # Use root config and set user_id to route to user folder
        with open(root_config_path, 'r') as f:
            config_data = yaml.safe_load(f)
        if 'config' not in config_data:
            config_data['config'] = {}
        # Strip "user_" prefix if present since NodeConfig adds it
        clean_user_id = user_id.replace('user_', '') if user_id.startswith('user_') else user_id
        config_data['config']['user_id'] = clean_user_id
        config = NodeConfig(config_data)
    
    search_engine = NodeSearch(config)
    
    return config, search_engine


def initialize_all_users(user_ids: List[str]) -> Dict[str, NodeSearch]:
    """Initialize NodeRAG systems for all users"""
    print(f"\n🔧 Initializing NodeRAG for {len(user_ids)} users...")
    print("=" * 70)
    
    search_engines = {}
    
    for user_id in user_ids:
        try:
            print(f"   {user_id}...", end=" ", flush=True)
            config, search_engine = initialize_system(user_id)
            search_engines[user_id] = search_engine
            print(f"✓ ({len(search_engine.G.nodes)} nodes)")
        except Exception as e:
            print(f"✗ Failed: {str(e)}")
    
    print(f"\n✅ Initialized {len(search_engines)}/{len(user_ids)} users")
    return search_engines


def process_single_row(
    search_engine: NodeSearch, 
    query: str, 
    job_description: str,
    category: str,
    row_index: int,
    disable_qa: bool = False
) -> Dict[str, Any]:
    """Process a single row from the dataset"""
    start_time = time.time()
    
    try:
        # Call NodeRAG with job context (and optionally disable QA)
        result = search_engine.answer(query, job_context=job_description, disable_qa=disable_qa)
        latency_ms = (time.time() - start_time) * 1000
        
        retrieval = result.retrieval
        nodes_retrieved = len(retrieval.search_list) if hasattr(retrieval, 'search_list') else 0
        
        # Get token counts (built-in to Answer object)
        retrieval_tokens = result.retrieval_tokens if hasattr(result, 'retrieval_tokens') else 0
        response_tokens = result.response_tokens if hasattr(result, 'response_tokens') else 0
        total_tokens = retrieval_tokens + response_tokens
        
        return {
            "success": True,
            "row_index": row_index,
            "query": query,
            "category": category,
            "answer": result.response,
            "latency_ms": latency_ms,
            "latency_seconds": latency_ms / 1000,
            "nodes_retrieved": nodes_retrieved,
            "answer_length": len(result.response),
            "retrieval_tokens": retrieval_tokens,
            "response_tokens": response_tokens,
            "total_tokens": total_tokens,
            "error": None
        }
    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000
        print(f"❌ Row {row_index}: Error - {str(e)}")
        return {
            "success": False,
            "row_index": row_index,
            "query": query,
            "category": category,
            "answer": "",
            "latency_ms": latency_ms,
            "latency_seconds": latency_ms / 1000,
            "nodes_retrieved": 0,
            "answer_length": 0,
            "retrieval_tokens": 0,
            "response_tokens": 0,
            "total_tokens": 0,
            "error": str(e)
        }


def process_csv_dataset(
    df: pd.DataFrame,
    search_engines: Dict[str, NodeSearch],
    csv_path: Path,
    max_rows: Optional[int] = None,
    mode: str = "qa"  # "qa" or "no_qa"
) -> List[Dict[str, Any]]:
    """Process dataset CSV with NodeRAG"""
    
    # Determine which columns to use based on mode
    if mode == "no_qa":
        answer_col = "NO_QA_NodeRAG Answer"
        tokens_col = "NO_QA_NodeRAG Tokens"
        time_col = "NO_QA_NodeRAG Time"
        disable_qa = True
        mode_label = "NO_QA"
    else:
        answer_col = "NodeRAG Answer"
        tokens_col = "NodeRAG Tokens"
        time_col = "NodeRAG Time"
        disable_qa = False
        mode_label = "QA"
    
    # Find rows that need processing (empty answer column)
    mask = df[answer_col].isna() | (df[answer_col] == "") | (df[answer_col].astype(str).str.strip() == "")
    rows_to_process = df[mask].head(max_rows) if max_rows else df[mask]
    
    total_rows = len(rows_to_process)
    
    print(f"\n📊 Dataset Processing ({mode_label} Mode)")
    print("=" * 70)
    print(f"Total rows in dataset: {len(df):,}")
    print(f"Already processed ({mode_label}): {(~mask).sum():,}")
    print(f"To process ({mode_label}): {total_rows:,}")
    
    if total_rows == 0:
        print("\n✅ All rows already processed!")
        return []
    
    all_results = []
    processed_count = 0
    successful_count = 0
    failed_count = 0
    
    for batch_start in range(0, total_rows, SAVE_INTERVAL):
        batch_end = min(batch_start + SAVE_INTERVAL, total_rows)
        batch_rows = rows_to_process.iloc[batch_start:batch_end]
        
        print(f"\n{'='*70}")
        print(f"📦 Processing batch: rows {batch_start + 1} to {batch_end} of {total_rows}")
        print(f"{'='*70}")
        
        batch_successful = 0
        
        for idx, (df_idx, row) in enumerate(batch_rows.iterrows(), 1):
            user_id = row['User ID']
            query = row['Question']
            job_description = row['Job Description']
            category = row['Category']
            
            # Get search engine for this user
            if user_id not in search_engines:
                print(f"⚠️  Row {df_idx}: User {user_id} not initialized, skipping...")
                continue
            
            search_engine = search_engines[user_id]
            
            # Progress indicator
            print(f"[{batch_start + idx}/{total_rows}] {user_id} | {category} | {query[:40]}...", end=" ", flush=True)
            
            # Process the row
            result = process_single_row(
                search_engine,
                query,
                job_description,
                category,
                df_idx,
                disable_qa=disable_qa
            )
            
            if result["success"]:
                # Update dataframe with correct columns based on mode
                df.at[df_idx, answer_col] = result["answer"]
                df.at[df_idx, tokens_col] = result["total_tokens"]
                df.at[df_idx, time_col] = f"{result['latency_seconds']:.2f}"
                
                successful_count += 1
                batch_successful += 1
                
                print(f"✓ {result['latency_ms']:.0f}ms | {result['total_tokens']} tok")
            else:
                failed_count += 1
                print(f"✗ FAILED")
            
            all_results.append(result)
            processed_count += 1
        
        # Save progress after each batch
        save_dataframe(df, csv_path)
        
        print(f"\n📈 Batch Summary:")
        print(f"   ✅ Successful: {batch_successful}/{len(batch_rows)}")
        print(f"   📊 Overall progress: {processed_count}/{total_rows} ({processed_count/total_rows*100:.1f}%)")
        print(f"   ✅ Total successful: {successful_count}")
        print(f"   ❌ Total failed: {failed_count}")
    
    return all_results


def save_dataframe(df: pd.DataFrame, csv_path: Path):
    """Save dataframe to CSV"""
    try:
        df.to_csv(csv_path, index=False, encoding='utf-8')
        print(f"💾 Saved progress to {csv_path.name}")
    except Exception as e:
        backup_path = csv_path.parent / f"{csv_path.stem}_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        df.to_csv(backup_path, index=False, encoding='utf-8')
        print(f"⚠️  Saved to backup: {backup_path.name}")


def calculate_statistics(results: List[Dict[str, Any]], df: pd.DataFrame) -> Dict[str, Any]:
    """Calculate comprehensive statistics from results"""
    successful_results = [r for r in results if r["success"]]
    
    if not successful_results:
        return {"error": "No successful queries"}
    
    latencies = [r["latency_ms"] for r in successful_results]
    nodes_retrieved = [r["nodes_retrieved"] for r in successful_results]
    retrieval_tokens = [r["retrieval_tokens"] for r in successful_results]
    response_tokens = [r["response_tokens"] for r in successful_results]
    total_tokens = [r["total_tokens"] for r in successful_results]
    
    stats = {
        "total_queries": len(results),
        "successful_queries": len(successful_results),
        "failed_queries": len(results) - len(successful_results),
        "success_rate": (len(successful_results) / len(results)) * 100,
        
        # Latency statistics
        "avg_latency_ms": sum(latencies) / len(latencies),
        "min_latency_ms": min(latencies),
        "max_latency_ms": max(latencies),
        "median_latency_ms": sorted(latencies)[len(latencies) // 2],
        "std_dev_latency_ms": (sum((x - sum(latencies) / len(latencies))**2 for x in latencies) / len(latencies))**0.5,
        
        # Retrieval statistics
        "avg_nodes_retrieved": sum(nodes_retrieved) / len(nodes_retrieved),
        "avg_answer_length": sum(r["answer_length"] for r in successful_results) / len(successful_results),
        
        # Token statistics
        "avg_retrieval_tokens": sum(retrieval_tokens) / len(retrieval_tokens),
        "avg_response_tokens": sum(response_tokens) / len(response_tokens),
        "avg_total_tokens": sum(total_tokens) / len(total_tokens),
        "total_tokens_used": sum(total_tokens),
        "min_total_tokens": min(total_tokens),
        "max_total_tokens": max(total_tokens),
        
        # Dataset statistics
        "unique_users": df['User ID'].nunique(),
        "unique_categories": df['Category'].nunique(),
        "total_rows_in_dataset": len(df)
    }
    
    return stats


def calculate_per_category_stats(results: List[Dict[str, Any]], df: pd.DataFrame) -> Dict[str, Dict[str, Any]]:
    """Calculate statistics grouped by category"""
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
            tokens = [r["total_tokens"] for r in successful]
            category_stats[category] = {
                "count": len(cat_results),
                "successful": len(successful),
                "success_rate": (len(successful) / len(cat_results)) * 100,
                "avg_latency_ms": sum(latencies) / len(latencies),
                "std_dev_latency_ms": (sum((x - sum(latencies) / len(latencies))**2 for x in latencies) / len(latencies))**0.5 if len(latencies) > 1 else 0,
                "avg_tokens": sum(tokens) / len(tokens),
                "total_in_dataset": (df['Category'] == category).sum()
            }
        else:
            category_stats[category] = {
                "count": len(cat_results),
                "successful": 0,
                "success_rate": 0,
                "avg_latency_ms": 0,
                "std_dev_latency_ms": 0,
                "avg_tokens": 0,
                "total_in_dataset": (df['Category'] == category).sum()
            }
    
    return category_stats


def calculate_per_user_stats(results: List[Dict[str, Any]], df: pd.DataFrame) -> Dict[str, Dict[str, Any]]:
    """Calculate statistics grouped by user"""
    # Get user_id from df using row_index
    user_stats = {}
    
    for result in results:
        if not result["success"]:
            continue
            
        row_idx = result["row_index"]
        user_id = df.loc[row_idx, 'User ID']
        
        if user_id not in user_stats:
            user_stats[user_id] = {
                "latencies": [],
                "tokens": [],
                "nodes": [],
                "count": 0,
                "successful": 0
            }
        
        user_stats[user_id]["latencies"].append(result["latency_ms"])
        user_stats[user_id]["tokens"].append(result["total_tokens"])
        user_stats[user_id]["nodes"].append(result["nodes_retrieved"])
        user_stats[user_id]["count"] += 1
        user_stats[user_id]["successful"] += 1
    
    # Calculate averages
    final_stats = {}
    for user_id, data in user_stats.items():
        if data["successful"] > 0:
            final_stats[user_id] = {
                "count": data["count"],
                "successful": data["successful"],
                "avg_latency_ms": sum(data["latencies"]) / len(data["latencies"]),
                "avg_tokens": sum(data["tokens"]) / len(data["tokens"]),
                "avg_nodes": sum(data["nodes"]) / len(data["nodes"]),
                "total_in_dataset": (df['User ID'] == user_id).sum()
            }
    
    return final_stats


def save_statistics_json(stats: Dict, category_stats: Dict, user_stats: Dict, output_dir: Path):
    """Save all statistics to JSON file"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_file = output_dir / f"benchmark_statistics_{timestamp}.json"
    
    output_data = {
        "timestamp": datetime.now().isoformat(),
        "overall_statistics": stats,
        "category_statistics": category_stats,
        "user_statistics": user_stats
    }
    
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    
    print(f"\n📊 Statistics saved to: {json_file.name}")
    return json_file


def generate_markdown_report_old(results, stats, category_stats, config, search_engine) -> str:
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

## Table 2: Token Usage Statistics

| Metric | Value |
|--------|-------|
| **Average Total Tokens per Query** | **{stats['avg_total_tokens']:.1f}** |
| Average Retrieval Tokens (Context) | {stats['avg_retrieval_tokens']:.1f} |
| Average Response Tokens (Generated) | {stats['avg_response_tokens']:.1f} |
| **Total Tokens Used (All Queries)** | **{stats['total_tokens_used']:,}** |
| Min Tokens per Query | {stats['min_total_tokens']} |
| Max Tokens per Query | {stats['max_total_tokens']} |

---

## Table 3: Performance by Query Category

| Category | Count | Successful | Success Rate | Avg Latency (ms) | Avg Tokens | Std Dev (ms) |
|----------|-------|------------|--------------|------------------|------------|--------------|
"""
    
    for category in sorted(category_stats.keys()):
        cat_stat = category_stats[category]
        report += f"| {category} | {cat_stat['count']} | {cat_stat['successful']} | {cat_stat['success_rate']:.1f}% | {cat_stat['avg_latency_ms']:.2f} | {cat_stat['avg_tokens']:.1f} | {cat_stat['std_dev_latency_ms']:.2f} |\n"
    
    report += f"""
---

## Table 4: Retrieval Statistics

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
    print("  Processing Dataset CSV with NodeRAG")
    print("="*70)
    
    # Parse command line arguments
    csv_path = None
    max_rows = None
    
    for i, arg in enumerate(sys.argv[1:]):
        if arg == "--csv" and i + 1 < len(sys.argv) - 1:
            csv_path = Path(sys.argv[i + 2])
        elif arg == "--max" and i + 1 < len(sys.argv) - 1:
            try:
                max_rows = int(sys.argv[i + 2])
            except ValueError:
                print(f"⚠️  Invalid max rows: {sys.argv[i + 2]}")
    
    # Default CSV path
    if not csv_path:
        csv_path = Path("Dataset/benchmark_dataset_filtered.csv")
        print(f"📂 Using default CSV: {csv_path}")
    
    # Check if CSV exists
    if not csv_path.exists():
        print(f"❌ Error: CSV file not found: {csv_path}")
        print(f"\nUsage: python quick_benchmark.py --csv [path_to_csv] [--max N]")
        sys.exit(1)
    
    # Load dataset
    print(f"\n📂 Loading dataset from: {csv_path.name}")
    try:
        df = pd.read_csv(csv_path, encoding='utf-8', low_memory=False)
        print(f"✅ Loaded {len(df):,} rows")
    except Exception as e:
        print(f"❌ Error loading CSV: {e}")
        sys.exit(1)
    
    # Verify required columns
    required_columns = ['User ID', 'Question', 'Job Description', 'Category', 'NodeRAG Answer', 'NodeRAG Tokens', 'NodeRAG Time']
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        print(f"❌ Missing required columns: {missing_columns}")
        sys.exit(1)
    
    # Convert columns to appropriate dtypes
    df["NodeRAG Answer"] = df["NodeRAG Answer"].astype(object)
    df["NodeRAG Tokens"] = df["NodeRAG Tokens"].astype(object)
    df["NodeRAG Time"] = df["NodeRAG Time"].astype(object)
    df["NO_QA_NodeRAG Answer"] = df["NO_QA_NodeRAG Answer"].astype(object)
    df["NO_QA_NodeRAG Tokens"] = df["NO_QA_NodeRAG Tokens"].astype(object)
    df["NO_QA_NodeRAG Time"] = df["NO_QA_NodeRAG Time"].astype(object)
    
    # Get unique user IDs from dataset
    user_ids = sorted(df['User ID'].unique())
    print(f"\n👥 Found {len(user_ids)} unique users: {', '.join(user_ids)}")
    
    # Initialize all user search engines
    search_engines = initialize_all_users(user_ids)
    
    if not search_engines:
        print("❌ No users could be initialized")
        sys.exit(1)
    
    # Process dataset - BOTH modes (QA and NO_QA)
    print(f"\n🚀 Starting benchmark processing (QA and NO_QA modes)...")
    if max_rows:
        print(f"   Limit: {max_rows} rows per mode")
    
    start_time = time.time()
    all_results = []
    
    # Mode 1: Process with QA enabled
    try:
        print(f"\n{'='*70}")
        print("  PHASE 1: Processing with QA ENABLED")
        print(f"{'='*70}")
        results_qa = process_csv_dataset(df, search_engines, csv_path, max_rows, mode="qa")
        all_results.extend(results_qa)
    except KeyboardInterrupt:
        print("\n\n⚠️  QA mode interrupted by user. Progress has been saved.")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error during QA processing: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    # Mode 2: Process with QA disabled  
    try:
        print(f"\n{'='*70}")
        print("  PHASE 2: Processing with QA DISABLED (NO_QA)")
        print(f"{'='*70}")
        results_no_qa = process_csv_dataset(df, search_engines, csv_path, max_rows, mode="no_qa")
        all_results.extend(results_no_qa)
    except KeyboardInterrupt:
        print("\n\n⚠️  NO_QA mode interrupted by user. Progress has been saved.")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error during NO_QA processing: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    total_time = time.time() - start_time
    
    if not all_results:
        print("\n✅ No rows needed processing!")
        sys.exit(0)
    
    results = all_results  # Use combined results for statistics
    
    # Calculate statistics
    print(f"\n📊 Calculating statistics...")
    stats = calculate_statistics(results, df)
    category_stats = calculate_per_category_stats(results, df)
    user_stats = calculate_per_user_stats(results, df)
    
    # Save statistics to JSON
    output_dir = Path("results")
    output_dir.mkdir(exist_ok=True)
    
    json_file = save_statistics_json(stats, category_stats, user_stats, output_dir)
    
    # Print summary
    print(f"\n\n{'='*70}")
    print("  ✅ BENCHMARK COMPLETE")
    print("="*70)
    
    print(f"\n⏱️  TIMING:")
    print(f"   Total time: {total_time:.2f}s ({total_time/60:.1f} minutes)")
    
    print(f"\n📊 OVERALL STATISTICS:")
    print(f"   • Total Queries: {stats['total_queries']}")
    print(f"   • Success Rate: {stats['success_rate']:.1f}%")
    print(f"   • Average Latency: {stats['avg_latency_ms']:.2f} ms")
    print(f"   • Average Tokens: {stats['avg_total_tokens']:.1f}")
    print(f"   • Total Tokens Used: {stats['total_tokens_used']:,}")
    
    print(f"\n📋 BY CATEGORY:")
    for category in sorted(category_stats.keys()):
        cat_stat = category_stats[category]
        print(f"   • {category:20s}: {cat_stat['successful']:3d} processed, "
              f"{cat_stat['avg_latency_ms']:6.1f}ms avg, "
              f"{cat_stat['avg_tokens']:6.1f} tokens avg")
    
    print(f"\n👥 BY USER:")
    for user_id in sorted(user_stats.keys()):
        user_stat = user_stats[user_id]
        print(f"   • {user_id}: {user_stat['successful']:3d} processed, "
              f"{user_stat['avg_latency_ms']:6.1f}ms avg, "
              f"{user_stat['avg_tokens']:6.1f} tokens avg")
    
    print(f"\n📁 FILES:")
    print(f"   • Dataset CSV (updated): {csv_path.name}")
    print(f"   • Statistics JSON: {json_file.name}")
    
    print("\n" + "="*70 + "\n")


if __name__ == "__main__":
    main()
