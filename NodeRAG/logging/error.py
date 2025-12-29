from functools import wraps
from .logger import setup_logger
import json
import os

error_logger = setup_logger(__name__,os.path.join(os.getcwd(),'error.log'))

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
                # Check for any error indicators (not just "'error':")
                is_error = (
                    "'error':" in response.lower() or
                    "error" in response.lower() or
                    "exception" in response.lower() or
                    "failed" in response.lower() or
                    "authentication" in response.lower() or
                    "rate limit" in response.lower() or
                    "api key" in response.lower() or
                    "unauthorized" in response.lower() or
                    "forbidden" in response.lower() or
                    len(response) < 100  # Very short responses are likely errors
                )
                
                if is_error:
                    # ALWAYS log errors - make them visible
                    error_msg = f"LLM Error: {response}"
                    print(f'\n[ERROR] {error_msg}\n')  # Print to console immediately
                    error_logger.error(error_msg)
                    
                    # Also log the full context
                    try:
                        input_data = args[1] if len(args) > 1 else kwargs.get('input', None)
                        if input_data:
                            error_logger.error(f"Input data: {json.dumps(input_data, indent=2)[:500]}")  # First 500 chars
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
                    # If error detected but not cached, still raise with the actual error message
                    raise Exception(f'LLM Error: {response}')
        return response
            
    return wrapper

def cache_error_async(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        response = await func(*args, **kwargs)
        if isinstance(response, str):
            if kwargs.get('cache_path'):
                # Check for any error indicators (not just "'error':")
                is_error = (
                    "'error':" in response.lower() or
                    "error" in response.lower() or
                    "exception" in response.lower() or
                    "failed" in response.lower() or
                    "authentication" in response.lower() or
                    "rate limit" in response.lower() or
                    "api key" in response.lower() or
                    "unauthorized" in response.lower() or
                    "forbidden" in response.lower() or
                    len(response) < 100  # Very short responses are likely errors
                )
                
                if is_error:
                    # ALWAYS log errors - make them visible
                    error_msg = f"LLM Error: {response}"
                    print(f'\n[ERROR] {error_msg}\n')  # Print to console immediately
                    error_logger.error(error_msg)
                    
                    # Also log the full context
                    try:
                        input_data = args[1] if len(args) > 1 else kwargs.get('input', None)
                        if input_data:
                            error_logger.error(f"Input data: {json.dumps(input_data, indent=2)[:500]}")  # First 500 chars
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
                        # If error detected but not cached, still raise with the actual error message
                        raise Exception(f'LLM Error: {response}')
        return response
            
    return wrapper

def clear_cache(path:str) -> None:
    with open(path,'w') as f:
        f.write('')
    return 'cache cleared'