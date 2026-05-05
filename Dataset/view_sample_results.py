"""Quick script to view sample generated answers"""
import pandas as pd
import sys
import os

if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Get the directory where this script is located
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATASET_PATH = os.path.join(SCRIPT_DIR, "qa_dataset_20260204_011255.csv")

# Check if row number was provided
row_number = None
if len(sys.argv) > 1:
    try:
        row_number = int(sys.argv[1])
        if row_number < 1:
            print("❌ Error: Row number must be 1 or greater")
            sys.exit(1)
    except ValueError:
        print(f"❌ Error: Invalid row number '{sys.argv[1]}'. Please provide a valid integer.")
        print(f"Usage: python view_sample_results.py [row_number]")
        sys.exit(1)

# If specific row requested, read that row
if row_number:
    # Read the specific row (accounting for 0-based indexing)
    try:
        df = pd.read_csv(DATASET_PATH, skiprows=range(1, row_number), nrows=1, low_memory=False)
        if len(df) == 0:
            print(f"❌ Error: Row {row_number} does not exist in the dataset")
            sys.exit(1)
        
        # Check if this row has an answer
        if pd.isna(df.iloc[0]['LLM Answer']) or df.iloc[0]['LLM Answer'] == '':
            print(f"\n⚠️  Row {row_number} has not been processed yet (LLM Answer is empty)")
            print(f"\nRow details:")
            print(f"   Job Title: {df.iloc[0]['Job Title']}")
            print(f"   Question: {df.iloc[0]['Question'][:100]}...")
            print(f"   Resume File: {df.iloc[0]['Resume File Name']}")
            sys.exit(0)
        
        row = df.iloc[0]
        row_index = row_number
    except Exception as e:
        print(f"❌ Error reading row {row_number}: {e}")
        sys.exit(1)
else:
    # Read first few rows and find first completed one
    df = pd.read_csv(DATASET_PATH, nrows=10, low_memory=False)
    completed = df[df['LLM Answer'].notna() & (df['LLM Answer'] != '')]
    
    if len(completed) == 0:
        print("No completed rows found in the first 10 rows.")
        print("Try: python view_sample_results.py [row_number]")
        sys.exit(0)
    
    row = completed.iloc[0]
    row_index = completed.index[0] + 1  # +1 because CSV is 1-indexed (header is row 0)

# Display the row
print("\n" + "="*80)
print(f"📝 GENERATED ANSWER - Row {row_index}")
print("="*80)

print(f"\n🎯 Job Title: {row['Job Title']}")
print(f"\n📄 Resume File: {row['Resume File Name']}")
print(f"\n❓ Question:")
print(f"   {row['Question']}")
print(f"\n💬 LLM Answer:")
print(f"{row['LLM Answer']}")
print(f"\n📊 Metrics:")
print(f"   Tokens: {row['Tokens']}")
print(f"   Time: {row['Time']} seconds")
print("\n" + "="*80)
print(f"\n💡 Usage: python view_sample_results.py [row_number]")
print(f"   Example: python view_sample_results.py 5")

