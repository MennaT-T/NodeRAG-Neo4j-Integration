"""
Split Balanced Dataset into Ingestion and Testing CSVs.

Strategy:
- For each resume, shuffle its 20 JDs and split them into two equal halves of 10.
- Ingestion CSV : first 10 JDs  → 10 × 7 = 70 rows per resume (for backend Q&A ingestion)
- Testing CSV   : second 10 JDs → 10 × 7 = 70 rows per resume (for NodeRAG evaluation)

Input:  qa_dataset_balanced_clean_20260315_131829.csv  (10,209 rows, 73 resumes, 20 JDs each)
Output: qa_dataset_ingestion_[timestamp].csv           (73 × 70 = 5,110 rows)
        qa_dataset_testing_[timestamp].csv             (73 × 70 = 5,110 rows)
"""

import pandas as pd
import numpy as np
import os
import sys
from datetime import datetime

if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
INPUT_FILE  = "qa_dataset_balanced_clean_20260315_131829.csv"
INPUT_PATH  = os.path.join(SCRIPT_DIR, INPUT_FILE)
JDS_PER_SET = 10        # 10 JDs per resume per split
RANDOM_SEED = 42

print("\n" + "=" * 70)
print("✂️   Split Dataset → Ingestion & Testing")
print("=" * 70)

print(f"\n📂 Loading: {INPUT_FILE}")
df = pd.read_csv(INPUT_PATH, encoding="utf-8", low_memory=False)
print(f"✅ Loaded {len(df):,} rows  |  {df['Resume File Name'].nunique()} resumes")

rng = np.random.default_rng(seed=RANDOM_SEED)

ingestion_indices = []
testing_indices   = []

for resume, resume_df in df.groupby("Resume File Name"):
    unique_jds = resume_df["Job Description"].unique()

    # Shuffle JDs and split into two halves
    shuffled = rng.permutation(unique_jds)
    ingestion_jds = shuffled[:JDS_PER_SET]
    testing_jds   = shuffled[JDS_PER_SET:JDS_PER_SET * 2]

    # Collect all rows for each half (all 7 questions per JD)
    ing_mask  = resume_df["Job Description"].isin(ingestion_jds)
    test_mask = resume_df["Job Description"].isin(testing_jds)

    ingestion_indices.extend(resume_df[ing_mask].index.tolist())
    testing_indices.extend(resume_df[test_mask].index.tolist())

ingestion_df = df.loc[ingestion_indices].reset_index(drop=True)
testing_df   = df.loc[testing_indices].reset_index(drop=True)

# ── Verification ──────────────────────────────────────────────────────────────
ing_counts  = ingestion_df.groupby("Resume File Name").size()
test_counts = testing_df.groupby("Resume File Name").size()

print(f"\n📊 Ingestion set:")
print(f"   Rows:               {len(ingestion_df):,}")
print(f"   Resumes:            {ingestion_df['Resume File Name'].nunique()}")
print(f"   Rows/resume — min:  {ing_counts.min()}   max: {ing_counts.max()}   avg: {ing_counts.mean():.0f}")

print(f"\n📊 Testing set:")
print(f"   Rows:               {len(testing_df):,}")
print(f"   Resumes:            {testing_df['Resume File Name'].nunique()}")
print(f"   Rows/resume — min:  {test_counts.min()}   max: {test_counts.max()}   avg: {test_counts.mean():.0f}")

print(f"\n✅ No overlap: {len(set(ingestion_indices) & set(testing_indices)) == 0}")
print(f"✅ Full coverage: {len(ingestion_indices) + len(testing_indices) == len(df)}")

# ── Save ──────────────────────────────────────────────────────────────────────
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

ing_file  = f"qa_dataset_ingestion_{timestamp}.csv"
test_file = f"qa_dataset_testing_{timestamp}.csv"

ing_path  = os.path.join(SCRIPT_DIR, ing_file)
test_path = os.path.join(SCRIPT_DIR, test_file)

ingestion_df.to_csv(ing_path,  index=False, encoding="utf-8")
testing_df.to_csv(test_path,   index=False, encoding="utf-8")

ing_mb  = os.path.getsize(ing_path)  / (1024 * 1024)
test_mb = os.path.getsize(test_path) / (1024 * 1024)

print("\n" + "=" * 70)
print("✅ Done!")
print("=" * 70)
print(f"\n   📥 Ingestion → {ing_file}")
print(f"      {len(ingestion_df):,} rows  |  {ingestion_df['Resume File Name'].nunique()} resumes  |  {JDS_PER_SET} JDs × 7 questions = 70 rows/resume  |  {ing_mb:.2f} MB")
print(f"\n   🧪 Testing   → {test_file}")
print(f"      {len(testing_df):,} rows  |  {testing_df['Resume File Name'].nunique()} resumes  |  {JDS_PER_SET} JDs × 7 questions = 70 rows/resume  |  {test_mb:.2f} MB")
print("=" * 70 + "\n")

