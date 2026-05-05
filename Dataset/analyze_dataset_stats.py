"""
Dataset Statistics and Breakdown Script
Safely analyzes the processed rows in the QA dataset.
Creates a temporary copy first to avoid conflicts with the running processing script.
"""

import pandas as pd
import os
import sys
import shutil
from datetime import datetime
from collections import Counter

# Fix Windows console encoding for emojis
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Get the directory where this script is located
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATASET_PATH = os.path.join(SCRIPT_DIR, "qa_dataset_20260204_011255.csv")
TEMP_COPY_PATH = os.path.join(SCRIPT_DIR, "temp_dataset_analysis.csv")


def create_temp_copy():
    """Create a temporary copy of the dataset for safe analysis"""
    print("📋 Creating temporary copy of dataset for analysis...")
    print("   (This avoids conflicts with the running processing script)")
    
    try:
        # Try to copy the file
        shutil.copy2(DATASET_PATH, TEMP_COPY_PATH)
        print("✅ Temporary copy created successfully\n")
        return True
    except PermissionError:
        print("⚠️  Warning: File is currently locked (being written to)")
        print("   Please wait a few seconds for the save to complete and try again.")
        return False
    except Exception as e:
        print(f"❌ Error creating copy: {e}")
        return False


def cleanup_temp_copy():
    """Remove temporary copy"""
    try:
        if os.path.exists(TEMP_COPY_PATH):
            os.remove(TEMP_COPY_PATH)
            print("\n🧹 Cleaned up temporary copy")
    except Exception:
        pass


def analyze_dataset():
    """Analyze the dataset and show comprehensive statistics"""
    
    print("\n" + "="*80)
    print("📊 DATASET PROCESSING STATISTICS & BREAKDOWN")
    print("="*80 + "\n")
    
    # Load dataset
    print("⏳ Loading dataset (this may take a moment)...")
    try:
        df = pd.read_csv(TEMP_COPY_PATH, encoding='utf-8', low_memory=False)
        print(f"✅ Loaded {len(df):,} total rows\n")
    except Exception as e:
        print(f"❌ Error loading dataset: {e}")
        return
    
    # Identify processed vs unprocessed rows
    processed_mask = df["LLM Answer"].notna() & (df["LLM Answer"] != "")
    processed_df = df[processed_mask]
    unprocessed_df = df[~processed_mask]
    
    num_processed = len(processed_df)
    num_unprocessed = len(unprocessed_df)
    total_rows = len(df)
    
    # Overall Progress
    print("="*80)
    print("📈 OVERALL PROGRESS")
    print("="*80)
    progress_pct = (num_processed / total_rows * 100) if total_rows > 0 else 0
    
    # Progress bar
    bar_length = 50
    filled = int(bar_length * num_processed / total_rows) if total_rows > 0 else 0
    bar = '█' * filled + '░' * (bar_length - filled)
    
    print(f"\n[{bar}] {progress_pct:.2f}%\n")
    print(f"✅ Processed:    {num_processed:>10,} rows")
    print(f"⏳ Unprocessed:  {num_unprocessed:>10,} rows")
    print(f"📊 Total:        {total_rows:>10,} rows")
    
    if num_processed == 0:
        print("\n⚠️  No processed rows found. Cannot generate statistics.")
        return
    
    # File Information
    file_size = os.path.getsize(DATASET_PATH)
    file_size_mb = file_size / (1024 * 1024)
    modified_time = datetime.fromtimestamp(os.path.getmtime(DATASET_PATH))
    
    print(f"\n📁 File Info:")
    print(f"   Size: {file_size_mb:.2f} MB")
    print(f"   Last modified: {modified_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # ==================== UNIQUE COUNTS ====================
    print("\n" + "="*80)
    print("🎯 UNIQUE ENTITIES PROCESSED")
    print("="*80)
    
    unique_resumes = processed_df["Resume File Name"].nunique()
    unique_job_titles = processed_df["Job Title"].nunique()
    unique_questions = processed_df["Question"].nunique()
    unique_job_descriptions = processed_df["Job Description"].nunique()
    
    print(f"\n📄 Unique Resumes:         {unique_resumes:>6,}")
    print(f"💼 Unique Job Titles:      {unique_job_titles:>6,}")
    print(f"❓ Unique Questions:       {unique_questions:>6,}")
    print(f"📝 Unique Job Descriptions:{unique_job_descriptions:>6,}")
    
    # ==================== JOB TITLE DISTRIBUTION ====================
    print("\n" + "="*80)
    print("💼 JOB TITLE DISTRIBUTION")
    print("="*80)
    
    job_title_counts = processed_df["Job Title"].value_counts()
    print(f"\nTotal Processed Rows by Job Title:\n")
    print(f"{'Job Title':<30} {'Processed Rows':>15} {'% of Total':>12}")
    print("-" * 80)
    
    for job_title, count in job_title_counts.items():
        pct = (count / num_processed * 100)
        print(f"{job_title:<30} {count:>15,} {pct:>11.2f}%")
    
    # ==================== QUESTION DISTRIBUTION ====================
    print("\n" + "="*80)
    print("❓ QUESTION DISTRIBUTION")
    print("="*80)
    
    question_counts = processed_df["Question"].value_counts()
    print(f"\nTotal Processed Rows by Question:\n")
    print(f"{'Question':<70} {'Count':>8}")
    print("-" * 80)
    
    for question, count in question_counts.head(15).items():  # Show top 15
        question_short = question[:67] + "..." if len(question) > 70 else question
        print(f"{question_short:<70} {count:>8,}")
    
    if len(question_counts) > 15:
        print(f"{'... and ' + str(len(question_counts) - 15) + ' more questions':<70}")
    
    # ==================== RESUME DISTRIBUTION ====================
    print("\n" + "="*80)
    print("📄 RESUME DISTRIBUTION")
    print("="*80)
    
    resume_counts = processed_df["Resume File Name"].value_counts()
    
    # Statistics
    avg_per_resume = resume_counts.mean()
    max_per_resume = resume_counts.max()
    min_per_resume = resume_counts.min()
    
    print(f"\nResume Usage Statistics:")
    print(f"   Average rows per resume: {avg_per_resume:.1f}")
    print(f"   Maximum rows per resume: {max_per_resume:,}")
    print(f"   Minimum rows per resume: {min_per_resume:,}")
    
    print(f"\nTop 10 Most Used Resumes:\n")
    print(f"{'Resume File':<40} {'Times Used':>12}")
    print("-" * 80)
    
    for resume, count in resume_counts.head(10).items():
        print(f"{resume:<40} {count:>12,}")
    
    # ==================== TOKEN STATISTICS ====================
    print("\n" + "="*80)
    print("🎯 TOKEN USAGE STATISTICS")
    print("="*80)
    
    # Filter out rows with valid token counts
    tokens_data = processed_df["Tokens"].dropna()
    tokens_data = tokens_data[tokens_data != ""]
    
    if len(tokens_data) > 0:
        tokens_numeric = pd.to_numeric(tokens_data, errors='coerce').dropna()
        
        if len(tokens_numeric) > 0:
            total_tokens = tokens_numeric.sum()
            avg_tokens = tokens_numeric.mean()
            max_tokens = tokens_numeric.max()
            min_tokens = tokens_numeric.min()
            median_tokens = tokens_numeric.median()
            
            print(f"\n📊 Token Metrics:")
            print(f"   Total tokens used:     {total_tokens:>15,.0f}")
            print(f"   Average per request:   {avg_tokens:>15,.1f}")
            print(f"   Median per request:    {median_tokens:>15,.0f}")
            print(f"   Maximum in a request:  {max_tokens:>15,.0f}")
            print(f"   Minimum in a request:  {min_tokens:>15,.0f}")
            
            # Estimate costs (example rates - update based on actual pricing)
            # Google AI Studio free tier: 15 RPM, 1M TPM, 1500 RPD for free
            print(f"\n💰 Usage Notes:")
            print(f"   Total API calls made: {num_processed:,}")
            print(f"   All usage is on Google AI Studio free tier")
    
    # ==================== TIME STATISTICS ====================
    print("\n" + "="*80)
    print("⏱️  PROCESSING TIME STATISTICS")
    print("="*80)
    
    # Filter out rows with valid time data
    time_data = processed_df["Time"].dropna()
    time_data = time_data[time_data != ""]
    
    if len(time_data) > 0:
        time_numeric = pd.to_numeric(time_data, errors='coerce').dropna()
        
        if len(time_numeric) > 0:
            total_time_seconds = time_numeric.sum()
            avg_time = time_numeric.mean()
            max_time = time_numeric.max()
            min_time = time_numeric.min()
            median_time = time_numeric.median()
            
            total_time_hours = total_time_seconds / 3600
            
            print(f"\n⏱️  Time Metrics:")
            print(f"   Total processing time: {total_time_hours:>15,.2f} hours")
            print(f"   Average per request:   {avg_time:>15,.2f} seconds")
            print(f"   Median per request:    {median_time:>15,.2f} seconds")
            print(f"   Fastest request:       {min_time:>15,.2f} seconds")
            print(f"   Slowest request:       {max_time:>15,.2f} seconds")
            
            # Estimate remaining time
            remaining_rows = num_unprocessed
            if remaining_rows > 0:
                estimated_remaining_hours = (remaining_rows * avg_time) / 3600
                estimated_remaining_days = estimated_remaining_hours / 24
                
                print(f"\n📅 Estimated Completion:")
                print(f"   Remaining rows:        {remaining_rows:>15,}")
                print(f"   Estimated time left:   {estimated_remaining_hours:>15,.1f} hours")
                print(f"                          {estimated_remaining_days:>15,.1f} days")
    
    # ==================== DATA QUALITY ====================
    print("\n" + "="*80)
    print("✅ DATA QUALITY CHECKS")
    print("="*80)
    
    # Check for empty or very short answers
    if num_processed > 0:
        answer_lengths = processed_df["LLM Answer"].astype(str).str.len()
        
        short_answers = (answer_lengths < 100).sum()
        medium_answers = ((answer_lengths >= 100) & (answer_lengths < 500)).sum()
        long_answers = (answer_lengths >= 500).sum()
        
        avg_length = answer_lengths.mean()
        
        print(f"\n📝 Answer Length Distribution:")
        print(f"   Short (<100 chars):    {short_answers:>10,} ({short_answers/num_processed*100:>5.1f}%)")
        print(f"   Medium (100-500):      {medium_answers:>10,} ({medium_answers/num_processed*100:>5.1f}%)")
        print(f"   Long (>500 chars):     {long_answers:>10,} ({long_answers/num_processed*100:>5.1f}%)")
        print(f"   Average length:        {avg_length:>10,.0f} characters")
    
    # ==================== SUMMARY ====================
    print("\n" + "="*80)
    print("📋 SUMMARY")
    print("="*80)
    print(f"""
Current Status:
  • {num_processed:,} / {total_rows:,} rows processed ({progress_pct:.2f}%)
  • {unique_resumes} unique resumes analyzed
  • {unique_job_titles} job titles covered
  • {unique_questions} unique questions answered
  • Processing continues in background...
""")
    
    print("="*80 + "\n")


def main():
    """Main execution"""
    print("\n" + "="*80)
    print("📊 Dataset Statistics Analyzer")
    print("="*80 + "\n")
    
    # Create temporary copy for safe analysis
    if not create_temp_copy():
        print("\n💡 Tip: Wait for the processing script to save (watch for '💾 Saved progress'),")
        print("   then try again immediately after.")
        return
    
    try:
        # Analyze the dataset
        analyze_dataset()
    finally:
        # Always cleanup temp copy
        cleanup_temp_copy()


if __name__ == "__main__":
    main()

