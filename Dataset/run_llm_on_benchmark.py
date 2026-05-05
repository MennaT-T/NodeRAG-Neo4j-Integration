"""
LLM Benchmark Dataset Processing Script
Processes benchmark_dataset CSV by calling Google AI Studio API (Gemini) to generate answers
for rows with empty LLM Answer (the 4 additional benchmark questions per job-resume pair).

Based on run_llm_on_dataset.py with adaptations for benchmark dataset structure.
"""

import pandas as pd
import os
import sys
import time
import asyncio
import aiohttp
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from dotenv import load_dotenv
import json
from pathlib import Path

# Fix Windows console encoding for emojis
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Configuration
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATASET_PATH = os.path.join(SCRIPT_DIR, "benchmark_dataset_20260204_232109.csv")
OUTPUT_PATH = os.path.join(SCRIPT_DIR, "benchmark_dataset_20260204_232109.csv")  # Overwrite the same file
ENV_PATH = os.path.join(SCRIPT_DIR, ".env")
MODEL_NAME = "gemma-3-12b-it"
API_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

# Rate Limits for Gemma 3 12b
RPM = 30  # Requests per minute
TPM = 15000  # Tokens per minute
RPD = 14400  # Requests per day

# Processing Configuration
MAX_PARALLEL_REQUESTS = 10  # Process 10 rows at a time
SAVE_INTERVAL = 50  # Save every 50 requests
MAX_RETRIES_PER_KEY = 3  # Retries before switching key
RETRY_DELAY = 2  # Initial retry delay in seconds

# Rate limiting tracking
class RateLimiter:
    def __init__(self):
        self.request_times = []  # Timestamps of requests
        self.requests_today = 0
        self.last_reset = datetime.now().date()
        
    def can_request(self) -> bool:
        """Check if we can make a request based on RPM and RPD limits"""
        now = datetime.now()
        
        # Reset daily counter
        if now.date() > self.last_reset:
            self.requests_today = 0
            self.last_reset = now.date()
        
        # Check daily limit
        if self.requests_today >= RPD:
            return False
        
        # Remove requests older than 1 minute
        one_minute_ago = now.timestamp() - 60
        self.request_times = [t for t in self.request_times if t > one_minute_ago]
        
        # Check RPM limit
        if len(self.request_times) >= RPM:
            return False
        
        return True
    
    def add_request(self):
        """Record a new request"""
        self.request_times.append(datetime.now().timestamp())
        self.requests_today += 1
    
    def get_wait_time(self) -> float:
        """Get how long to wait before next request (in seconds)"""
        if not self.request_times:
            return 0
        
        now = datetime.now().timestamp()
        one_minute_ago = now - 60
        
        # Find oldest request in the last minute
        recent_requests = [t for t in self.request_times if t > one_minute_ago]
        if len(recent_requests) >= RPM:
            oldest = min(recent_requests)
            wait_time = 60 - (now - oldest) + 1  # Add 1 second buffer
            return max(0, wait_time)
        
        return 0


class APIKeyManager:
    def __init__(self, keys: List[str]):
        self.keys = keys
        self.current_key_index = 0
        self.rate_limiters = {i: RateLimiter() for i in range(len(keys))}
        self.exhausted_keys = set()
        
    def get_current_key(self) -> Optional[str]:
        """Get the current API key"""
        if len(self.exhausted_keys) >= len(self.keys):
            return None
        return self.keys[self.current_key_index]
    
    def get_rate_limiter(self) -> Optional[RateLimiter]:
        """Get the rate limiter for current key"""
        if len(self.exhausted_keys) >= len(self.keys):
            return None
        return self.rate_limiters[self.current_key_index]
    
    def mark_key_exhausted(self):
        """Mark current key as exhausted and switch to next"""
        print(f"⚠️  API Key {self.current_key_index + 1} exhausted. Switching to next key...")
        self.exhausted_keys.add(self.current_key_index)
        self._switch_to_next_available_key()
    
    def switch_key(self):
        """Switch to the next available key"""
        print(f"🔄 Switching from API Key {self.current_key_index + 1} to next available key...")
        self._switch_to_next_available_key()
    
    def _switch_to_next_available_key(self):
        """Find and switch to next available key"""
        for _ in range(len(self.keys)):
            self.current_key_index = (self.current_key_index + 1) % len(self.keys)
            if self.current_key_index not in self.exhausted_keys:
                print(f"✅ Switched to API Key {self.current_key_index + 1}")
                return
        print("❌ All API keys exhausted!")
    
    def all_keys_exhausted(self) -> bool:
        """Check if all keys are exhausted"""
        return len(self.exhausted_keys) >= len(self.keys)


async def call_gemini_api(
    session: aiohttp.ClientSession,
    api_key: str,
    job_description: str,
    question: str,
    latex_code: str,
    row_index: int
) -> Tuple[Optional[str], Optional[int], float, Optional[str]]:
    """
    Call Gemini API to generate an answer.
    Returns: (answer, tokens, time_taken, error)
    """
    start_time = time.time()
    
    # Construct the prompt
    prompt = f"""You are answering a job application question. Based on the resume information provided, answer the question in first-person as if you are the candidate.

Job Description:
{job_description}

Question:
{question}

Your Resume (LaTeX format):
{latex_code}

Instructions:
- Answer the question in first-person (use "I", "my", etc.)
- Be specific and use details from your resume
- Keep your answer professional and relevant to the job description
- Aim for 2-4 paragraphs

Your Answer:"""

    url = API_ENDPOINT.replace("{model}", MODEL_NAME)
    
    headers = {
        "Content-Type": "application/json",
    }
    
    payload = {
        "contents": [{
            "parts": [{
                "text": prompt
            }]
        }],
        "generationConfig": {
            "temperature": 0.7,
            "topK": 40,
            "topP": 0.95,
            "maxOutputTokens": 1024,
        }
    }
    
    try:
        async with session.post(
            f"{url}?key={api_key}",
            headers=headers,
            json=payload,
            timeout=aiohttp.ClientTimeout(total=120)
        ) as response:
            time_taken = time.time() - start_time
            
            if response.status == 200:
                result = await response.json()
                
                # Extract answer
                answer = result.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                
                # Extract token count
                usage_metadata = result.get("usageMetadata", {})
                total_tokens = usage_metadata.get("totalTokenCount", 0)
                
                return answer, total_tokens, time_taken, None
            
            elif response.status == 429:
                # Rate limit hit
                return None, None, time_taken, "rate_limit"
            
            elif response.status == 403:
                # API key exhausted (quota)
                return None, None, time_taken, "quota_exceeded"
            
            else:
                error_text = await response.text()
                print(f"❌ Row {row_index}: API error {response.status}: {error_text[:200]}")
                return None, None, time_taken, f"api_error_{response.status}"
                
    except asyncio.TimeoutError:
        time_taken = time.time() - start_time
        print(f"⏱️  Row {row_index}: Request timeout")
        return None, None, time_taken, "timeout"
    
    except Exception as e:
        time_taken = time.time() - start_time
        print(f"❌ Row {row_index}: Exception: {str(e)}")
        return None, None, time_taken, f"exception_{type(e).__name__}"


async def process_row(
    session: aiohttp.ClientSession,
    key_manager: APIKeyManager,
    row_data: Dict,
    row_index: int,
    semaphore: asyncio.Semaphore
) -> Tuple[int, Optional[str], Optional[int], float, bool]:
    """
    Process a single row with rate limiting and key rotation.
    Returns: (row_index, answer, tokens, time, success)
    """
    async with semaphore:
        retries = 0
        
        while retries < MAX_RETRIES_PER_KEY * len(key_manager.keys):
            # Check if all keys exhausted
            if key_manager.all_keys_exhausted():
                print(f"🛑 All API keys exhausted. Stopping processing.")
                return row_index, None, None, 0, False
            
            api_key = key_manager.get_current_key()
            rate_limiter = key_manager.get_rate_limiter()
            
            # Wait if rate limit reached
            while not rate_limiter.can_request():
                wait_time = rate_limiter.get_wait_time()
                if wait_time > 0:
                    print(f"⏳ Rate limit reached for Key {key_manager.current_key_index + 1}. Waiting {wait_time:.1f}s...")
                    await asyncio.sleep(wait_time)
            
            # Record request
            rate_limiter.add_request()
            
            # Make API call
            answer, tokens, time_taken, error = await call_gemini_api(
                session,
                api_key,
                row_data["Job Description"],
                row_data["Question"],
                row_data["Latex_Code"],
                row_index
            )
            
            if error is None:
                # Success
                return row_index, answer, tokens, time_taken, True
            
            elif error == "rate_limit":
                # Rate limit hit, switch key
                key_manager.switch_key()
                retries += 1
                await asyncio.sleep(RETRY_DELAY)
            
            elif error == "quota_exceeded":
                # Key exhausted, mark and switch
                key_manager.mark_key_exhausted()
                retries += 1
            
            else:
                # Other error, retry with exponential backoff
                retries += 1
                wait = RETRY_DELAY * (2 ** min(retries, 5))
                print(f"🔄 Row {row_index}: Retrying in {wait}s... (attempt {retries})")
                await asyncio.sleep(wait)
        
        print(f"❌ Row {row_index}: Failed after {retries} retries")
        return row_index, None, None, 0, False


async def process_dataset(
    df: pd.DataFrame,
    key_manager: APIKeyManager,
    max_rows: Optional[int] = None
):
    """Process the dataset with parallel requests"""
    
    # Find rows that need processing (empty LLM Answer)
    # Handle both NaN and empty string cases
    mask = df["LLM Answer"].isna() | (df["LLM Answer"] == "") | (df["LLM Answer"].astype(str).str.strip() == "")
    rows_to_process = df[mask].head(max_rows) if max_rows else df[mask]
    
    total_rows = len(rows_to_process)
    
    print(f"\n📊 Dataset Statistics:")
    print(f"   Total rows in dataset: {len(df):,}")
    print(f"   Rows with LLM answers: {(~mask).sum():,}")
    print(f"   Rows to process (empty): {total_rows:,}")
    
    # Show breakdown by source
    if 'Source' in df.columns:
        print(f"\n📋 Breakdown by source:")
        for source in df['Source'].unique():
            source_mask = df['Source'] == source
            source_empty = (mask & source_mask).sum()
            source_filled = (~mask & source_mask).sum()
            print(f"   {source}: {source_filled} filled, {source_empty} empty")
    
    print(f"\n🔑 Available API keys: {len(key_manager.keys)}")
    print(f"⚡ Parallel requests: {MAX_PARALLEL_REQUESTS}")
    print(f"💾 Save interval: every {SAVE_INTERVAL} requests\n")
    
    if total_rows == 0:
        print("✅ No rows to process!")
        return
    
    # Create semaphore for parallel processing
    semaphore = asyncio.Semaphore(MAX_PARALLEL_REQUESTS)
    
    # Process in batches
    processed_count = 0
    successful_count = 0
    failed_count = 0
    
    async with aiohttp.ClientSession() as session:
        for batch_start in range(0, total_rows, SAVE_INTERVAL):
            batch_end = min(batch_start + SAVE_INTERVAL, total_rows)
            batch_rows = rows_to_process.iloc[batch_start:batch_end]
            
            print(f"\n{'='*70}")
            print(f"📦 Processing batch: rows {batch_start + 1} to {batch_end} of {total_rows}")
            print(f"{'='*70}")
            
            # Create tasks for this batch
            tasks = []
            for idx, (df_idx, row) in enumerate(batch_rows.iterrows()):
                task = process_row(
                    session,
                    key_manager,
                    row.to_dict(),
                    df_idx,
                    semaphore
                )
                tasks.append(task)
            
            # Process batch
            batch_start_time = time.time()
            results = await asyncio.gather(*tasks)
            batch_time = time.time() - batch_start_time
            
            # Update dataframe with results
            batch_successful = 0
            for row_index, answer, tokens, time_taken, success in results:
                processed_count += 1
                
                if success and answer:
                    df.at[row_index, "LLM Answer"] = answer
                    df.at[row_index, "Tokens"] = tokens if tokens else 0
                    df.at[row_index, "Time"] = f"{time_taken:.2f}"
                    successful_count += 1
                    batch_successful += 1
                else:
                    failed_count += 1
                
                # Check if all keys exhausted
                if key_manager.all_keys_exhausted():
                    print(f"\n🛑 All API keys exhausted. Saving progress...")
                    save_dataframe(df)
                    return
            
            # Save progress
            save_dataframe(df)
            
            # Print batch summary
            print(f"\n📈 Batch Summary:")
            print(f"   ✅ Successful: {batch_successful}/{len(batch_rows)}")
            print(f"   ⏱️  Batch time: {batch_time:.2f}s")
            print(f"   📊 Overall progress: {processed_count}/{total_rows} ({processed_count/total_rows*100:.1f}%)")
            print(f"   ✅ Total successful: {successful_count}")
            print(f"   ❌ Total failed: {failed_count}")
            
            # Small delay between batches
            if batch_end < total_rows:
                await asyncio.sleep(1)
    
    print(f"\n{'='*70}")
    print(f"🎉 Processing Complete!")
    print(f"{'='*70}")
    print(f"✅ Successfully processed: {successful_count:,}/{total_rows:,}")
    print(f"❌ Failed: {failed_count:,}/{total_rows:,}")


def save_dataframe(df: pd.DataFrame):
    """Save dataframe to CSV"""
    try:
        df.to_csv(OUTPUT_PATH, index=False, encoding='utf-8')
        print(f"💾 Saved progress to {os.path.basename(OUTPUT_PATH)}")
    except Exception as e:
        # Try backup save
        backup_path = os.path.join(SCRIPT_DIR, f"benchmark_dataset_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
        df.to_csv(backup_path, index=False, encoding='utf-8')
        print(f"⚠️  Saved to backup: {backup_path}")


def load_api_keys() -> List[str]:
    """Load API keys from .env file"""
    load_dotenv(ENV_PATH)
    
    keys = []
    for i in range(1, 6):  # GEMINI_API_KEY_1 to GEMINI_API_KEY_5
        key = os.getenv(f"GEMINI_API_KEY_{i}")
        if key:
            keys.append(key)
    
    if not keys:
        raise ValueError(f"No API keys found in {ENV_PATH}. Please add GEMINI_API_KEY_1 to GEMINI_API_KEY_5")
    
    print(f"🔑 Loaded {len(keys)} API key(s)")
    return keys


def main():
    """Main execution function"""
    print("\n" + "="*70)
    print("🤖 LLM Benchmark Dataset Processing Script")
    print("="*70)
    
    # Get max rows from command line argument
    max_rows = None
    if len(sys.argv) > 1:
        try:
            max_rows = int(sys.argv[1])
            print(f"🎯 Processing limit: {max_rows} rows")
        except ValueError:
            print(f"⚠️  Invalid row limit '{sys.argv[1]}'. Processing all rows.")
    else:
        print("🎯 Processing limit: All rows (use argument to limit, e.g., 'python run_llm_on_benchmark.py 5')")
    
    # Load API keys
    try:
        api_keys = load_api_keys()
        key_manager = APIKeyManager(api_keys)
    except Exception as e:
        print(f"❌ Error loading API keys: {e}")
        return
    
    # Load dataset
    print(f"📂 Loading dataset: {os.path.basename(DATASET_PATH)}")
    try:
        df = pd.read_csv(DATASET_PATH, encoding='utf-8', low_memory=False)
        print(f"✅ Loaded {len(df):,} rows")
    except Exception as e:
        print(f"❌ Error loading dataset: {e}")
        return
    
    # Ensure required columns exist
    required_columns = ["Job Title", "Job Description", "Question", "Latex_Code", "LLM Answer", "Tokens", "Time"]
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        print(f"❌ Missing required columns: {missing_columns}")
        return
    
    # Convert columns to appropriate dtypes to avoid FutureWarning
    df["LLM Answer"] = df["LLM Answer"].astype(object)
    df["Time"] = df["Time"].astype(object)
    df["Tokens"] = df["Tokens"].astype(float)
    
    # Process dataset
    try:
        asyncio.run(process_dataset(df, key_manager, max_rows))
    except KeyboardInterrupt:
        print("\n\n⚠️  Process interrupted by user. Saving progress...")
        save_dataframe(df)
    except Exception as e:
        print(f"\n❌ Error during processing: {e}")
        import traceback
        traceback.print_exc()
        save_dataframe(df)
    
    print("\n✅ Script completed!")


if __name__ == "__main__":
    main()

