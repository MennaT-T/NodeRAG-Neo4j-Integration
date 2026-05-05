"""
Check the status of the benchmark dataset - which rows need LLM processing
"""
import pandas as pd
import sys
import os

if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATASET_PATH = os.path.join(SCRIPT_DIR, "benchmark_dataset_20260204_232109.csv")

df = pd.read_csv(DATASET_PATH, encoding='utf-8', low_memory=False)

print("\n" + "="*70)
print("  BENCHMARK DATASET STATUS CHECK")
print("="*70)

print(f"\n📊 Total rows: {len(df)}")

# Check empty LLM answers
mask = df["LLM Answer"].isna() | (df["LLM Answer"] == "") | (df["LLM Answer"].astype(str).str.strip() == "")
filled = (~mask).sum()
empty = mask.sum()

print(f"\n📋 LLM Answer Status:")
print(f"   ✅ Filled: {filled} ({filled/len(df)*100:.1f}%)")
print(f"   ❌ Empty: {empty} ({empty/len(df)*100:.1f}%)")

# Breakdown by source
print(f"\n📦 Breakdown by Source:")
for source in df['Source'].unique():
    source_mask = df['Source'] == source
    source_filled = (~mask & source_mask).sum()
    source_empty = (mask & source_mask).sum()
    source_total = source_mask.sum()
    
    print(f"\n   {source.upper()}:")
    print(f"      Total: {source_total}")
    print(f"      ✅ Filled: {source_filled} ({source_filled/source_total*100:.1f}%)")
    print(f"      ❌ Empty: {source_empty} ({source_empty/source_total*100:.1f}%)")

# Breakdown by category
print(f"\n🏷️  Breakdown by Category (Empty rows only):")
empty_df = df[mask]
for category in sorted(empty_df['Category'].unique()):
    count = (empty_df['Category'] == category).sum()
    print(f"   {category}: {count}")

# Show sample empty rows
print(f"\n📋 Sample Empty Rows (first 3):")
print("="*70)
for idx, row in empty_df.head(3).iterrows():
    print(f"\nRow {idx}:")
    print(f"   User ID: {row['User ID']}")
    print(f"   Category: {row['Category']}")
    print(f"   Source: {row['Source']}")
    print(f"   Question: {row['Question'][:60]}...")

print(f"\n{'='*70}")
print(f"🚀 Ready to process {empty} rows with run_llm_on_benchmark.py")
print("="*70)

