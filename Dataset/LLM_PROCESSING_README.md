# LLM Dataset Processing Guide

This guide explains how to use the `run_llm_on_dataset.py` script to process your Q&A dataset with Google's Gemini API.

## 🎯 Purpose

The script processes the generated `qa_dataset_*.csv` file by:
- Calling Google AI Studio's Gemini API (gemma-3-12b-it model)
- Generating first-person answers to job application questions based on resume data
- Tracking token usage and response times
- Handling rate limits with automatic API key rotation
- Processing rows in parallel for efficiency
- Saving progress periodically

## 📋 Prerequisites

1. **Python Dependencies**: Install required packages
   ```bash
   pip install pandas aiohttp python-dotenv
   ```

2. **API Keys**: Get your Google AI Studio API keys
   - Go to https://aistudio.google.com/app/apikey
   - Create 1-5 API keys (more keys = better rate limit handling)
   - Each key has limits:
     - 30 requests per minute (RPM)
     - 15,000 tokens per minute (TPM)
     - 14,400 requests per day (RPD)

3. **Environment File**: Create `.env` file in the `Dataset/` folder
   ```bash
   cd Dataset
   cp .env.example .env
   # Edit .env and add your API keys
   ```

## 🚀 Usage

### Basic Usage (Process All Rows)
```bash
python Dataset/run_llm_on_dataset.py
```

### Test Mode (Process Limited Rows)
```bash
# Process only 5 rows for testing
python Dataset/run_llm_on_dataset.py 5

# Process 100 rows
python Dataset/run_llm_on_dataset.py 100
```

## ⚙️ Configuration

### Script Parameters (at the top of the script)

```python
# Processing Configuration
MAX_PARALLEL_REQUESTS = 10  # Process 10 rows simultaneously
SAVE_INTERVAL = 50          # Save progress every 50 requests
MAX_RETRIES_PER_KEY = 3     # Retries before switching API key
RETRY_DELAY = 2             # Initial retry delay in seconds

# Rate Limits (for gemma-3-12b-it)
RPM = 30    # Requests per minute
TPM = 15000 # Tokens per minute
RPD = 14400 # Requests per day
```

### Adjusting Parallel Requests

Based on Gemma 3's 30 RPM limit:
- **Conservative**: `MAX_PARALLEL_REQUESTS = 5` (safer, slower)
- **Default**: `MAX_PARALLEL_REQUESTS = 10` (balanced)
- **Aggressive**: `MAX_PARALLEL_REQUESTS = 15` (faster, more rate limit hits)

## 🔄 How It Works

1. **Load Dataset**: Reads the CSV and identifies rows with empty "LLM Answer" column
2. **Key Management**: Loads API keys and initializes rate limiters
3. **Parallel Processing**: Processes up to 10 rows simultaneously
4. **Rate Limiting**: Automatically waits when approaching limits
5. **Key Rotation**: Switches to next key when current key hits limits
6. **Error Handling**: Retries failed requests with exponential backoff
7. **Periodic Saves**: Saves progress every 50 requests
8. **Graceful Shutdown**: Saves on completion, interruption, or error

## 📊 Output

The script updates the existing CSV file with:
- **LLM Answer**: Generated first-person answer
- **Tokens**: Total token count (input + output)
- **Time**: Time taken for the request (in seconds)

## 🎯 Example API Call

For each row, the script sends:

```
Prompt:
You are answering a job application question. Based on the resume information 
provided, answer the question in first-person as if you are the candidate.

Job Description:
[Full job description from CSV]

Question:
[Question from CSV]

Your Resume (LaTeX format):
[Latex_Code from CSV]

Instructions:
- Answer the question in first-person (use "I", "my", etc.)
- Be specific and use details from your resume
- Keep your answer professional and relevant to the job description
- Aim for 2-4 paragraphs

Your Answer:
```

## 📈 Progress Tracking

The script displays real-time progress:
```
======================================================================
📦 Processing batch: rows 1 to 50 of 115290
======================================================================

📈 Batch Summary:
   ✅ Successful: 48/50
   ⏱️  Batch time: 125.45s
   📊 Overall progress: 50/115290 (0.0%)
   ✅ Total successful: 48
   ❌ Total failed: 2

💾 Saved progress to Dataset/qa_dataset_20260204_011255.csv
```

## ⚠️ Rate Limit Handling

When rate limits are hit:
1. **Soft Limit**: Script waits automatically
   ```
   ⏳ Rate limit reached for Key 1. Waiting 15.3s...
   ```

2. **Key Rotation**: Switches to next available key
   ```
   🔄 Switching from API Key 1 to next available key...
   ✅ Switched to API Key 2
   ```

3. **Key Exhausted**: Marks key as exhausted
   ```
   ⚠️  API Key 1 exhausted. Switching to next key...
   ```

4. **All Keys Exhausted**: Saves progress and stops
   ```
   🛑 All API keys exhausted. Saving progress...
   ```

## 🛠️ Troubleshooting

### Issue: "No API keys found"
**Solution**: Ensure `.env` file exists in `Dataset/` folder with at least one key

### Issue: Rate limits hit immediately
**Solution**: 
- Reduce `MAX_PARALLEL_REQUESTS` to 5
- Add more API keys
- Wait for quota to reset (daily at midnight PT)

### Issue: Script crashes
**Solution**: 
- Check your internet connection
- Ensure dataset file is not open in another program
- Check if you have enough disk space
- Run with fewer rows first: `python run_llm_on_dataset.py 5`

### Issue: Low-quality responses
**Solution**: Adjust generation config in the script:
```python
"generationConfig": {
    "temperature": 0.7,     # Lower = more deterministic (0.0-1.0)
    "topK": 40,             # Consider top K tokens
    "topP": 0.95,           # Nucleus sampling threshold
    "maxOutputTokens": 1024 # Max response length
}
```

## 📊 Estimated Processing Time

With the default configuration:
- **Per request**: ~2-3 seconds
- **Per batch (50 rows)**: ~2-3 minutes
- **1,000 rows**: ~40-60 minutes
- **Full dataset (115,290 rows)**: ~80-120 hours with 5 keys

### Optimization Tips:
1. Use all 5 API keys to maximize throughput
2. Run overnight or in the background
3. Process in chunks using the row limit parameter
4. Consider using Google Cloud's paid tier for higher limits

## 🔐 Security Notes

- **Never commit `.env` file** to version control
- Keep API keys secure and private
- Rotate keys periodically
- Monitor usage at https://aistudio.google.com/

## 💡 Tips

1. **Test First**: Always run with 5-10 rows first to verify setup
2. **Monitor Progress**: Check the CSV file periodically during processing
3. **Resume Processing**: If interrupted, the script automatically skips completed rows
4. **Backup**: The script creates automatic backups if the main save fails
5. **Parallel Testing**: Start with lower parallel requests, then increase if stable

## 📞 Support

If you encounter issues:
1. Check the console output for specific error messages
2. Verify your API keys are active at https://aistudio.google.com/
3. Ensure all required Python packages are installed
4. Check the CSV file is not corrupted or locked

---

**Happy Processing! 🚀**

