"""
Quick test script to verify Google AI Studio API keys work correctly
"""

import os
import sys
import asyncio
import aiohttp
from dotenv import load_dotenv

# Fix Windows console encoding for emojis
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Configuration
# Get the directory where this script is located
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(SCRIPT_DIR, ".env")
MODEL_NAME = "gemma-3-12b-it"
API_ENDPOINT = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_NAME}:generateContent"


async def test_api_key(api_key: str, key_number: int) -> bool:
    """Test if an API key works"""
    
    test_prompt = "Say 'Hello, I am working!' in a friendly way."
    
    payload = {
        "contents": [{
            "parts": [{
                "text": test_prompt
            }]
        }],
        "generationConfig": {
            "maxOutputTokens": 50,
        }
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{API_ENDPOINT}?key={api_key}",
                headers={"Content-Type": "application/json"},
                json=payload,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                
                if response.status == 200:
                    result = await response.json()
                    answer = result.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                    tokens = result.get("usageMetadata", {}).get("totalTokenCount", 0)
                    
                    print(f"✅ Key {key_number}: WORKING")
                    print(f"   Response: {answer[:100]}...")
                    print(f"   Tokens used: {tokens}")
                    return True
                    
                elif response.status == 403:
                    print(f"❌ Key {key_number}: INVALID or QUOTA EXCEEDED")
                    error_text = await response.text()
                    print(f"   Error: {error_text[:200]}")
                    return False
                    
                elif response.status == 429:
                    print(f"⚠️  Key {key_number}: RATE LIMITED (but valid)")
                    return True
                    
                else:
                    print(f"❌ Key {key_number}: ERROR (Status {response.status})")
                    error_text = await response.text()
                    print(f"   Error: {error_text[:200]}")
                    return False
                    
    except asyncio.TimeoutError:
        print(f"⏱️  Key {key_number}: TIMEOUT (network issue?)")
        return False
        
    except Exception as e:
        print(f"❌ Key {key_number}: EXCEPTION - {str(e)}")
        return False


async def main():
    """Test all API keys"""
    print("\n" + "="*70)
    print("🔑 API Key Testing Script")
    print("="*70 + "\n")
    
    # Load API keys
    load_dotenv(ENV_PATH)
    
    keys = []
    for i in range(1, 6):
        key = os.getenv(f"GEMINI_API_KEY_{i}")
        if key:
            keys.append((i, key))
    
    if not keys:
        print(f"❌ No API keys found in {ENV_PATH}")
        print(f"   Please create {ENV_PATH} with GEMINI_API_KEY_1 to GEMINI_API_KEY_5")
        return
    
    print(f"📋 Found {len(keys)} API key(s) to test\n")
    
    # Test each key
    working_keys = 0
    for key_num, api_key in keys:
        masked_key = api_key[:8] + "..." + api_key[-4:] if len(api_key) > 12 else "***"
        print(f"\n🧪 Testing Key {key_num}: {masked_key}")
        
        success = await test_api_key(api_key, key_num)
        if success:
            working_keys += 1
        
        # Small delay between tests
        if key_num < len(keys):
            await asyncio.sleep(1)
    
    # Summary
    print("\n" + "="*70)
    print("📊 Test Summary")
    print("="*70)
    print(f"✅ Working keys: {working_keys}/{len(keys)}")
    print(f"❌ Failed keys: {len(keys) - working_keys}/{len(keys)}")
    
    if working_keys > 0:
        print(f"\n🎉 You're ready to run the main script!")
        print(f"   Test with: python Dataset/run_llm_on_dataset.py 5")
        print(f"   Full run: python Dataset/run_llm_on_dataset.py")
    else:
        print(f"\n⚠️  No working keys found. Please check your API keys.")
        print(f"   Get keys at: https://aistudio.google.com/app/apikey")
    
    print()


if __name__ == "__main__":
    asyncio.run(main())

