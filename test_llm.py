"""Quick test to see exactly what Gemma-3-12b returns for the two failing text chunks."""
import os
import sys
sys.path.insert(0, '.')
os.environ.pop('GOOGLE_API_KEY', None)   # ensure we use yaml key, not env var

from google import genai

API_KEY = 'AIzaSyDmYbzjoIKzYlaT_bbB83-eq-e4zneTjsg'
MODEL   = 'models/gemma-3-12b-it'

# Abbreviated version of the actual NodeRAG text-decomposition prompt
PROMPT_TEMPLATE = """
Goal: Given a text, segment it into multiple semantic units.
OUTPUT FORMAT:
You MUST respond with valid JSON:
{{"Output": [{{"semantic_unit": "string", "entities": ["ENTITY1"], "relationships": ["A, rel, B"]}}]}}
CRITICAL: Respond with ONLY the JSON object, no markdown, no explanations.

Text:{text}
"""

SHORT_TEXT = "(Microsoft Access) - DB2 - MySQL\nMethodologies: Data Integration - ETL Methodologies\nExtracurricular Activities"

ETL_SNIPPET = """Talend ETL Developer On-Site
Tata Consultancy Services Feb 2016 - Jan 2018
• Designed and developed end-to-end ETL processes
• Troubleshot long-running jobs and fixed identified issues
• Demonstrated excellent error handling capabilities
• Performed Unit and System testing to validate data loads"""

client = genai.Client(api_key=API_KEY)

for label, text in [("SHORT (skills)", SHORT_TEXT), ("ETL snippet", ETL_SNIPPET)]:
    print(f"\n{'='*60}")
    print(f"TEST: {label}")
    print(f"{'='*60}")
    prompt = PROMPT_TEMPLATE.format(text=text)
    try:
        resp = client.models.generate_content(model=MODEL, contents=[prompt])
        raw = resp.text
        print(f"Length: {len(raw)}")
        print(f"Starts with: {repr(raw[:80])}")
        print(f"Contains 'error': {'error' in raw.lower()}")
        # Check if valid JSON
        import json
        stripped = raw.strip()
        if stripped.startswith(('{','[')):
            try:
                parsed = json.loads(stripped)
                top_has_error = isinstance(parsed, dict) and 'error' in parsed
                print(f"Valid JSON: YES — top-level 'error' key: {top_has_error}")
            except Exception as e:
                print(f"Valid JSON: NO — parse error: {e}")
        else:
            print(f"NOT JSON (starts with non-brace char)")
    except Exception as e:
        print(f"API call FAILED: {e}")
