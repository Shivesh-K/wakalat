"""
Document Retriever Package

This package provides functionality for retrieving documents from web sources
with comprehensive logging and error handling.
"""

from .base import WakalatLogger
from .src.data import DocRetriever

__version__ = "1.0.0"
__author__ = "Document Retrieval Team"

# Make key classes available at package level
__all__ = [
    'WakalatLogger',
    'DocRetriever'
]