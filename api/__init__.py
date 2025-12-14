"""
NodeRAG FastAPI Backend
=======================

A comprehensive REST API for the NodeRAG knowledge graph system.

Endpoints cover:
- Graph building and management
- Search and Q&A
- Document management (resumes, job descriptions)
- Q&A node management
- Neo4j synchronization

Author: Generated for Graduation Project
Version: 1.0.0
"""

from .main import app
from .models import *
from .services import *

__all__ = ['app']
