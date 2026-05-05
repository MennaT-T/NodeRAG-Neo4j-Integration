"""
Create Balanced Dataset Script

For each unique resume, samples exactly 20 job descriptions (keeping all 7 questions
per JD) so every resume contributes exactly 140 rows — regardless of how many rows
it originally had.

Input:  qa_dataset_completed_20260315_130219.csv  (18,293 rows, 73 resumes)
Output: qa_dataset_balanced_[timestamp].csv       (73 × 140 = 10,220 rows)
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

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_FILE = "qa_dataset_completed_20260315_130219.csv"
INPUT_PATH = os.path.join(SCRIPT_DIR, INPUT_FILE)

JDS_PER_RESUME = 20
QUESTIONS_PER_JD = 7
TARGET_ROWS_PER_RESUME = JDS_PER_RESUME * QUESTIONS_PER_JD  # 140
RANDOM_SEED = 42

print("\n" + "=" * 70)
print("⚖️  Create Balanced Dataset")
print("=" * 70)

# Load
print(f"\n📂 Loading: {INPUT_FILE}")
df = pd.read_csv(INPUT_PATH, encoding="utf-8", low_memory=False)
print(f"✅ Loaded {len(df):,} rows")

# Analyse current distribution
print("\n📊 Current rows per resume:")
rows_per_resume = df.groupby("Resume File Name").size().sort_values(ascending=False)
print(f"   Resumes:  {len(rows_per_resume)}")
print(f"   Max rows: {rows_per_resume.max():,}")
print(f"   Min rows: {rows_per_resume.min():,}")
print(f"   Avg rows: {rows_per_resume.mean():.0f}")

over  = (rows_per_resume > TARGET_ROWS_PER_RESUME).sum()
exact = (rows_per_resume == TARGET_ROWS_PER_RESUME).sum()
under = (rows_per_resume < TARGET_ROWS_PER_RESUME).sum()
print(f"\n   > {TARGET_ROWS_PER_RESUME} rows (will be downsampled): {over}")
print(f"   = {TARGET_ROWS_PER_RESUME} rows (kept as-is):          {exact}")
print(f"   < {TARGET_ROWS_PER_RESUME} rows (kept as-is):          {under}")

# Sample at JD level
print(f"\n✂️  Sampling {JDS_PER_RESUME} JDs × {QUESTIONS_PER_JD} questions = {TARGET_ROWS_PER_RESUME} rows per resume...")
rng = np.random.default_rng(seed=RANDOM_SEED)
sampled_indices = []

for resume, resume_df in df.groupby("Resume File Name"):
    unique_jds = resume_df["Job Description"].unique()
    n_pick = min(JDS_PER_RESUME, len(unique_jds))
    selected_jds = rng.choice(unique_jds, size=n_pick, replace=False)
    mask = resume_df["Job Description"].isin(selected_jds)
    sampled_indices.extend(resume_df[mask].index.tolist())

balanced_df = df.loc[sampled_indices].reset_index(drop=True)

# Verify
print("\n📊 Balanced rows per resume:")
balanced_counts = balanced_df.groupby("Resume File Name").size()
print(f"   Resumes:  {len(balanced_counts)}")
print(f"   Max rows: {balanced_counts.max():,}")
print(f"   Min rows: {balanced_counts.min():,}")
print(f"   Avg rows: {balanced_counts.mean():.0f}")
print(f"   Total:    {len(balanced_df):,}")

# Save
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
output_file = f"qa_dataset_balanced_{timestamp}.csv"
output_path = os.path.join(SCRIPT_DIR, output_file)

print(f"\n💾 Saving to: {output_file}")
balanced_df.to_csv(output_path, index=False, encoding="utf-8")
size_mb = os.path.getsize(output_path) / (1024 * 1024)

print("\n" + "=" * 70)
print("✅ Done!")
print("=" * 70)
print(f"   File:     {output_file}")
print(f"   Size:     {size_mb:.2f} MB")
print(f"   Rows:     {len(balanced_df):,}")
print(f"   Resumes:  {balanced_df['Resume File Name'].nunique()}")
print(f"   JDs/resume:  {JDS_PER_RESUME}  ×  {QUESTIONS_PER_JD} questions = {TARGET_ROWS_PER_RESUME} rows each")
print("=" * 70 + "\n")

