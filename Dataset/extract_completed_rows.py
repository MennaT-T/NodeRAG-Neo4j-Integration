"""
Extract Completed Rows Script
Safely creates a new CSV containing only rows with LLM answers.
Creates a temporary copy first to avoid conflicts with the running processing script.
"""

import pandas as pd
import os
import sys
import shutil
from datetime import datetime

# Fix Windows console encoding for emojis
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Get the directory where this script is located
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATASET_PATH = os.path.join(SCRIPT_DIR, "qa_dataset_20260204_011255.csv")
TEMP_COPY_PATH = os.path.join(SCRIPT_DIR, "temp_dataset_extraction.csv")


def create_temp_copy():
    """Create a temporary copy of the dataset for safe extraction"""
    print("📋 Creating temporary copy of dataset...")
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


def extract_completed_rows():
    """Extract rows with LLM answers to a new CSV"""
    
    print("\n" + "="*80)
    print("📤 EXTRACTING COMPLETED ROWS")
    print("="*80 + "\n")
    
    # Load dataset
    print("⏳ Loading dataset from temporary copy...")
    try:
        df = pd.read_csv(TEMP_COPY_PATH, encoding='utf-8', low_memory=False)
        print(f"✅ Loaded {len(df):,} total rows\n")
    except Exception as e:
        print(f"❌ Error loading dataset: {e}")
        return
    
    # Filter for completed rows (rows with LLM Answer)
    print("🔍 Filtering for completed rows...")
    completed_mask = df["LLM Answer"].notna() & (df["LLM Answer"] != "")
    completed_df = df[completed_mask]
    
    num_completed = len(completed_df)
    num_total = len(df)
    
    if num_completed == 0:
        print("⚠️  No completed rows found. Nothing to extract.")
        return
    
    print(f"✅ Found {num_completed:,} completed rows ({num_completed/num_total*100:.2f}% of total)\n")
    
    # Statistics about what's being extracted
    print("="*80)
    print("📊 EXTRACTION SUMMARY")
    print("="*80)
    
    unique_resumes = completed_df["Resume File Name"].nunique()
    unique_job_titles = completed_df["Job Title"].nunique()
    unique_questions = completed_df["Question"].nunique()
    unique_descriptions = completed_df["Job Description"].nunique()
    
    print(f"\nCompleted Rows Breakdown:")
    print(f"   Total rows:            {num_completed:>10,}")
    print(f"   Unique resumes:        {unique_resumes:>10,}")
    print(f"   Unique job titles:     {unique_job_titles:>10,}")
    print(f"   Unique questions:      {unique_questions:>10,}")
    print(f"   Unique descriptions:   {unique_descriptions:>10,}")
    
    # Token statistics
    tokens_data = completed_df["Tokens"].dropna()
    tokens_data = tokens_data[tokens_data != ""]
    if len(tokens_data) > 0:
        tokens_numeric = pd.to_numeric(tokens_data, errors='coerce').dropna()
        if len(tokens_numeric) > 0:
            total_tokens = tokens_numeric.sum()
            avg_tokens = tokens_numeric.mean()
            print(f"\n   Total tokens used:     {total_tokens:>10,.0f}")
            print(f"   Average tokens/row:    {avg_tokens:>10,.1f}")
    
    # Time statistics
    time_data = completed_df["Time"].dropna()
    time_data = time_data[time_data != ""]
    if len(time_data) > 0:
        time_numeric = pd.to_numeric(time_data, errors='coerce').dropna()
        if len(time_numeric) > 0:
            total_time_hours = time_numeric.sum() / 3600
            avg_time = time_numeric.mean()
            print(f"\n   Total processing time: {total_time_hours:>10,.2f} hours")
            print(f"   Average time/row:      {avg_time:>10,.2f} seconds")
    
    # Generate output filename with timestamp
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_filename = f"qa_dataset_completed_{timestamp}.csv"
    output_path = os.path.join(SCRIPT_DIR, output_filename)
    
    # Save to new CSV
    print(f"\n{'='*80}")
    print("💾 SAVING TO NEW CSV")
    print("="*80 + "\n")
    
    print(f"📁 Output file: {output_filename}")
    print(f"⏳ Writing {num_completed:,} rows to CSV...")
    
    try:
        completed_df.to_csv(output_path, index=False, encoding='utf-8')
        
        # Get file size
        file_size = os.path.getsize(output_path)
        file_size_mb = file_size / (1024 * 1024)
        
        print(f"✅ Successfully created new CSV!")
        print(f"   File: {output_filename}")
        print(f"   Size: {file_size_mb:.2f} MB")
        print(f"   Rows: {num_completed:,}")
        print(f"   Location: {SCRIPT_DIR}")
        
        # Show column info
        print(f"\n📋 Columns included:")
        for col in completed_df.columns:
            print(f"   • {col}")
        
        print(f"\n{'='*80}")
        print("✅ EXTRACTION COMPLETE!")
        print("="*80)
        print(f"""
The new CSV contains only the completed rows with LLM answers.
You can now work with this smaller file for analysis, testing, or evaluation.

Original dataset: {num_total:,} rows
Extracted dataset: {num_completed:,} rows
Reduction: {(1 - num_completed/num_total)*100:.1f}% smaller
""")
        
    except Exception as e:
        print(f"❌ Error saving CSV: {e}")
        import traceback
        traceback.print_exc()


def main():
    """Main execution"""
    print("\n" + "="*80)
    print("📤 Extract Completed Rows to New CSV")
    print("="*80 + "\n")
    
    # Check if original dataset exists
    if not os.path.exists(DATASET_PATH):
        print(f"❌ Dataset not found: {DATASET_PATH}")
        return
    
    # Get file info
    file_size = os.path.getsize(DATASET_PATH)
    file_size_mb = file_size / (1024 * 1024)
    modified_time = datetime.fromtimestamp(os.path.getmtime(DATASET_PATH))
    
    print(f"📁 Source Dataset:")
    print(f"   File: qa_dataset_20260204_011255.csv")
    print(f"   Size: {file_size_mb:.2f} MB")
    print(f"   Last modified: {modified_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Create temporary copy for safe extraction
    if not create_temp_copy():
        print("\n💡 Tip: Wait for the processing script to save (watch for '💾 Saved progress'),")
        print("   then try again immediately after.")
        return
    
    try:
        # Extract completed rows
        extract_completed_rows()
    finally:
        # Always cleanup temp copy
        cleanup_temp_copy()
    
    print()


if __name__ == "__main__":
    main()

