"""
ETL Package for Weekly Document Retrieval Pipeline

This package provides a comprehensive ETL solution for incrementally
retrieving and loading document data into BigQuery using GCP services.
"""

from .etl_orchestrator import ETLOrchestrator
from .incremental_checker import IncrementalDocumentChecker
from .watermark_manager import WatermarkManager

__version__ = "1.0.0"
__all__ = [
    'ETLOrchestrator',
    'IncrementalDocumentChecker',
    'WatermarkManager'
]
