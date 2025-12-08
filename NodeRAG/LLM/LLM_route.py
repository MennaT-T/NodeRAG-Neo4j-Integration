import asyncio
import time
from .LLM_base import I,O,Dict
from .LLM import *

from ..logging.error import (
    cache_error,
    cache_error_async
)



def LLM_route(config : ModelConfig) -> LLM:
    
    '''Route the request to the appropriate LLM service provider'''
        


    service_provider = config.get("service_provider")
    model_name = config.get("model_name")
    embedding_model_name = config.get("embedding_model_name",None)
    api_keys = config.get("api_keys",None)
        
    match service_provider:
        case "openai":
            return OPENAI(model_name, api_keys, config)
        case "openai_embedding":
            return OpenAI_Embedding(embedding_model_name, api_keys, config)
        case "gemini":
            return Gemini(model_name, api_keys, config)
        case "gemini_embedding":
            return Gemini_Embedding(embedding_model_name, api_keys, config)
        case _:
            raise ValueError("Service provider not supported")
   
            

class API_client():
    
    def __init__(self, 
                 config : ModelConfig) -> None:
        
        self.llm = LLM_route(config)
        
        # Primary: Use explicit request_delay if provided
        self.request_delay = config.get("request_delay", None)
        
        # Fallback: Calculate from rate_limit (requests per minute)
        if self.request_delay is None:
            rate_limit = config.get("rate_limit", 10)
            # Convert RPM to delay: 60 seconds / requests_per_minute
            self.request_delay = 60.0 / rate_limit if rate_limit > 0 else 6.0
        
        # Semaphore for concurrent request control (set to 1 for strict ordering)
        self.semaphore = asyncio.Semaphore(1)
        
        # Lock to protect last_request_time from race conditions
        self._lock = asyncio.Lock()
        self.last_request_time = 0.0


            
    @cache_error_async
    async def __call__(self, input: I, *,cache_path:str|None=None,meta_data:Dict|None=None) -> O:
        
        async with self.semaphore:
            # Time-based rate limiting with lock protection
            async with self._lock:
                current_time = time.time()
                elapsed = current_time - self.last_request_time
                if elapsed < self.request_delay:
                    await asyncio.sleep(self.request_delay - elapsed)
                self.last_request_time = time.time()
            
            response = await self.llm.predict_async(input)
            
        return response
    
    @cache_error
    def request(self, input:I, *,cache_path:str|None=None,meta_data:Dict|None=None) -> O:
        
        # Apply request delay for synchronous calls
        # Note: sync calls don't need async lock, but still respect delay
        current_time = time.time()
        elapsed = current_time - self.last_request_time
        if elapsed < self.request_delay:
            time.sleep(self.request_delay - elapsed)
        
        response = self.llm.predict(input)
        self.last_request_time = time.time()
        
        return response
    
    def stream_chat(self,input:I):
        yield from self.llm.stream_chat(input)
    
    
