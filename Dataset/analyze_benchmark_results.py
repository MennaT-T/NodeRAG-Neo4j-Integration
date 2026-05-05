"""
Analyze benchmark dataset and extract statistics for paper
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
DATASET_PATH = os.path.join(SCRIPT_DIR, "benchmark_dataset_filtered.csv")

print("="*80)
print("BENCHMARK DATASET ANALYSIS FOR PAPER")
print("="*80)

# Load dataset
df = pd.read_csv(DATASET_PATH, low_memory=False)

print(f"\n[1] DATASET OVERVIEW")
print("-" * 80)
print(f"Total rows: {len(df):,}")
print(f"Columns: {len(df.columns)}")
print(f"Column names: {list(df.columns)}")

# Check for completed rows
llm_completed = df['LLM Answer'].notna() & (df['LLM Answer'] != '')
noderag_completed = df['NodeRAG Answer'].notna() & (df['NodeRAG Answer'] != '')

print(f"\nLLM completed rows: {llm_completed.sum():,}")
print(f"NodeRAG completed rows: {noderag_completed.sum():,}")
print(f"Both completed: {(llm_completed & noderag_completed).sum():,}")

# Filter to rows with both LLM and NodeRAG results
completed_df = df[llm_completed & noderag_completed].copy()
print(f"\nRows with both LLM and NodeRAG results: {len(completed_df):,}")

if len(completed_df) == 0:
    print("\n[ERROR] No rows with both LLM and NodeRAG results found!")
    sys.exit(1)

# Convert numeric columns
completed_df['Tokens'] = pd.to_numeric(completed_df['Tokens'], errors='coerce')
completed_df['Time'] = pd.to_numeric(completed_df['Time'], errors='coerce')
completed_df['NodeRAG Tokens'] = pd.to_numeric(completed_df['NodeRAG Tokens'], errors='coerce')
completed_df['NodeRAG Time'] = pd.to_numeric(completed_df['NodeRAG Time'], errors='coerce')

print("\n[2] DATASET CHARACTERISTICS")
print("-" * 80)

# Unique values
print(f"Unique users: {completed_df['User ID'].nunique()}")
print(f"User IDs: {sorted(completed_df['User ID'].unique())}")
print(f"\nUnique job titles: {completed_df['Job Title'].nunique()}")
print(f"Unique questions: {completed_df['Question'].nunique()}")
print(f"Unique resumes: {completed_df['Resume File Name'].nunique()}")

# Category distribution
print(f"\n[3] CATEGORY DISTRIBUTION")
print("-" * 80)
category_dist = completed_df['Category'].value_counts().sort_index()
print(category_dist.to_string())
print(f"\nTotal categories: {completed_df['Category'].nunique()}")

# Source distribution
print(f"\n[4] SOURCE DISTRIBUTION")
print("-" * 80)
source_dist = completed_df['Source'].value_counts()
print(source_dist.to_string())

# Per-user statistics
print(f"\n[5] PER-USER DISTRIBUTION")
print("-" * 80)
user_counts = completed_df.groupby('User ID').size().sort_values(ascending=False)
print(user_counts.to_string())

print(f"\n[6] LLM PERFORMANCE STATISTICS")
print("-" * 80)
print(f"Average tokens: {completed_df['Tokens'].mean():.2f}")
print(f"Median tokens: {completed_df['Tokens'].median():.2f}")
print(f"Std dev tokens: {completed_df['Tokens'].std():.2f}")
print(f"Min tokens: {completed_df['Tokens'].min():.0f}")
print(f"Max tokens: {completed_df['Tokens'].max():.0f}")
print(f"\nAverage time (seconds): {completed_df['Time'].mean():.2f}")
print(f"Median time (seconds): {completed_df['Time'].median():.2f}")
print(f"Std dev time (seconds): {completed_df['Time'].std():.2f}")
print(f"Min time (seconds): {completed_df['Time'].min():.2f}")
print(f"Max time (seconds): {completed_df['Time'].max():.2f}")

print(f"\n[7] NODERAG PERFORMANCE STATISTICS")
print("-" * 80)
print(f"Average tokens: {completed_df['NodeRAG Tokens'].mean():.2f}")
print(f"Median tokens: {completed_df['NodeRAG Tokens'].median():.2f}")
print(f"Std dev tokens: {completed_df['NodeRAG Tokens'].std():.2f}")
print(f"Min tokens: {completed_df['NodeRAG Tokens'].min():.0f}")
print(f"Max tokens: {completed_df['NodeRAG Tokens'].max():.0f}")
print(f"\nAverage time (seconds): {completed_df['NodeRAG Time'].mean():.2f}")
print(f"Median time (seconds): {completed_df['NodeRAG Time'].median():.2f}")
print(f"Std dev time (seconds): {completed_df['NodeRAG Time'].std():.2f}")
print(f"Min time (seconds): {completed_df['NodeRAG Time'].min():.2f}")
print(f"Max time (seconds): {completed_df['NodeRAG Time'].max():.2f}")

print(f"\n[8] COMPARATIVE ANALYSIS (NodeRAG vs LLM)")
print("-" * 80)
token_diff = completed_df['NodeRAG Tokens'] - completed_df['Tokens']
time_diff = completed_df['NodeRAG Time'] - completed_df['Time']

print(f"Average token difference (NodeRAG - LLM): {token_diff.mean():.2f}")
print(f"Average time difference (NodeRAG - LLM): {time_diff.mean():.2f} seconds")
print(f"\nNodeRAG uses {(token_diff.mean() / completed_df['Tokens'].mean() * 100):.1f}% more tokens on average")
print(f"NodeRAG takes {(time_diff.mean() / completed_df['Time'].mean() * 100):.1f}% more time on average")

print(f"\n[9] PER-CATEGORY STATISTICS")
print("-" * 80)
print("\nLLM by Category:")
llm_by_cat = completed_df.groupby('Category').agg({
    'Tokens': ['count', 'mean', 'std'],
    'Time': ['mean', 'std']
}).round(2)
print(llm_by_cat.to_string())

print("\n\nNodeRAG by Category:")
noderag_by_cat = completed_df.groupby('Category').agg({
    'NodeRAG Tokens': ['count', 'mean', 'std'],
    'NodeRAG Time': ['mean', 'std']
}).round(2)
print(noderag_by_cat.to_string())

print(f"\n[10] ANSWER LENGTH STATISTICS")
print("-" * 80)
completed_df['LLM Answer Length'] = completed_df['LLM Answer'].str.len()
completed_df['NodeRAG Answer Length'] = completed_df['NodeRAG Answer'].str.len()

print(f"LLM average answer length (chars): {completed_df['LLM Answer Length'].mean():.0f}")
print(f"LLM median answer length (chars): {completed_df['LLM Answer Length'].median():.0f}")
print(f"\nNodeRAG average answer length (chars): {completed_df['NodeRAG Answer Length'].mean():.0f}")
print(f"NodeRAG median answer length (chars): {completed_df['NodeRAG Answer Length'].median():.0f}")

print(f"\n[11] SUCCESS RATE")
print("-" * 80)
total_rows_attempted = len(df)
llm_success_rate = (llm_completed.sum() / total_rows_attempted) * 100
noderag_success_rate = (noderag_completed.sum() / total_rows_attempted) * 100

print(f"LLM success rate: {llm_success_rate:.1f}% ({llm_completed.sum():,}/{total_rows_attempted:,})")
print(f"NodeRAG success rate: {noderag_success_rate:.1f}% ({noderag_completed.sum():,}/{total_rows_attempted:,})")

# Save summary statistics to JSON
summary = {
    "dataset_overview": {
        "total_rows": len(df),
        "llm_completed": int(llm_completed.sum()),
        "noderag_completed": int(noderag_completed.sum()),
        "both_completed": int((llm_completed & noderag_completed).sum()),
        "unique_users": int(completed_df['User ID'].nunique()),
        "unique_job_titles": int(completed_df['Job Title'].nunique()),
        "unique_questions": int(completed_df['Question'].nunique()),
        "unique_resumes": int(completed_df['Resume File Name'].nunique()),
        "unique_categories": int(completed_df['Category'].nunique())
    },
    "llm_stats": {
        "avg_tokens": float(completed_df['Tokens'].mean()),
        "median_tokens": float(completed_df['Tokens'].median()),
        "std_tokens": float(completed_df['Tokens'].std()),
        "min_tokens": float(completed_df['Tokens'].min()),
        "max_tokens": float(completed_df['Tokens'].max()),
        "avg_time_seconds": float(completed_df['Time'].mean()),
        "median_time_seconds": float(completed_df['Time'].median()),
        "std_time_seconds": float(completed_df['Time'].std()),
        "min_time_seconds": float(completed_df['Time'].min()),
        "max_time_seconds": float(completed_df['Time'].max()),
        "avg_answer_length": float(completed_df['LLM Answer Length'].mean()),
        "median_answer_length": float(completed_df['LLM Answer Length'].median())
    },
    "noderag_stats": {
        "avg_tokens": float(completed_df['NodeRAG Tokens'].mean()),
        "median_tokens": float(completed_df['NodeRAG Tokens'].median()),
        "std_tokens": float(completed_df['NodeRAG Tokens'].std()),
        "min_tokens": float(completed_df['NodeRAG Tokens'].min()),
        "max_tokens": float(completed_df['NodeRAG Tokens'].max()),
        "avg_time_seconds": float(completed_df['NodeRAG Time'].mean()),
        "median_time_seconds": float(completed_df['NodeRAG Time'].median()),
        "std_time_seconds": float(completed_df['NodeRAG Time'].std()),
        "min_time_seconds": float(completed_df['NodeRAG Time'].min()),
        "max_time_seconds": float(completed_df['NodeRAG Time'].max()),
        "avg_answer_length": float(completed_df['NodeRAG Answer Length'].mean()),
        "median_answer_length": float(completed_df['NodeRAG Answer Length'].median())
    },
    "comparative": {
        "avg_token_diff": float(token_diff.mean()),
        "avg_time_diff": float(time_diff.mean()),
        "token_diff_percent": float((token_diff.mean() / completed_df['Tokens'].mean() * 100)),
        "time_diff_percent": float((time_diff.mean() / completed_df['Time'].mean() * 100))
    },
    "category_distribution": category_dist.to_dict(),
    "source_distribution": source_dist.to_dict(),
    "per_user_counts": user_counts.to_dict()
}

import json
output_file = os.path.join(SCRIPT_DIR, "benchmark_statistics.json")
with open(output_file, 'w', encoding='utf-8') as f:
    json.dump(summary, f, indent=2)

print(f"\n[OK] Statistics saved to: {output_file}")
print("\n" + "="*80)
print("ANALYSIS COMPLETE")
print("="*80)

