# Quick Setup Instructions

## Step 1: Install Dependencies

```bash
pip install pandas aiohttp python-dotenv
```

## Step 2: Create .env File

Create a file named `.env` in the `Dataset/` folder with your Google AI Studio API keys:

```bash
cd Dataset
```

Create `.env` file with this content:

```
GEMINI_API_KEY_1=your_first_api_key_here
GEMINI_API_KEY_2=your_second_api_key_here
GEMINI_API_KEY_3=your_third_api_key_here
GEMINI_API_KEY_4=your_fourth_api_key_here
GEMINI_API_KEY_5=your_fifth_api_key_here
```

### Getting API Keys:
1. Go to https://aistudio.google.com/app/apikey
2. Click "Create API Key"
3. Copy the key and paste it in the `.env` file
4. Repeat for up to 5 keys (minimum 1 required)

## Step 3: Test Your API Keys

```bash
python Dataset/test_api_keys.py
```

This will verify all your keys work correctly.

## Step 4: Run a Test

Process just 5 rows to verify everything works:

```bash
python Dataset/run_llm_on_dataset.py 5
```

Check the CSV file to see if the "LLM Answer", "Tokens", and "Time" columns are populated.

## Step 5: Run Full Processing

Once testing looks good, run on all rows:

```bash
python Dataset/run_llm_on_dataset.py
```

Or specify a custom limit:

```bash
python Dataset/run_llm_on_dataset.py 1000
```

---

## ⚡ Quick Commands Reference

| Command | Description |
|---------|-------------|
| `python Dataset/test_api_keys.py` | Test all API keys |
| `python Dataset/run_llm_on_dataset.py 5` | Process 5 rows (testing) |
| `python Dataset/run_llm_on_dataset.py 100` | Process 100 rows |
| `python Dataset/run_llm_on_dataset.py` | Process all rows |

## 📊 Expected Performance

- **Processing speed**: ~2-3 seconds per row
- **Parallel requests**: 10 rows at once
- **Saves**: Every 50 rows
- **Rate limits**: 30 requests/min per key

With 5 keys, you can process:
- **~150 requests/minute** (with rotation)
- **~5,000-7,000 rows/hour**
- **Full dataset (~115K rows)**: 16-24 hours

## 🔄 Resuming After Interruption

The script automatically skips rows that already have answers. So if you stop the script (Ctrl+C) or it crashes, just run it again:

```bash
python Dataset/run_llm_on_dataset.py
```

It will continue from where it left off!

---

For detailed information, see `LLM_PROCESSING_README.md`

