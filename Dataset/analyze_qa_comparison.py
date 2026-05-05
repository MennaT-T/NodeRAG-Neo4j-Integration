"""
Analyze QA vs NO_QA NodeRAG performance comparison
- NO_QA data from benchmark_dataset_filtered.csv (NodeRAG columns)
- QA data from benchmark_dataset_filtered_2.csv (NodeRAG columns)
- Compare both against LLM baseline
"""
import pandas as pd
import numpy as np
import sys
import os

# Fix Windows console encoding
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
NO_QA_PATH = os.path.join(SCRIPT_DIR, "benchmark_dataset_filtered.csv")
QA_PATH = os.path.join(SCRIPT_DIR, "benchmark_dataset_filtered_2.csv")

print("="*80)
print("QA vs NO_QA NODERAG COMPARISON ANALYSIS")
print("="*80)

# Load datasets
print("\n[1] LOADING DATASETS")
print("-" * 80)
df_noqa = pd.read_csv(NO_QA_PATH, low_memory=False)
df_qa = pd.read_csv(QA_PATH, low_memory=False)

print(f"NO_QA dataset: {len(df_noqa)} rows")
print(f"QA dataset: {len(df_qa)} rows")

# Filter to completed rows
llm_completed_noqa = df_noqa['LLM Answer'].notna() & (df_noqa['LLM Answer'] != '')
noderag_noqa_completed = df_noqa['NodeRAG Answer'].notna() & (df_noqa['NodeRAG Answer'] != '')

llm_completed_qa = df_qa['LLM Answer'].notna() & (df_qa['LLM Answer'] != '')
noderag_qa_completed = df_qa['NodeRAG Answer'].notna() & (df_qa['NodeRAG Answer'] != '')

print(f"\nNO_QA - Both completed: {(llm_completed_noqa & noderag_noqa_completed).sum()}")
print(f"QA - Both completed: {(llm_completed_qa & noderag_qa_completed).sum()}")

# Create completed dataframes
df_noqa_completed = df_noqa[llm_completed_noqa & noderag_noqa_completed].copy()
df_qa_completed = df_qa[llm_completed_qa & noderag_qa_completed].copy()

# Convert numeric columns
for df in [df_noqa_completed, df_qa_completed]:
    df['Tokens'] = pd.to_numeric(df['Tokens'], errors='coerce')
    df['Time'] = pd.to_numeric(df['Time'], errors='coerce')
    df['NodeRAG Tokens'] = pd.to_numeric(df['NodeRAG Tokens'], errors='coerce')
    df['NodeRAG Time'] = pd.to_numeric(df['NodeRAG Time'], errors='coerce')

print("\n[2] DATASET COMPARISON")
print("-" * 80)
print(f"NO_QA completed queries: {len(df_noqa_completed)}")
print(f"QA completed queries: {len(df_qa_completed)}")
print(f"NO_QA users: {df_noqa_completed['User ID'].nunique()}")
print(f"QA users: {df_qa_completed['User ID'].nunique()}")

print("\n[3] LLM BASELINE STATISTICS (from NO_QA dataset)")
print("-" * 80)
print(f"Average latency: {df_noqa_completed['Time'].mean():.2f}s")
print(f"Median latency: {df_noqa_completed['Time'].median():.2f}s")
print(f"Std dev latency: {df_noqa_completed['Time'].std():.2f}s")
print(f"Min latency: {df_noqa_completed['Time'].min():.2f}s")
print(f"Max latency: {df_noqa_completed['Time'].max():.2f}s")
print(f"\nAverage tokens: {df_noqa_completed['Tokens'].mean():.2f}")
print(f"Median tokens: {df_noqa_completed['Tokens'].median():.2f}")
print(f"Std dev tokens: {df_noqa_completed['Tokens'].std():.2f}")

print("\n[4] NODERAG WITHOUT QA STATISTICS")
print("-" * 80)
print(f"Average latency: {df_noqa_completed['NodeRAG Time'].mean():.2f}s")
print(f"Median latency: {df_noqa_completed['NodeRAG Time'].median():.2f}s")
print(f"Std dev latency: {df_noqa_completed['NodeRAG Time'].std():.2f}s")
print(f"Min latency: {df_noqa_completed['NodeRAG Time'].min():.2f}s")
print(f"Max latency: {df_noqa_completed['NodeRAG Time'].max():.2f}s")
print(f"\nAverage tokens: {df_noqa_completed['NodeRAG Tokens'].mean():.2f}")
print(f"Median tokens: {df_noqa_completed['NodeRAG Tokens'].median():.2f}")
print(f"Std dev tokens: {df_noqa_completed['NodeRAG Tokens'].std():.2f}")

print("\n[5] NODERAG WITH QA STATISTICS")
print("-" * 80)
print(f"Average latency: {df_qa_completed['NodeRAG Time'].mean():.2f}s")
print(f"Median latency: {df_qa_completed['NodeRAG Time'].median():.2f}s")
print(f"Std dev latency: {df_qa_completed['NodeRAG Time'].std():.2f}s")
print(f"Min latency: {df_qa_completed['NodeRAG Time'].min():.2f}s")
print(f"Max latency: {df_qa_completed['NodeRAG Time'].max():.2f}s")
print(f"\nAverage tokens: {df_qa_completed['NodeRAG Tokens'].mean():.2f}")
print(f"Median tokens: {df_qa_completed['NodeRAG Tokens'].median():.2f}")
print(f"Std dev tokens: {df_qa_completed['NodeRAG Tokens'].std():.2f}")

print("\n[6] COMPARATIVE ANALYSIS - THREE WAY COMPARISON")
print("-" * 80)

# LLM baseline stats
llm_avg = df_noqa_completed['Time'].mean()
llm_std = df_noqa_completed['Time'].std()
llm_tokens = df_noqa_completed['Tokens'].mean()

# NO_QA NodeRAG stats
noqa_avg = df_noqa_completed['NodeRAG Time'].mean()
noqa_std = df_noqa_completed['NodeRAG Time'].std()
noqa_tokens = df_noqa_completed['NodeRAG Tokens'].mean()

# QA NodeRAG stats
qa_avg = df_qa_completed['NodeRAG Time'].mean()
qa_std = df_qa_completed['NodeRAG Time'].std()
qa_tokens = df_qa_completed['NodeRAG Tokens'].mean()

print("\nLATENCY COMPARISON:")
print(f"  LLM Baseline:        {llm_avg:.2f}s")
print(f"  NodeRAG (NO_QA):     {noqa_avg:.2f}s  ({((noqa_avg - llm_avg) / llm_avg * 100):+.1f}% vs LLM)")
print(f"  NodeRAG (WITH_QA):   {qa_avg:.2f}s  ({((qa_avg - llm_avg) / llm_avg * 100):+.1f}% vs LLM)")
print(f"  QA Impact:           {qa_avg - noqa_avg:+.2f}s  ({((qa_avg - noqa_avg) / noqa_avg * 100):+.1f}%)")

print("\nCONSISTENCY (Std Dev):")
print(f"  LLM Baseline:        {llm_std:.2f}s")
print(f"  NodeRAG (NO_QA):     {noqa_std:.2f}s  ({((noqa_std - llm_std) / llm_std * 100):+.1f}% vs LLM)")
print(f"  NodeRAG (WITH_QA):   {qa_std:.2f}s  ({((qa_std - llm_std) / llm_std * 100):+.1f}% vs LLM)")
print(f"  QA Impact:           {qa_std - noqa_std:+.2f}s  ({((qa_std - noqa_std) / noqa_std * 100):+.1f}%)")

print("\nTOKEN USAGE:")
print(f"  LLM Baseline:        {llm_tokens:.0f}")
print(f"  NodeRAG (NO_QA):     {noqa_tokens:.0f}  ({((noqa_tokens - llm_tokens) / llm_tokens * 100):+.1f}% vs LLM)")
print(f"  NodeRAG (WITH_QA):   {qa_tokens:.0f}  ({((qa_tokens - llm_tokens) / llm_tokens * 100):+.1f}% vs LLM)")
print(f"  QA Impact:           {qa_tokens - noqa_tokens:+.0f}  ({((qa_tokens - noqa_tokens) / noqa_tokens * 100):+.1f}%)")

print("\n[7] CATEGORY-SPECIFIC ANALYSIS")
print("-" * 80)

print("\nNO_QA by Category:")
noqa_by_cat = df_noqa_completed.groupby('Category').agg({
    'NodeRAG Time': ['mean', 'std'],
    'NodeRAG Tokens': 'mean'
}).round(2)
print(noqa_by_cat.to_string())

print("\n\nWITH_QA by Category:")
qa_by_cat = df_qa_completed.groupby('Category').agg({
    'NodeRAG Time': ['mean', 'std'],
    'NodeRAG Tokens': 'mean'
}).round(2)
print(qa_by_cat.to_string())

print("\n\nLLM Baseline by Category (for reference):")
llm_by_cat = df_noqa_completed.groupby('Category').agg({
    'Time': ['mean', 'std'],
    'Tokens': 'mean'
}).round(2)
print(llm_by_cat.to_string())

print("\n[8] KEY INSIGHTS")
print("-" * 80)

if qa_avg < llm_avg and noqa_avg < llm_avg:
    print("✓ BOTH NodeRAG variants outperform LLM baseline")
elif qa_avg < llm_avg:
    print("✓ NodeRAG WITH QA outperforms LLM baseline")
    print("✗ NodeRAG NO_QA slower than LLM baseline")
elif noqa_avg < llm_avg:
    print("✓ NodeRAG NO_QA outperforms LLM baseline")
    print("✗ NodeRAG WITH QA slower than LLM baseline")
else:
    print("✗ Both NodeRAG variants slower than LLM baseline")

if qa_avg < noqa_avg:
    print("✓ Q&A pipeline IMPROVES latency")
elif qa_avg > noqa_avg:
    print("✗ Q&A pipeline INCREASES latency")
else:
    print("= Q&A pipeline has neutral impact on latency")

if qa_std < llm_std and noqa_std < llm_std:
    print("✓ BOTH NodeRAG variants more consistent than LLM")
elif qa_std < llm_std:
    print("✓ NodeRAG WITH QA more consistent than LLM")
else:
    print("✗ Consistency varies")

# Save results to JSON
import json
summary = {
    "llm_baseline": {
        "avg_latency": float(llm_avg),
        "std_latency": float(llm_std),
        "avg_tokens": float(llm_tokens),
        "queries": int(len(df_noqa_completed))
    },
    "noderag_no_qa": {
        "avg_latency": float(noqa_avg),
        "std_latency": float(noqa_std),
        "avg_tokens": float(noqa_tokens),
        "improvement_vs_llm_pct": float((llm_avg - noqa_avg) / llm_avg * 100),
        "variance_reduction_pct": float((llm_std - noqa_std) / llm_std * 100),
        "token_overhead_pct": float((noqa_tokens - llm_tokens) / llm_tokens * 100),
        "queries": int(len(df_noqa_completed))
    },
    "noderag_with_qa": {
        "avg_latency": float(qa_avg),
        "std_latency": float(qa_std),
        "avg_tokens": float(qa_tokens),
        "improvement_vs_llm_pct": float((llm_avg - qa_avg) / llm_avg * 100),
        "variance_reduction_pct": float((llm_std - qa_std) / llm_std * 100),
        "token_overhead_pct": float((qa_tokens - llm_tokens) / llm_tokens * 100),
        "queries": int(len(df_qa_completed))
    },
    "qa_impact": {
        "latency_diff_seconds": float(qa_avg - noqa_avg),
        "latency_diff_pct": float((qa_avg - noqa_avg) / noqa_avg * 100),
        "std_diff_seconds": float(qa_std - noqa_std),
        "std_diff_pct": float((qa_std - noqa_std) / noqa_std * 100),
        "token_diff": float(qa_tokens - noqa_tokens),
        "token_diff_pct": float((qa_tokens - noqa_tokens) / noqa_tokens * 100)
    }
}

output_file = os.path.join(SCRIPT_DIR, "qa_comparison_statistics.json")
with open(output_file, 'w', encoding='utf-8') as f:
    json.dump(summary, f, indent=2)

print(f"\n[OK] Statistics saved to: {output_file}")
print("\n" + "="*80)
print("ANALYSIS COMPLETE")
print("="*80)

