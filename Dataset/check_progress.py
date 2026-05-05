"""
Quick progress checker for the LLM dataset processing
Reads the CSV and shows how many rows have been completed
"""

import pandas as pd
import os
import sys
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


def check_progress():
    """Check and display processing progress"""
    
    print("\n" + "="*70)
    print("📊 LLM Dataset Processing Progress")
    print("="*70 + "\n")
    
    if not os.path.exists(DATASET_PATH):
        print(f"❌ Dataset not found: {DATASET_PATH}")
        return
    
    # Get file info
    file_size = os.path.getsize(DATASET_PATH)
    file_size_mb = file_size / (1024 * 1024)
    modified_time = datetime.fromtimestamp(os.path.getmtime(DATASET_PATH))
    
    print(f"📁 File: {DATASET_PATH}")
    print(f"💾 Size: {file_size_mb:.2f} MB")
    print(f"🕐 Last modified: {modified_time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    print("⏳ Loading dataset (this may take a moment for large files)...")
    
    try:
        # Read only necessary columns to speed up loading
        df = pd.read_csv(
            DATASET_PATH,
            usecols=["LLM Answer", "Tokens", "Time"],
            encoding='utf-8',
            low_memory=False  # Suppress dtype warning for large files
        )
        
        total_rows = len(df)
        
        # Count completed rows (rows with non-empty LLM Answer)
        completed_mask = df["LLM Answer"].notna() & (df["LLM Answer"] != "")
        completed_rows = completed_mask.sum()
        pending_rows = total_rows - completed_rows
        
        # Calculate percentage
        completion_percentage = (completed_rows / total_rows * 100) if total_rows > 0 else 0
        
        # Print progress bar
        bar_length = 50
        filled_length = int(bar_length * completed_rows / total_rows) if total_rows > 0 else 0
        bar = '█' * filled_length + '░' * (bar_length - filled_length)
        
        print("\n" + "="*70)
        print("📈 Processing Status")
        print("="*70)
        print(f"\n[{bar}] {completion_percentage:.1f}%\n")
        print(f"✅ Completed: {completed_rows:,} rows")
        print(f"⏳ Pending: {pending_rows:,} rows")
        print(f"📊 Total: {total_rows:,} rows")
        
        # Calculate statistics for completed rows
        if completed_rows > 0:
            completed_df = df[completed_mask]
            
            # Token statistics
            tokens_with_data = completed_df["Tokens"].notna() & (completed_df["Tokens"] != "")
            if tokens_with_data.any():
                avg_tokens = completed_df.loc[tokens_with_data, "Tokens"].astype(float).mean()
                total_tokens = completed_df.loc[tokens_with_data, "Tokens"].astype(float).sum()
                print(f"\n🎯 Token Statistics:")
                print(f"   Average tokens per request: {avg_tokens:.0f}")
                print(f"   Total tokens used: {total_tokens:,.0f}")
            
            # Time statistics
            times_with_data = completed_df["Time"].notna() & (completed_df["Time"] != "")
            if times_with_data.any():
                avg_time = completed_df.loc[times_with_data, "Time"].astype(float).mean()
                total_time = completed_df.loc[times_with_data, "Time"].astype(float).sum()
                print(f"\n⏱️  Time Statistics:")
                print(f"   Average time per request: {avg_time:.2f}s")
                print(f"   Total processing time: {total_time/3600:.2f} hours")
                
                # Estimate remaining time
                if pending_rows > 0:
                    estimated_remaining = (pending_rows * avg_time) / 3600
                    print(f"   Estimated remaining time: {estimated_remaining:.2f} hours")
        
        # Check for recent activity
        if completed_rows > 0:
            print(f"\n💡 Tip: Check 'Last modified' time above to see if processing is active")
        
        if pending_rows == 0:
            print("\n🎉 All rows completed! Dataset processing is done!")
        elif completed_rows == 0:
            print("\n💡 No rows processed yet. Run: python Dataset/run_llm_on_dataset.py")
        else:
            print(f"\n🔄 Processing in progress... {pending_rows:,} rows remaining")
        
    except Exception as e:
        print(f"\n❌ Error reading dataset: {e}")
        import traceback
        traceback.print_exc()
    
    print()


if __name__ == "__main__":
    check_progress()

