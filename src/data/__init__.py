"""
Data package containing constants and document retrieval functionality.
"""

from .constants import DocRetrieverConstants
from .doc_id_retriever import DocRetriever

__version__ = "1.0.0"
__all__ = [
    'DocRetrieverConstants',
    'DocRetriever'
]