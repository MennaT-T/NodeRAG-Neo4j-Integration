"""Inspect what's in LLM_error.jsonl and test _is_llm_error on the actual LLM response."""
import json
import sys
import os
sys.path.insert(0, '.')
os.environ.pop('GOOGLE_API_KEY', None)

# Import the ACTUAL _is_llm_error function we edited
from NodeRAG.logging.error import _is_llm_error

CACHE_PATH = 'POC_Data/documents/users/user_36/cache/LLM_error.jsonl'

print("=== Cached error entries ===")
entries = []
with open(CACHE_PATH, 'r') as f:
    for i, line in enumerate(f, 1):
        line = line.strip()
        if not line:
            continue
        d = json.loads(line)
        entries.append(d)
        meta = d['meta_data']
        inp = d.get('input', {})
        query = inp.get('query', '')
        text_marker = query.rfind('Text:')
        text_snippet = query[text_marker:text_marker+150] if text_marker != -1 else query[:150]
        print(f"Entry {i}: text_id={meta['text_id']}, hash={meta['text_hash_id'][:12]}")
        print(f"  query len: {len(query)}, text snippet: {repr(text_snippet[:100])}")
        print()

print("\n=== Replaying LLM calls with NEW _is_llm_error ===")
from google import genai
from NodeRAG.config import NodeConfig

# Minimal config load to get the prompt template
import yaml
with open('POC_Data/documents/Node_config.yaml', 'r') as f:
    cfg = yaml.safe_load(f)
api_key = cfg['model_config']['api_keys'][0]
model = cfg['model_config']['model_name']
print(f"Using API key: {api_key[:20]}... model: {model}")

client = genai.Client(api_key=api_key)

for i, entry in enumerate(entries, 1):
    inp = entry['input']
    query = inp.get('query', '')
    # Rebuild what NodeRAG sends: query is the full prompt
    print(f"\n--- Entry {i}: text_id={entry['meta_data']['text_id']} ---")
    try:
        resp = client.models.generate_content(model=model, contents=[query])
        raw = resp.text
        is_err = _is_llm_error(raw)
        print(f"  Response len: {len(raw)}")
        print(f"  Starts with: {repr(raw[:60])}")
        print(f"  _is_llm_error() → {is_err}")
        if is_err:
            print("  *** Would be cached as error! ***")
        else:
            print("  ✓ Would be accepted as valid response")
    except Exception as e:
        print(f"  API call raised exception: {e}")
        print(f"  _is_llm_error(str(e)) → {_is_llm_error(str(e))}")
