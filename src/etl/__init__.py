"""
ETL Package for Weekly Document Retrieval Pipeline

This package provides a comprehensive ETL solution for incrementally
retrieving and loading document data into BigQuery using GCP services.
"""

from .services import ETLOrchestrator, IncrementalDocumentChecker, WatermarkManager
from .models import (
    ETLJobStatus,
    ETLRunMetrics,
    DocumentBatch,
    WatermarkState
)

__version__ = "1.0.0"
__all__ = [
    'ETLOrchestrator',
    'IncrementalDocumentChecker',
    'WatermarkManager',
    'ETLJobStatus',
    'ETLRunMetrics',
    'DocumentBatch',
    'WatermarkState'
]
