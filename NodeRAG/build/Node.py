from enum import Enum
import os
import json
from rich.tree import Tree
import asyncio
import sys

from ..config import NodeConfig

from .pipeline import (
    INIT_pipeline,
    document_pipline,
    text_pipline,
    Graph_pipeline,
    Attribution_generation_pipeline,
    Embedding_pipeline,
    SummaryGeneration,
    Insert_text,
    HNSW_pipeline,
    QA_Pipeline
)


class State(Enum):
    INIT = "INIT"
    DOCUMENT_PIPELINE = "Document pipeline"
    TEXT_PIPELINE = "Text pipeline" 
    GRAPH_PIPELINE = "Graph pipeline"
    QA_PIPELINE = "Q&A pipeline"
    ATTRIBUTE_PIPELINE = "Attribute pipeline"
    EMBEDDING_PIPELINE = "Embedding pipeline"
    SUMMARY_PIPELINE = "Summary pipeline"
    INSERT_TEXT = "Insert text pipeline"
    HNSW_PIPELINE = "HNSW pipeline"
    FINISHED = "FINISHED"
    ERROR = "ERROR"
    ERROR_LOG = "ERROR_LOG"
    ERROR_CACHE = "ERROR_CACHE"
    NO_ERROR = "NO_ERROR"
    
class NodeRag():
    def __init__(self,config:NodeConfig,web_ui:bool=False, incremental:bool=True):
        self._Current_state=State.INIT
        self.Error_type=State.NO_ERROR
        self.Is_incremental=False
        self.force_full_build = not incremental  # If incremental=False, force full build
        self.config=config
        self.console = self.config.console
        self.config.config_integrity()
        self._documents = None
        self._hash_ids = None
        self.observers = []
        self.web_ui = web_ui



        # define the state to pipeline mapping
        self.state_pipeline_map = {
            State.DOCUMENT_PIPELINE: document_pipline,
            State.TEXT_PIPELINE: text_pipline,
            State.GRAPH_PIPELINE: Graph_pipeline,
            State.ATTRIBUTE_PIPELINE: Attribution_generation_pipeline,
            State.EMBEDDING_PIPELINE: Embedding_pipeline,
            State.SUMMARY_PIPELINE: SummaryGeneration,
            State.INSERT_TEXT: Insert_text,
            State.HNSW_PIPELINE: HNSW_pipeline
        }
        
        # define the state sequence
        self.state_sequence = [
            State.INIT,
            State.DOCUMENT_PIPELINE,
            State.TEXT_PIPELINE,
            State.GRAPH_PIPELINE,
            State.QA_PIPELINE,
            State.ATTRIBUTE_PIPELINE,
            State.EMBEDDING_PIPELINE,
            State.SUMMARY_PIPELINE,
            State.INSERT_TEXT,
            State.HNSW_PIPELINE,
            State.FINISHED
        ]
        
    @property
    def state_dict(self):
        return {'Current_state':self.Current_state.value,
                'Error_type':self.Error_type.value,
                'Is_incremental':self.Is_incremental}
        
    @property
    def Current_state(self):
        return self._Current_state
    
    @Current_state.setter
    def Current_state(self,state:State):
        self._Current_state = state
        self.notify_state_change()
        
    def notify_state_change(self):
        
        for observer in self.observers:
            observer.update(self.Current_state.value)
    
    def add_observer(self,observer):
        
        self.observers.append(observer)
    
    def _init_qa_api_client(self):
        """Initialize Q&A API client from config"""
        try:
            from ..utils.qa_api_client import QAAPIClient
            
            # Access config correctly: self.config.config is the nested config dict
            api_config = self.config.config.get('qa_api', {})
            if not api_config or not api_config.get('enabled', False):
                return None
            
            # Determine if using mock data or real API
            use_mock = api_config.get('use_mock', True)
            api_base_url = api_config.get('base_url')
            mock_data_path = api_config.get('mock_data_path')
            
            # If mock_data_path is relative, resolve relative to main_folder
            if mock_data_path and not os.path.isabs(mock_data_path):
                # Resolve relative to the original main_folder (not effective_main_folder)
                # because mock data might be shared across users
                main_folder = self.config.main_folder
                mock_data_path = os.path.join(main_folder, mock_data_path)
                mock_data_path = os.path.normpath(mock_data_path)
            
            client = QAAPIClient(
                api_base_url=api_base_url,
                mock_data_path=mock_data_path,
                use_mock=use_mock
            )
            return client
        except Exception as e:
            self.config.console.print(f"[yellow]Warning: Failed to initialize QA API client: {e}[/yellow]")
            return None
        

    def set_state(self,state:State):
        
        self.Current_state = state
        
    def get_state(self):
        
        return self.Current_state
    
    async def state_transition(self):
        
        
        try:
            while True:
                self.update_state_tree()
                index = self.state_sequence.index(self.Current_state)
                if self.Current_state != State.FINISHED:
                    self.Current_state = self.state_sequence[index+1]
                
                if self.Current_state == State.FINISHED:
                    if self.Is_incremental:
                        if self.web_ui:
                            self.console.print("[bold green]Detected incremental file, Continue building.[/bold green]")
                            self.Current_state = State.DOCUMENT_PIPELINE
                            self.Is_incremental = False
                        else:
                            user_input = self.console.input("[bold green]Detected incremental file, Please enter 'y' to continue. Any other input will cancel the pipeline.[/bold green]")
                            if user_input.lower() == 'y':
                                self.console.print("[bold green]Pipeline finished. No incremental mode.[/bold green]")
                                self.Current_state = State.DOCUMENT_PIPELINE
                                self.Is_incremental = False
                            else:
                                self.console.print("[bold red]Pipeline cancelled by user.[/bold red]")
                                sys.exit()
                        
                    else:
                        if self.force_full_build:
                            self.console.print("[bold green]Forced full rebuild - continuing with pipeline.[/bold green]")
                            self.Current_state = State.DOCUMENT_PIPELINE
                            self.Is_incremental = False
                        else:
                            self.console.print("[bold green]Pipeline finished. No incremental mode.[/bold green]")
                            self.store_state()
                            self.config.whole_time()
                            return

                # Special handling for QA_PIPELINE (requires API client initialization)
                if self.Current_state == State.QA_PIPELINE:
                    api_client = self._init_qa_api_client()
                    if api_client:
                        self.config.console.print(f"[bold green]Processing {self.Current_state.value}...[/bold green]")
                        qa_pipeline = QA_Pipeline(self.config, api_client)
                        await qa_pipeline.main()
                        self.config.console.print(f"[bold green]Processing {self.Current_state.value} finished.[/bold green]")
                    else:
                        # Skip QA pipeline if not configured or disabled
                        self.config.console.print(f"[yellow]Skipping {self.Current_state.value} (not configured or disabled)[/yellow]")
                else:
                    # Standard pipeline execution
                    self.config.console.print(f"[bold green]Processing {self.Current_state.value} pipeline...[/bold green]")
                    await self.state_pipeline_map[self.Current_state](self.config).main()
                    self.config.console.print(f"[bold green]Processing {self.Current_state.value} pipeline finished.[/bold green]")
        
        except Exception as e:
            error_message = str(e)
            if 'Error cached' in error_message:
                self.Error_type = State.ERROR_CACHE
            elif 'error log' in error_message:
                self.Error_type = State.ERROR_LOG
            else:
                self.Error_type = State.ERROR
            self.store_state()
            raise Exception(f'Error happened in {self.Current_state.value}.{e}')
        except KeyboardInterrupt:
            self.store_state()
            self.config.console.print("\n[bold red]Pipeline interrupted by user.[/bold red]")
            sys.exit(0)
        
    def load_state(self):
        
        if os.path.exists(self.config.state_path):
            state_dict = json.load(open(self.config.state_path,'r'))
            self.Current_state = State(state_dict['Current_state'])
            self.Error_type = State(state_dict['Error_type'])
            self.Is_incremental = state_dict['Is_incremental']
        
    
    def store_state(self):
        
        json.dump(self.state_dict,open(self.config.state_path,'w'))
    
   
        
    def display_state_tree(self):
        
        tree = Tree("[bold cyan]🌳 State Tree[/bold cyan]")
        
        for state in self.state_sequence:
            tree.add(f"{state.value}", style="bright_green")
        
        self.console.print(tree)
        self.console.print(f"[bold green]Current working directory: {self.config.main_folder}[/bold green]")
        
        if self.web_ui:
            return
        
        while True:
            user_input = self.console.input("[bold blue]\nDo you want to start the pipeline? (y/n)[/bold blue] ")
            if user_input.lower() == 'y':
                self.console.clear()
                break
            elif user_input.lower() == 'n':
                self.console.print("[bold red]Pipeline cancelled by user.[/bold red]")
                sys.exit()
            else:
                self.console.input("[bold red]Invalid input. Please enter 'y' or 'n'.[/bold red]")
                
    def update_state_tree(self):
        
        self.console.clear()
        tree = Tree("[bold cyan]🚀 Processing Pipeline[/bold cyan]")
        index = self.state_sequence.index(self.Current_state)
        
        for i in range(index+1):
            tree.add(f"[green]{self.state_sequence[i].value} Done[/green]")
        
        self.console.print(tree)
    
    async def error_handler(self):
        
        self.update_state_tree()
        
        if self.Error_type == State.ERROR_LOG or self.Error_type == State.ERROR:
            self.console.print("[bold red]Error logged. Rerun the pipeline from the current state.[/bold red]")
        
            try:
                await self.state_pipeline_map[self.Current_state](self.config).main()
        
            except Exception as e:
                self.store_state()
                self.Error_type = State.ERROR
                raise Exception(f'Error happened in {self.Current_state} pipeline, please check the error log.{e}')
           
        if self.Error_type == State.ERROR_CACHE:
        
            self.console.print("[bold red]Error cached. Rerun the pipeline from the current state.[/bold red]")
        
            try:
                await self.state_pipeline_map[self.Current_state](self.config).rerun()
        
            except Exception as e:
                self.Error_type = State.ERROR_CACHE
                self.store_state()
                raise Exception(f'Error happened in {self.Current_state} pipeline, please check the error log.{e}')
        
        self.Error_type = State.NO_ERROR
       
    async def _run_async(self):
        
        self.load_state()
        
        self.Is_incremental = await INIT_pipeline(self.config).main()
            
        if self.Current_state == State.INIT:
            self.display_state_tree()
        
        if self.Error_type != State.NO_ERROR:
            await self.error_handler()
        
        if self.Error_type == State.NO_ERROR:
            await self.state_transition()  
    
    def run(self):
        asyncio.run(self._run_async())
        
        
