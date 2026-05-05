"""
Dataset Splitting Script for Ingestion and Testing

This script splits the completed QA dataset into two subsets:
1. Ingestion CSV: 10 random job descriptions per unique resume (for backend Q&A pipeline)
2. Testing CSV: All remaining rows (for NodeRAG evaluation)

Strategy:
- For each unique resume, randomly select 10 job descriptions
- Include ALL questions for those selected job descriptions
- Ensures both datasets have diverse representation
"""

import pandas as pd
import os
import sys
import numpy as np
from datetime import datetime
from collections import defaultdict

# Fix Windows console encoding for emojis
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Get the directory where this script is located
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Configuration
COMPLETED_CSV = "qa_dataset_completed_20260204_175205.csv"
INPUT_PATH = os.path.join(SCRIPT_DIR, COMPLETED_CSV)
JOB_DESCRIPTIONS_PER_RESUME = 10  # Number of job descriptions to select per resume
RANDOM_SEED = 42  # For reproducibility


def load_dataset():
    """Load the completed dataset"""
    print(f"📂 Loading dataset: {COMPLETED_CSV}")
    print("⏳ This may take a moment for large files...\n")
    
    try:
        df = pd.read_csv(INPUT_PATH, encoding='utf-8', low_memory=False)
        print(f"✅ Loaded {len(df):,} rows")
        return df
    except Exception as e:
        print(f"❌ Error loading dataset: {e}")
        return None


def analyze_dataset_structure(df):
    """Analyze the dataset structure before splitting"""
    print("\n" + "="*80)
    print("🔍 DATASET ANALYSIS")
    print("="*80)
    
    unique_resumes = df["Resume File Name"].nunique()
    unique_job_descriptions = df["Job Description"].nunique()
    unique_questions = df["Question"].nunique()
    unique_job_titles = df["Job Title"].nunique()
    
    print(f"\nDataset Structure:")
    print(f"   Total rows:              {len(df):>10,}")
    print(f"   Unique resumes:          {unique_resumes:>10,}")
    print(f"   Unique job descriptions: {unique_job_descriptions:>10,}")
    print(f"   Unique questions:        {unique_questions:>10,}")
    print(f"   Unique job titles:       {unique_job_titles:>10,}")
    
    # Analyze rows per resume
    rows_per_resume = df.groupby("Resume File Name").size()
    print(f"\nRows per Resume Statistics:")
    print(f"   Average:                 {rows_per_resume.mean():>10,.1f}")
    print(f"   Median:                  {rows_per_resume.median():>10,.0f}")
    print(f"   Min:                     {rows_per_resume.min():>10,}")
    print(f"   Max:                     {rows_per_resume.max():>10,}")
    
    # Analyze unique job descriptions per resume
    job_desc_per_resume = df.groupby("Resume File Name")["Job Description"].nunique()
    print(f"\nUnique Job Descriptions per Resume:")
    print(f"   Average:                 {job_desc_per_resume.mean():>10,.1f}")
    print(f"   Median:                  {job_desc_per_resume.median():>10,.0f}")
    print(f"   Min:                     {job_desc_per_resume.min():>10,}")
    print(f"   Max:                     {job_desc_per_resume.max():>10,}")
    
    # Check if any resume has fewer than target job descriptions
    resumes_below_target = (job_desc_per_resume < JOB_DESCRIPTIONS_PER_RESUME).sum()
    if resumes_below_target > 0:
        print(f"\n⚠️  Warning: {resumes_below_target} resume(s) have fewer than {JOB_DESCRIPTIONS_PER_RESUME} job descriptions")
        print(f"   These will include all available job descriptions")
    
    return unique_resumes, job_desc_per_resume


def split_dataset(df, job_descriptions_per_resume=10, random_seed=42):
    """
    Split dataset into ingestion and testing subsets.
    
    Strategy:
    - For each unique resume, randomly select N job descriptions
    - Include ALL rows (all questions) for those selected job descriptions
    - Remaining rows go to testing set
    """
    print("\n" + "="*80)
    print("✂️  SPLITTING DATASET")
    print("="*80)
    
    print(f"\nStrategy:")
    print(f"   • For each unique resume: select {job_descriptions_per_resume} random job descriptions")
    print(f"   • Include ALL questions for selected job descriptions")
    print(f"   • Random seed: {random_seed} (for reproducibility)")
    
    # Set random seed for reproducibility
    np.random.seed(random_seed)
    
    # Get unique resumes
    unique_resumes = df["Resume File Name"].unique()
    print(f"\n🔄 Processing {len(unique_resumes):,} unique resumes...")
    
    # Track selected row indices
    ingestion_indices = []
    
    # Process each resume
    resumes_processed = 0
    for resume in unique_resumes:
        # Get all rows for this resume
        resume_mask = df["Resume File Name"] == resume
        resume_df = df[resume_mask]
        
        # Get unique job descriptions for this resume
        unique_job_descs = resume_df["Job Description"].unique()
        num_available = len(unique_job_descs)
        
        # Select N job descriptions (or all if less than N available)
        num_to_select = min(job_descriptions_per_resume, num_available)
        selected_job_descs = np.random.choice(
            unique_job_descs, 
            size=num_to_select, 
            replace=False
        )
        
        # Get all row indices for the selected job descriptions
        for job_desc in selected_job_descs:
            mask = (df["Resume File Name"] == resume) & (df["Job Description"] == job_desc)
            indices = df[mask].index.tolist()
            ingestion_indices.extend(indices)
        
        resumes_processed += 1
        if resumes_processed % 10 == 0:
            print(f"   Processed {resumes_processed}/{len(unique_resumes)} resumes...", end='\r')
    
    print(f"   Processed {resumes_processed}/{len(unique_resumes)} resumes... Done!     ")
    
    # Create the two datasets
    print("\n📊 Creating datasets...")
    
    # Ingestion dataset: selected rows
    ingestion_df = df.loc[ingestion_indices].copy()
    
    # Testing dataset: remaining rows
    testing_mask = ~df.index.isin(ingestion_indices)
    testing_df = df[testing_mask].copy()
    
    print(f"✅ Split complete!")
    
    return ingestion_df, testing_df


def analyze_split_results(ingestion_df, testing_df, original_df):
    """Analyze the results of the split"""
    print("\n" + "="*80)
    print("📊 SPLIT RESULTS ANALYSIS")
    print("="*80)
    
    print(f"\n{'Metric':<35} {'Ingestion Set':>15} {'Testing Set':>15} {'Total':>15}")
    print("-" * 80)
    
    # Row counts
    print(f"{'Total Rows':<35} {len(ingestion_df):>15,} {len(testing_df):>15,} {len(original_df):>15,}")
    
    # Percentages
    ing_pct = len(ingestion_df) / len(original_df) * 100
    test_pct = len(testing_df) / len(original_df) * 100
    print(f"{'Percentage':<35} {ing_pct:>14.1f}% {test_pct:>14.1f}% {100.0:>14.1f}%")
    
    print()
    
    # Unique entities
    ing_resumes = ingestion_df["Resume File Name"].nunique()
    test_resumes = testing_df["Resume File Name"].nunique()
    total_resumes = original_df["Resume File Name"].nunique()
    print(f"{'Unique Resumes':<35} {ing_resumes:>15,} {test_resumes:>15,} {total_resumes:>15,}")
    
    ing_jobs = ingestion_df["Job Description"].nunique()
    test_jobs = testing_df["Job Description"].nunique()
    total_jobs = original_df["Job Description"].nunique()
    print(f"{'Unique Job Descriptions':<35} {ing_jobs:>15,} {test_jobs:>15,} {total_jobs:>15,}")
    
    ing_questions = ingestion_df["Question"].nunique()
    test_questions = testing_df["Question"].nunique()
    total_questions = original_df["Question"].nunique()
    print(f"{'Unique Questions':<35} {ing_questions:>15,} {test_questions:>15,} {total_questions:>15,}")
    
    ing_titles = ingestion_df["Job Title"].nunique()
    test_titles = testing_df["Job Title"].nunique()
    total_titles = original_df["Job Title"].nunique()
    print(f"{'Unique Job Titles':<35} {ing_titles:>15,} {test_titles:>15,} {total_titles:>15,}")
    
    # Token statistics
    if "Tokens" in ingestion_df.columns:
        ing_tokens = pd.to_numeric(ingestion_df["Tokens"], errors='coerce').sum()
        test_tokens = pd.to_numeric(testing_df["Tokens"], errors='coerce').sum()
        total_tokens = pd.to_numeric(original_df["Tokens"], errors='coerce').sum()
        print(f"\n{'Total Tokens':<35} {ing_tokens:>15,.0f} {test_tokens:>15,.0f} {total_tokens:>15,.0f}")


def save_datasets(ingestion_df, testing_df):
    """Save the split datasets to CSV files"""
    print("\n" + "="*80)
    print("💾 SAVING DATASETS")
    print("="*80 + "\n")
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Ingestion dataset
    ingestion_filename = f"qa_dataset_ingestion_{timestamp}.csv"
    ingestion_path = os.path.join(SCRIPT_DIR, ingestion_filename)
    
    print(f"💾 Saving ingestion dataset...")
    print(f"   File: {ingestion_filename}")
    ingestion_df.to_csv(ingestion_path, index=False, encoding='utf-8')
    ingestion_size = os.path.getsize(ingestion_path) / (1024 * 1024)
    print(f"   ✅ Saved: {len(ingestion_df):,} rows, {ingestion_size:.2f} MB")
    
    # Testing dataset
    testing_filename = f"qa_dataset_testing_{timestamp}.csv"
    testing_path = os.path.join(SCRIPT_DIR, testing_filename)
    
    print(f"\n💾 Saving testing dataset...")
    print(f"   File: {testing_filename}")
    testing_df.to_csv(testing_path, index=False, encoding='utf-8')
    testing_size = os.path.getsize(testing_path) / (1024 * 1024)
    print(f"   ✅ Saved: {len(testing_df):,} rows, {testing_size:.2f} MB")
    
    return ingestion_filename, testing_filename


def main():
    """Main execution"""
    print("\n" + "="*80)
    print("✂️  DATASET SPLITTING FOR INGESTION & TESTING")
    print("="*80)
    
    # Check if input file exists
    if not os.path.exists(INPUT_PATH):
        print(f"\n❌ Input file not found: {COMPLETED_CSV}")
        print(f"   Please ensure the completed dataset exists in the Dataset folder.")
        return
    
    # Load dataset
    df = load_dataset()
    if df is None:
        return
    
    # Analyze dataset structure
    analyze_dataset_structure(df)
    
    # Confirm before proceeding
    print("\n" + "="*80)
    print(f"📋 SPLIT CONFIGURATION")
    print("="*80)
    print(f"\nJob descriptions per resume: {JOB_DESCRIPTIONS_PER_RESUME}")
    print(f"Random seed: {RANDOM_SEED}")
    print(f"\nThis will create two new CSV files:")
    print(f"   1. qa_dataset_ingestion_[timestamp].csv  (for backend Q&A pipeline)")
    print(f"   2. qa_dataset_testing_[timestamp].csv    (for NodeRAG evaluation)")
    
    # Split the dataset
    ingestion_df, testing_df = split_dataset(
        df, 
        job_descriptions_per_resume=JOB_DESCRIPTIONS_PER_RESUME,
        random_seed=RANDOM_SEED
    )
    
    # Analyze results
    analyze_split_results(ingestion_df, testing_df, df)
    
    # Save datasets
    ing_file, test_file = save_datasets(ingestion_df, testing_df)
    
    # Final summary
    print("\n" + "="*80)
    print("✅ SPLITTING COMPLETE!")
    print("="*80)
    print(f"""
📁 Output Files Created:

1. {ing_file}
   Purpose: Ingest into backend for Q&A pipeline
   Rows: {len(ingestion_df):,}
   Strategy: {JOB_DESCRIPTIONS_PER_RESUME} random job descriptions per resume (all questions included)

2. {test_file}
   Purpose: Test NodeRAG system performance
   Rows: {len(testing_df):,}
   Strategy: All remaining rows not in ingestion set

🎯 Next Steps:
   • Use the ingestion CSV to populate your backend Q&A database
   • Use the testing CSV to evaluate NodeRAG vs naive LLM performance
   • Both sets ensure no overlap for fair evaluation

""")
    print("="*80 + "\n")


if __name__ == "__main__":
    main()

