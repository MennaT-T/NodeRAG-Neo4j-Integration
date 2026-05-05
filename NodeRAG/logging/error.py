from functools import wraps
from .logger import setup_logger
import json
import os

error_logger = setup_logger(__name__,os.path.join(os.getcwd(),'error.log'))


def _is_llm_error(response: str) -> bool:
    """
    Determine whether a string response from the LLM represents an actual API error
    rather than valid content that happens to contain words like 'error'.

    Strategy:
    1. If the response is valid JSON and does NOT have a top-level 'error' key,
       treat it as a legitimate LLM output regardless of its content.
    2. If it is valid JSON with a top-level 'error' key → definite API error.
    3. For non-JSON strings, fall back to keyword heuristics but avoid
       the catch-all "error" substring check that causes false positives on
       resumes/job descriptions that legitimately discuss error handling.
    """
    stripped = response.strip()

    # --- JSON path ---
    if stripped.startswith(('{', '[')):
        try:
            parsed = json.loads(stripped)
            # Valid JSON: only an error if the top-level object has an 'error' key
            if isinstance(parsed, dict) and 'error' in parsed:
                return True
            return False          # Valid JSON output → not an error
        except (json.JSONDecodeError, ValueError):
            pass                  # Fall through to string heuristics

    # --- String / non-JSON path ---
    # Avoid the broad `"error" in text` match; use only unambiguous signals.
    lower = response.lower()
    definite_api_errors = (
        "api key" in lower or
        "api_key" in lower or
        "authentication" in lower or
        "unauthorized" in lower or
        "forbidden" in lower or
        "rate limit" in lower or
        "quota exceeded" in lower or
        "invalid_argument" in lower or
        "permission denied" in lower or
        "key expired" in lower or
        "invalid api" in lower or
        "billing" in lower
    )
    if definite_api_errors:
        return True

    # Very short responses are almost certainly errors (real output is always long)
    if len(stripped) < 50:
        return True

    return False

def error_handler(func): 
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            return str(e)
    return wrapper
        
def error_handler_async(func): 
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            return str(e)
    return wrapper

def cache_error(func): 
    @wraps(func)
    def wrapper(*args, **kwargs):
        response = func(*args, **kwargs)
        
        if isinstance(response, list):
            return response
            
        if isinstance(response, str):
            if kwargs.get('cache_path'):
                is_error = _is_llm_error(response)
                
                if is_error:
                    error_msg = f"LLM Error: {response}"
                    print(f'\n[ERROR] {error_msg}\n')
                    error_logger.error(error_msg)
                    
                    try:
                        input_data = args[1] if len(args) > 1 else kwargs.get('input', None)
                        if input_data:
                            error_logger.error(f"Input data: {json.dumps(input_data, indent=2)[:500]}")
                    except:
                        pass
                    
                    meta_data = kwargs.get('meta_data',None)
                        
                    if meta_data is not None:
                        cache_path = kwargs.get('cache_path')
                            
                        input_data = args[1]
                        if input_data is None:
                            input_data = kwargs.get('input',None)
                        if isinstance(input_data,dict):
                            if input_data.get('response_format',None) is not None:
                                input_data.pop('response_format')
                        LLM_store = {'input':input_data,'meta_data':meta_data}
                        with open(cache_path,'a') as f:
                            f.write(json.dumps(LLM_store)+'\n')
                            response = 'Error cached'
                if response == 'Error cached':
                    return response
                else:
                    if is_error:
                        raise Exception(f'LLM Error: {response}')
        return response
            
    return wrapper

def cache_error_async(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        response = await func(*args, **kwargs)
        if isinstance(response, str):
            if kwargs.get('cache_path'):
                is_error = _is_llm_error(response)
                
                if is_error:
                    error_msg = f"LLM Error: {response}"
                    print(f'\n[ERROR] {error_msg}\n')
                    error_logger.error(error_msg)
                    
                    try:
                        input_data = args[1] if len(args) > 1 else kwargs.get('input', None)
                        if input_data:
                            error_logger.error(f"Input data: {json.dumps(input_data, indent=2)[:500]}")
                    except:
                        pass
                
                    meta_data = kwargs.get('meta_data',None)
                            
                    if meta_data is not None:
                        if kwargs.get('cache_path',None) is not None:
                            cache_path = kwargs.get('cache_path')
                            
                            input_data = args[1]
                            if input_data is None:
                                input_data = kwargs.get('input',None)
                            if isinstance(input_data, dict) and input_data.get('response_format',None) is not None:
                                input_data.pop('response_format')
                            LLM_store = {'input':input_data,'meta_data':meta_data}
                            with open(cache_path,'a') as f:
                                f.write(json.dumps(LLM_store)+'\n')
                                response = 'Error cached'
                    if response == 'Error cached':
                        return response
                    else:
                        raise Exception(f'LLM Error: {response}')
        return response
            
    return wrapper

def clear_cache(path:str) -> None:
    with open(path,'w') as f:
        f.write('')
    return 'cache cleared'