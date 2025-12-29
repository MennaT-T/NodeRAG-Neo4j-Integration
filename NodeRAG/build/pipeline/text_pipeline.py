from typing import Dict,List
import pandas as pd
import asyncio
import os
import json

from ...config import NodeConfig
from ...LLM import LLM_message
from ...storage import storage
from ..component import Text_unit
from ...logging.error import clear_cache
from ...logging import info_timer

class text_pipline():
        
        def __init__(self, config:NodeConfig)-> None:
            
            self.config = config
            self.texts = self.load_texts()
            
            
        def load_texts(self) -> pd.DataFrame:
            
            texts = storage.load_parquet(self.config.text_path)
            return texts
        
        async def text_decomposition_pipline(self) -> None:
            
            # Skip if no texts to process
            if len(self.texts) == 0:
                self.config.console.print("[green]No texts to process - all already decomposed[/green]")
                return
            
            async_task = []
            total_texts = len(self.texts)
            self.config.tracker.set(total_texts, 'Text Decomposition')
            
            for index, row in self.texts.iterrows():
                # Handle both 'hash_id' and 'id' column names (Neo4j uses 'id')
                node_id = row.get('hash_id', row.get('id'))
                text = Text_unit(row['context'], node_id, row['text_id'])
                async_task.append(text.text_decomposition(self.config))
            await asyncio.gather(*async_task)
            
                
        def increment(self) -> None:
            
            exist_hash_id = []
            
            # Read cache file with error handling for malformed entries
            try:
                with open(self.config.text_decomposition_path,'r',encoding='utf-8') as f:
                    for line_num, line in enumerate(f, 1):
                        line = line.strip()
                        if not line:  # Skip empty lines
                            continue
                        try:
                            line_data = json.loads(line)
                            # The cache file stores 'text_hash_id', not 'hash_id'
                            hash_key = line_data.get('text_hash_id') or line_data.get('hash_id')
                            if hash_key:
                                exist_hash_id.append(hash_key)
                        except json.JSONDecodeError:
                            # Skip malformed JSON lines
                            continue
            except FileNotFoundError:
                # Cache file doesn't exist yet, nothing to filter
                return
            except Exception as e:
                # Log error but continue - better to process than fail silently
                self.config.console.print(f"[yellow]Warning: Error reading cache file: {e}[/yellow]")
                return
            
            # Handle both 'hash_id' and 'id' column names (Neo4j uses 'id')
            if len(self.texts) == 0:
                return  # Nothing to filter
            
            id_column = 'hash_id' if 'hash_id' in self.texts.columns else 'id'
            if id_column not in self.texts.columns:
                # Column doesn't exist, can't filter
                self.config.console.print(f"[yellow]Warning: Column '{id_column}' not found in texts DataFrame[/yellow]")
                return
            
            self.texts = self.texts[~self.texts[id_column].isin(exist_hash_id)]
            
        async def rerun(self) -> None:
            
            self.texts = self.load_texts()
            
            with open(self.config.LLM_error_cache,'r',encoding='utf-8') as f:
                LLM_store = []
                for line in f:
                    line = json.loads(line)
                    LLM_store.append(line)
            
            clear_cache(self.config.LLM_error_cache)
            
            await self.rerun_request(LLM_store)
            # Filter out already processed texts before continuing
            if os.path.exists(self.config.text_decomposition_path):
                if os.path.getsize(self.config.text_decomposition_path) > 0:
                    self.increment()
            # After rerun, continue with normal processing of any remaining texts
            # This handles both: (1) new texts added since last run, (2) texts that were never attempted
            await self.text_decomposition_pipline()
            self.config.tracker.close()
            # CRITICAL: Check if any errors occurred during rerun
            self.check_error_cache()
                    
        async def rerun_request(self,LLM_store:List[Dict]) -> None:
            tasks = []
            
            self.config.tracker.set(len(LLM_store),'Rerun LLM on error cache of text decomposition pipeline')
            
            for store in LLM_store:
                input_data = store['input']
                store.pop('input')
                input_data.update({'response_format':self.config.prompt_manager.text_decomposition_json})    
                tasks.append(self.request_save(input_data,store,self.config))
            await asyncio.gather(*tasks)
            self.config.tracker.close()
        
        async def request_save(self,
                               input_data:LLM_message,
                               meta_data:Dict) -> None:
            
            response = await self.config.client(input_data,cache_path=self.config.LLM_error_cache,meta_data = meta_data)
            
            # Write complete data structure with metadata (same format as text_unit.text_decomposition)
            with open(self.config.text_decomposition_path,'a',encoding='utf-8') as f:
                data = {**meta_data, 'response': response}
                f.write(json.dumps(data, ensure_ascii=False) + '\n')
            
            self.config.tracker.update()
            
        def check_error_cache(self) -> None:
            
            if os.path.exists(self.config.LLM_error_cache):
                num = 0
                error_details = []
                
                with open(self.config.LLM_error_cache,'r',encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            num += 1
                            try:
                                error_data = json.loads(line)
                                # Try to extract useful info
                                meta = error_data.get('meta_data', {})
                                text_id = meta.get('text_id', 'unknown')
                                text_hash = meta.get('text_hash_id', 'unknown')[:8] if meta.get('text_hash_id') else 'unknown'
                                error_details.append(f"  - Text ID: {text_id}, Hash: {text_hash}")
                            except:
                                error_details.append(f"  - Error entry #{num}")
                        
                if num > 0:
                    self.config.console.print(f"[red]LLM Error Detected: There are {num} errors")
                    if error_details:
                        self.config.console.print("[yellow]Affected texts:")
                        for detail in error_details[:5]:  # Show first 5
                            self.config.console.print(f"[yellow]{detail}")
                        if len(error_details) > 5:
                            self.config.console.print(f"[yellow]  ... and {len(error_details) - 5} more")
                    
                    # Try to read error.log if it exists
                    error_log_path = os.path.join(os.getcwd(), 'error.log')
                    if os.path.exists(error_log_path):
                        try:
                            with open(error_log_path, 'r', encoding='utf-8') as f:
                                error_lines = f.readlines()
                                if error_lines:
                                    self.config.console.print("[red]Recent error messages from error.log:")
                                    # Show last 3 error lines
                                    for line in error_lines[-3:]:
                                        if line.strip():
                                            self.config.console.print(f"[red]  {line.strip()[:200]}")  # First 200 chars
                        except Exception as e:
                            pass
                    
                    self.config.console.print("[red]Error cache file: LLM_error.jsonl (in cache folder)")
                    self.config.console.print("[red]Error log file: error.log (in working directory)")
                    self.config.console.print("[red]Please fix the error and run the pipeline again")
                    raise Exception(f"Error happened in text decomposition pipeline: {num} error(s) cached. Check error.log for details.")

        @info_timer(message='Text Pipeline')
        async def main(self) -> None:
            
            if os.path.exists(self.config.text_decomposition_path):
                if os.path.getsize(self.config.text_decomposition_path) > 0:
                    self.increment()
                    
            await self.text_decomposition_pipline()
            self.config.tracker.close()
            self.check_error_cache()

            
                
                
        
            
            
            
    